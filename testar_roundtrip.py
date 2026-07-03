#!/usr/bin/env python
"""Teste de round-trip (HANDOFF_v4 §3): extrai a foto original do PSD, gera a
arte de novo com ela, e compara com a composição de referência
(outputs/_debug_original_com_variaveis.png). Se o pipeline reproduz o PSD
com fidelidade, qualquer foto/dado novo herda a mesma fidelidade por
construção.

O critério mede a região da foto EXCLUINDO onde texto variável (GONZALO
ARAYA, JUL/07/TERÇA/19:00 etc.) se sobrepõe a ela — o texto novo é
renderizado pelo Pillow, não pelo motor nativo do Photoshop, então diverge
da referência por um motivo completamente à parte da fidelidade fotográfica
que este teste quer isolar (Workstream A do HANDOFF_v4; fidelidade de texto
é escopo do BRIEF_v3, já resolvido separadamente). O SSIM/diff do canvas
inteiro (contaminado pelo texto) é só informativo.

Critério: SSIM >= 0.93 na região foto-sem-texto + diff médio absoluto < 6/255
por canal na mesma região.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from PIL import Image
from psd_tools import PSDImage
from skimage.metrics import structural_similarity

from fbs import ajustes as ajustes_mod
from fbs import config, psd_reader, util
from gerar import gerar_formato

REFERENCIA = os.path.join(config.OUTPUTS_DIR, "_debug_original_com_variaveis.png")
FOTO_ROUNDTRIP = os.path.join(config.ROOT, "fotos", "_roundtrip_gonzalo.png")
SSIM_MINIMO = 0.93
DIFF_MEDIO_MAXIMO = 6.0


def _mascara_foto_sem_texto(variaveis, tamanho):
    """Booleano HxW: True dentro do bbox da foto E fora do bbox de qualquer
    slot de texto (esses se sobrepõem espacialmente à foto — GONZALO ARAYA e
    JUL/07/TERÇA/19:00 desenham por cima dela)."""
    w, h = tamanho
    mask = np.zeros((h, w), dtype=bool)
    x1, y1, x2, y2 = variaveis["foto_artista"]["bbox"]
    mask[y1:y2, x1:x2] = True
    for slot, meta in variaveis.items():
        if slot == "foto_artista":
            continue
        tx1, ty1, tx2, ty2 = meta["bbox"]
        mask[ty1:ty2, tx1:tx2] = False
    return mask


def main():
    if not os.path.isfile(REFERENCIA):
        print(f"ERRO: referência não encontrada: {REFERENCIA}", file=sys.stderr)
        sys.exit(1)

    logger = util.configurar_log()

    print("1. Extraindo foto original do PSD (foto_artista.topil())...")
    psd = PSDImage.open(config.TEMPLATE_FILES["feed"])
    variaveis = psd_reader.extrair_variaveis(psd)
    foto_layer = variaveis["foto_artista"]["layer_ref"]
    foto_original = foto_layer.topil().convert("RGB")
    os.makedirs(os.path.dirname(FOTO_ROUNDTRIP), exist_ok=True)
    foto_original.save(FOTO_ROUNDTRIP)
    print(f"   salva em {FOTO_ROUNDTRIP} ({foto_original.size})")

    print("2. Gerando arte com a foto extraída (job round-trip)...")
    job_bruto = {
        "edicao": 28,
        "artista": "GONZALO ARAYA",
        "data": "2026-07-07",
        "hora": "19:00",
        "foto": FOTO_ROUNDTRIP,
        "formatos": ["feed"],
    }
    job = util.validar_job(job_bruto)
    ajustes = ajustes_mod.carregar_ajustes()
    resultado = gerar_formato(job, "feed", logger, ajustes).convert("RGB")
    caminho_saida = os.path.join(config.OUTPUTS_DIR, "_roundtrip_resultado.png")
    resultado.save(caminho_saida)
    print(f"   salvo em {caminho_saida}")

    print("3. Comparando com a referência (região da foto, sem sobreposição de texto)...")
    ref = Image.open(REFERENCIA).convert("RGB")
    if ref.size != resultado.size:
        print(f"ERRO: tamanhos diferentes — ref={ref.size} resultado={resultado.size}", file=sys.stderr)
        sys.exit(1)

    arr_ref = np.array(ref).astype(np.float64)
    arr_novo = np.array(resultado).astype(np.float64)

    ssim_total, diff_map = structural_similarity(
        arr_ref, arr_novo, channel_axis=2, data_range=255, full=True
    )
    print(f"   SSIM canvas inteiro (informativo, contaminado por texto): {ssim_total:.4f}")

    mask = _mascara_foto_sem_texto(variaveis, ref.size)
    diff_pixel_medio_por_canal = np.abs(arr_ref - arr_novo).mean(axis=2)
    diff_medio = diff_pixel_medio_por_canal[mask].mean()
    ssim_regiao = diff_map.mean(axis=2)[mask].mean()
    print(f"   SSIM região foto (sem texto): {ssim_regiao:.4f}  (mínimo exigido: {SSIM_MINIMO})")
    print(f"   diff médio abs região foto (sem texto): {diff_medio:.2f}/255  (máximo aceito: {DIFF_MEDIO_MAXIMO})")

    print("4. Gerando heatmap de diff...")
    diff_norm = diff_pixel_medio_por_canal.copy()
    diff_norm[~mask] *= 0.3  # esmaece fora da região avaliada, mas mantém visível pra contexto
    maximo = diff_norm.max() if diff_norm.max() > 0 else 1.0
    heatmap = (np.clip(diff_norm / maximo, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(heatmap).save(os.path.join(config.OUTPUTS_DIR, "_diff_roundtrip.png"))
    print(f"   salvo em {os.path.join(config.OUTPUTS_DIR, '_diff_roundtrip.png')}")

    print()
    ok_ssim = ssim_regiao >= SSIM_MINIMO
    ok_diff = diff_medio < DIFF_MEDIO_MAXIMO
    if ok_ssim and ok_diff:
        print("PASSOU — round-trip dentro dos critérios do HANDOFF_v4 §3 (região da foto).")
        sys.exit(0)
    else:
        print("NÃO PASSOU:")
        if not ok_ssim:
            print(f"  - SSIM {ssim_regiao:.4f} < {SSIM_MINIMO}")
        if not ok_diff:
            print(f"  - diff médio {diff_medio:.2f} >= {DIFF_MEDIO_MAXIMO}")
        sys.exit(1)


if __name__ == "__main__":
    main()
