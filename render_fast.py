#!/usr/bin/env python
"""Preview aproximado sem abrir PSD. Não substitui a renderização final."""
import argparse
import json
import os
import time

from PIL import Image, ImageDraw, ImageEnhance

from fbs import ajustes as ajustes_mod
from fbs import compositor, config, util
from preparar_cache_preview import BASE_PATH, MASCARA_PATH, SLOTS_PATH, preparar_cache


def _ajuste(ajustes, slot):
    return dict(ajustes_mod.ajuste_do_slot(ajustes, "feed", slot))


def _desenhar_fixos(canvas, job, dados):
    draw = ImageDraw.Draw(canvas)
    entrada_x, entrada_y, _, _ = dados["fixos"]["entrada_bbox"]
    fonte_entrada = util.carregar_fonte("archivo_black", 27)
    draw.text((entrada_x, entrada_y), "ENTRADA", font=fonte_entrada, fill=(215, 190, 157, 255))
    draw.text((entrada_x, entrada_y + 29), "GRATUITA", font=fonte_entrada, fill=(215, 190, 157, 255))

    banda_x, banda_y, _, _ = dados["fixos"]["banda_bbox"]
    fonte_banda = util.carregar_fonte("archivo", 24)
    draw.text((banda_x, banda_y + 5), "COM: ", font=fonte_banda, fill=(232, 222, 210, 255))
    prefixo = draw.textlength("COM: ", font=fonte_banda)
    util.desenhar_texto_iniciais(
        draw, (banda_x + prefixo, banda_y + 5), job["banda_ancora"].title(),
        fonte_banda, (215, 0, 26, 255), (232, 222, 210, 255),
    )
    draw.text((banda_x, banda_y + 39), "+ JAM SESSION COM CONVIDADOS",
              font=util.carregar_fonte("mono", 18), fill=(232, 222, 210, 255))


def gerar_fast(job, ajustes):
    preparar_cache(force=False)
    with open(SLOTS_PATH, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    canvas = Image.open(BASE_PATH).convert("RGBA")

    x1, y1, x2, y2 = dados["foto_bbox"]
    largura, altura = x2 - x1, y2 - y1
    foto = Image.open(job["_foto_path"]).convert("RGB")
    foto = util.fit_cover(foto, largura, altura, foco=job["foco"])
    ajuste_foto = _ajuste(ajustes, "foto_artista")
    foto = compositor.ajustar_foto(foto, ajuste_foto)
    mascara = Image.open(MASCARA_PATH).convert("L")
    mascara = compositor.ajustar_mascara_foto(mascara, ajuste_foto)
    foto_rgba = foto.convert("RGBA")
    foto_rgba.putalpha(mascara)
    canvas.alpha_composite(foto_rgba, (x1, y1))

    _desenhar_fixos(canvas, job, dados)

    data = job["_data_ptbr"]
    valores = {
        "txt_artista": job["artista"].upper(),
        "txt_edicao": f"CONVIDA #{job['edicao']}",
        "txt_data_mes": data["mes"],
        "txt_data_dia": data["dia"],
        "txt_data_semana": data["semana"],
        "txt_data_hora": job["hora"],
        "txt_local_nome": job["local_nome"],
        "txt_local_bairro": job["local_bairro"],
        "txt_local_endereco": job["local_endereco"].replace("—", "-"),
    }
    for slot, texto in valores.items():
        meta = dados["slots"][slot]
        ajuste_slot = _ajuste(ajustes, slot)
        ajuste_slot["_preview_fast"] = True
        if slot in {"txt_data_mes", "txt_data_dia", "txt_data_semana", "txt_data_hora"}:
            ajuste_slot.update({
                "caixa_x": 897, "caixa_largura": 142, "alinhamento": "centro",
                "offset_x": 0, "ajustar_tracking": True, "preenchimento_largura": .92,
            })
        compositor.desenhar_texto(canvas, meta, texto, ajuste=ajuste_slot)

    ajuste_linhas = _ajuste(ajustes, "linhas_rodape")
    draw = ImageDraw.Draw(canvas)
    cor = ajuste_linhas.get("cor", "#C97816")
    ox, oy = ajuste_linhas.get("offset_x", 0), ajuste_linhas.get("offset_y", 0)
    espessura = int(ajuste_linhas.get("espessura", 2))
    for indice, (rx1, ry1, rx2, _ry2) in enumerate(dados["fixos"]["linhas"], 1):
        largura_linha = ajuste_linhas.get(f"largura_{indice}", rx2 - rx1)
        draw.rectangle((rx1 + ox, ry1 + oy, rx1 + ox + largura_linha,
                        ry1 + oy + espessura - 1), fill=cor)

    global_cfg = _ajuste(ajustes, "global")
    resultado = canvas.convert("RGB")
    # O base cacheado já contém textura/grain do PSD. No preview rápido,
    # recalcular overlays full-canvas custaria mais que todos os textos juntos.
    resultado = ImageEnhance.Brightness(resultado).enhance(float(global_cfg.get("brilho", 1)))
    resultado = ImageEnhance.Contrast(resultado).enhance(float(global_cfg.get("contraste", 1)))
    return ImageEnhance.Color(resultado).enhance(float(global_cfg.get("saturacao", 1)))


def main():
    parser = argparse.ArgumentParser(description="Render rápido FBS sem PSD")
    parser.add_argument("--job", default=os.path.join("jobs", "job.json"))
    parser.add_argument("--ajustes", default="ajustes.editor.tmp.json")
    parser.add_argument("--out", default=os.path.join("outputs", "_fast_preview.png"))
    args = parser.parse_args()
    os.chdir(config.ROOT)
    inicio = time.perf_counter()
    with open(args.job, "r", encoding="utf-8") as arquivo:
        job = util.validar_job(json.load(arquivo))
    ajustes = ajustes_mod.carregar_ajustes(args.ajustes)
    imagem = gerar_fast(job, ajustes)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    imagem.save(args.out)
    print(f"Preview rápido: {args.out} ({time.perf_counter() - inicio:.3f}s)")


if __name__ == "__main__":
    main()
