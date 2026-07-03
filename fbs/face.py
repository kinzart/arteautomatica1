"""Detecção de rosto (OpenCV Haar Cascade) + calibração de âncora a partir
do próprio PSD, pra posicionar a foto nova sem depender de um `foco` chumbado
(HANDOFF_v4 §2). Sem mediapipe: já tínhamos opencv-python instalado, e
mediapipe puxaria upgrade de numpy 1.26->2.4 com risco real de quebrar
psd-tools/scikit-image — Haar Cascade é a alternativa que o próprio
HANDOFF_v4 já aceita.
"""
import json
import os

import cv2
import numpy as np
from PIL import Image

from . import config, util

_cascade = None


def _carregar_cascade():
    global _cascade
    if _cascade is None:
        caminho = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        _cascade = cv2.CascadeClassifier(caminho)
    return _cascade


def detectar_rosto(pil_img):
    """Detecta o maior rosto em `pil_img`. Retorna (cx, cy, w, h) relativos
    (0.0-1.0) ao tamanho da imagem, ou None se não achar nenhum."""
    cascade = _carregar_cascade()
    arr = np.array(pil_img.convert("L"))
    rostos = cascade.detectMultiScale(arr, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    if len(rostos) == 0:
        return None
    x, y, w, h = max(rostos, key=lambda r: r[2] * r[3])
    largura, altura = pil_img.size
    return ((x + w / 2) / largura, (y + h / 2) / altura, w / largura, h / altura)


def _caminho_ancora(formato):
    return os.path.join(config.TEMPLATES_DIR, f"fbs_{formato}.anchor.json")


def calibrar_ancora(psd, variaveis, formato):
    """Extrai a foto original de `foto_artista`, detecta o rosto nela, e
    salva a âncora (posição do rosto relativa ao bbox da camada + altura do
    rosto em px) em `assets/templates/fbs_{formato}.anchor.json`.

    Como `layer.topil()` retorna a foto no tamanho exato do bbox da camada,
    a posição relativa do rosto NA FOTO já é a posição relativa DENTRO DO
    BBOX — não precisa converter pra coordenadas de canvas.

    Retorna o dict salvo, ou None se não detectar rosto (não escreve nada
    nesse caso — mantém a calibração anterior, se houver).
    """
    foto_layer = variaveis["foto_artista"]["layer_ref"]
    foto_original = foto_layer.topil().convert("RGB")

    rosto = detectar_rosto(foto_original)
    if rosto is None:
        return None

    cx_rel, cy_rel, _w_rel, h_rel = rosto
    dados = {
        "ancora_x_rel": cx_rel,
        "ancora_y_rel": cy_rel,
        "altura_rosto_px": h_rel * foto_original.height,
    }
    os.makedirs(config.TEMPLATES_DIR, exist_ok=True)
    with open(_caminho_ancora(formato), "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2)
    return dados


def calibrar_se_necessario(formato, logger=None):
    """Lê a âncora salva se ainda for válida (PSD não mudou desde a última
    calibração); recalibra automaticamente se o PSD for mais novo que o
    `.anchor.json`, ou se o arquivo não existir ainda (HANDOFF_v4 §5).

    Retorna o dict da âncora, ou None se o template não existir ou nenhum
    rosto tiver sido detectado (fallback pro enquadramento manual)."""
    psd_path = config.TEMPLATE_FILES.get(formato)
    if not psd_path or not os.path.isfile(psd_path):
        return None

    caminho = _caminho_ancora(formato)
    precisa_calibrar = (
        not os.path.isfile(caminho)
        or os.path.getmtime(psd_path) > os.path.getmtime(caminho)
    )
    if not precisa_calibrar:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)

    from psd_tools import PSDImage

    from . import psd_reader

    psd = PSDImage.open(psd_path)
    variaveis = psd_reader.extrair_variaveis(psd)
    dados = calibrar_ancora(psd, variaveis, formato)
    if dados is None and logger:
        logger.warning("calibrar_ancora: rosto não detectado no template '%s' — fallback fit_cover", formato)
    return dados


def posicionar_por_rosto(foto_nova, largura_bbox, altura_bbox, ancora, foco_fallback="topo", log=None):
    """Posiciona `foto_nova` num viewport `largura_bbox` x `altura_bbox`,
    alinhando o rosto detectado nela à âncora calibrada — mesmo tamanho
    relativo de rosto, mesma posição relativa dentro do bbox que a
    referência. Sempre cobre o bbox inteiro (nunca deixa borda vazia).

    Sem rosto detectável (na foto nova OU sem âncora calibrada): cai no
    `fit_cover` simples com `foco_fallback`, e loga aviso.
    """
    rosto = detectar_rosto(foto_nova) if ancora is not None else None
    if rosto is None:
        if log:
            log.warning(
                "posicionar_por_rosto: rosto não detectado — usando fit_cover(foco=%s)",
                foco_fallback,
            )
        return util.fit_cover(foto_nova, largura_bbox, altura_bbox, foco=foco_fallback)

    cx_rel, cy_rel, _w_rel, h_rel = rosto
    altura_rosto_nova = h_rel * foto_nova.height
    if altura_rosto_nova <= 0:
        return util.fit_cover(foto_nova, largura_bbox, altura_bbox, foco=foco_fallback)

    escala_rosto = ancora["altura_rosto_px"] / altura_rosto_nova
    escala_cover = max(largura_bbox / foto_nova.width, altura_bbox / foto_nova.height)
    escala = max(escala_rosto, escala_cover)  # nunca menor que o cover mínimo

    novo_w = max(int(round(foto_nova.width * escala)), largura_bbox)
    novo_h = max(int(round(foto_nova.height * escala)), altura_bbox)
    redim = foto_nova.resize((novo_w, novo_h), Image.LANCZOS)

    face_x = cx_rel * novo_w
    face_y = cy_rel * novo_h
    ancora_local_x = ancora["ancora_x_rel"] * largura_bbox
    ancora_local_y = ancora["ancora_y_rel"] * altura_bbox

    crop_x1 = int(round(face_x - ancora_local_x))
    crop_y1 = int(round(face_y - ancora_local_y))
    crop_x1 = min(max(crop_x1, 0), novo_w - largura_bbox)
    crop_y1 = min(max(crop_y1, 0), novo_h - altura_bbox)

    return redim.crop((crop_x1, crop_y1, crop_x1 + largura_bbox, crop_y1 + altura_bbox))
