"""Abre o PSD, extrai as camadas variáveis e compõe a base (fundo + fixos, sem variáveis)."""
import logging

import numpy as np
from PIL import Image
from psd_tools.api.layers import PixelLayer

from . import config

# benigno (BRIEF_v3 §6) — psd-tools às vezes falha em ler um marcador extra de
# ajuste de Curvas que não afeta o resultado composto.
logging.getLogger("psd_tools.psd.adjustments").setLevel(logging.ERROR)


def _resolver_slot(nome_camada):
    if nome_camada in config.CAMADAS_VARIAVEIS:
        return nome_camada
    return config.MAPA_CAMADAS_LEGADO.get(nome_camada)


def _extrair_tracking(layer):
    try:
        ed = layer.engine_dict
        style = ed["StyleRun"]["RunArray"][0]["StyleSheet"]["StyleSheetData"]
        return style.get("Tracking", 0)
    except Exception:
        return 0


def _amostrar_cor(layer, fallback=(243, 238, 227)):
    """Cor real do texto renderizado (glifo + eventual pattern overlay/textura),
    amostrada do composite isolado da camada.

    Mais fiel que ler `FillColor.Values` bruto: nesse PSD, `GONZALO ARAYA` e
    `CONVIDA #28` retornam FillColor [1,1,1,1] (viraria preto pela fórmula
    CMYK->RGB do brief), mas a cor visível é creme/âmbar — o valor "puro" não
    reflete blend modes/pattern overlay aplicados no layer style.
    """
    try:
        img = np.array(layer.composite().convert("RGBA"))
        alpha = img[..., 3]
        mask = alpha > 128
        if not mask.any():
            return fallback
        media = img[..., :3][mask].mean(axis=0)
        return tuple(int(v) for v in media)
    except Exception:
        return fallback


def extrair_variaveis(psd):
    """Retorna {slot: metadata} para as 7 camadas variáveis do PSD.

    slot é sempre um dos nomes em config.CAMADAS_VARIAVEIS, independente do
    nome real da camada (ver config.MAPA_CAMADAS_LEGADO pra camadas que ainda
    não foram renomeadas pra convenção do brief no Photoshop).
    """
    variaveis = {}
    for layer in psd.descendants():
        slot = _resolver_slot(layer.name)
        if slot is None:
            continue
        if slot in variaveis:
            raise ValueError(
                f"camada duplicada pro slot '{slot}': '{layer.name}' e "
                f"'{variaveis[slot]['layer_ref'].name}' (nomes ambíguos no PSD)"
            )
        meta = {
            "slot": slot,
            "bbox": layer.bbox,
            "kind": layer.kind,
            "opacity": layer.opacity,
            "layer_ref": layer,
        }
        if layer.kind == "type":
            meta["text"] = layer.text
            meta["tracking"] = _extrair_tracking(layer)
            meta["cor_rgb"] = _amostrar_cor(layer)
        variaveis[slot] = meta

    faltando = config.CAMADAS_VARIAVEIS - variaveis.keys()
    if faltando:
        raise ValueError(f"camadas variáveis não encontradas no PSD: {sorted(faltando)}")

    return variaveis


def meta_texto(layer, slot):
    """Converte uma camada de texto adicional do PSD em metadata do compositor."""
    return {
        "slot": slot,
        "bbox": layer.bbox,
        "kind": layer.kind,
        "opacity": layer.opacity,
        "layer_ref": layer,
        "text": layer.text,
        "tracking": _extrair_tracking(layer),
        "cor_rgb": _amostrar_cor(layer),
    }


def compor_base(psd, variaveis):
    """Oculta as camadas variáveis (só em memória — o PSD em disco não é tocado)
    e retorna a composição resultante como PIL.Image RGBA."""
    for meta in variaveis.values():
        meta["layer_ref"].visible = False
    return psd.composite().convert("RGBA")


def extrair_mascara_camada(layer):
    """Máscara de `layer`, alinhada e recortada ao bbox DA CAMADA — não ao
    bbox da própria máscara, que pode ser maior/deslocado em relação ao
    pixel data da camada (ex.: em `foto_artista` a máscara vai de x=55 a
    x=1080, mas o bbox da camada é x=172 a x=1003; sem realinhar, a máscara
    sairia deslocada ~117px pra esquerda do que devia).

    Retorna PIL "L" do tamanho do bbox da camada, ou None se não tiver máscara.
    """
    if layer.mask is None:
        return None

    lx1, ly1, lx2, ly2 = layer.bbox
    largura, altura = lx2 - lx1, ly2 - ly1
    fundo = Image.new("L", (largura, altura), layer.mask.background_color)

    mx1, my1, mx2, my2 = layer.mask.bbox
    if mx2 > mx1 and my2 > my1:
        fundo.paste(layer.mask.topil(), (mx1 - lx1, my1 - ly1))
    return fundo


def compor_com_foto_nova(psd, variaveis, foto_rgba):
    """Insere `foto_rgba` (PIL RGBA, mesmo tamanho do bbox de `foto_artista`,
    com a máscara de fusão já aplicada como canal alpha) como uma camada de
    pixel de verdade, na MESMA posição da pilha que a camada original oculta,
    e retorna o composite (RGBA) resultante — fundo + fixos + foto nova, com
    todo adjustment layer, grain e blend mode aplicado pelo motor de
    composição real do psd-tools.

    Histórico (HANDOFF_v4 §1): a primeira tentativa reimplementava os
    adjustment layers (Brilho/Contraste, Exposição) e o overlay "acima" via
    numpy, isolando camadas com `psd.composite()` e recompondo manualmente.
    Isso quebra pra qualquer camada com `blend_mode` diferente de NORMAL —
    nesse PSD, o grain (`textura_grain`, Overlay, opacidade 25%) e uma
    textura de luz (Lighten) ficam ACIMA da foto. Isolar uma camada Overlay
    sem o fundo real embaixo produz uma composição ~38% preta cobrindo tudo
    (o motor de blend não tem contra o que misturar), escurecendo a foto
    bem mais que o correto — testado e confirmado nesta sessão (round-trip
    SSIM caiu pra 0.77 com a abordagem numérica, contra 0.96+ com esta).
    Inserir a foto como camada de verdade elimina o problema inteiro: o
    psd-tools sempre compõe com o fundo real presente, então todo blend
    mode funciona exatamente como no Photoshop.

    As 6 camadas de texto continuam ocultas — são desenhadas depois, por
    cima do resultado, com `compositor.desenhar_texto` (Pillow, inalterado).
    """
    foto_layer = variaveis["foto_artista"]["layer_ref"]
    x1, y1, _, _ = variaveis["foto_artista"]["bbox"]
    idx_original = foto_layer.parent.index(foto_layer)

    visibilidade_original = {}
    for slot, meta in variaveis.items():
        layer = meta["layer_ref"]
        visibilidade_original[layer] = layer.visible
        if slot != "foto_artista":
            layer.visible = False

    nova = PixelLayer.frompil(foto_rgba, psd, name="__foto_nova_temp__", top=y1, left=x1)
    parent = nova.parent
    parent.remove(nova)
    parent.insert(idx_original, nova)
    foto_layer.visible = False

    try:
        return psd.composite().convert("RGBA")
    finally:
        parent.remove(nova)
        for layer, vis in visibilidade_original.items():
            layer.visible = vis
