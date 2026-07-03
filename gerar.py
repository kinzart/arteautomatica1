#!/usr/bin/env python
"""Gerador de artes FBS — jobs/job.json -> outputs/fbs{N}_{feed,story,sympla}.png

PSD-driven (BRIEF_v3): o PSD em assets/templates/ é a fonte de verdade — este
script só oculta as 7 camadas variáveis, recompõe a base e redesenha texto e
foto novos por cima, herdando fonte/cor/tracking do PSD original.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageEnhance
from psd_tools import PSDImage

from fbs import ajustes as ajustes_mod
from fbs import camadas, compositor, config, face, psd_reader, util


def _valores_texto(job):
    d = job["_data_ptbr"]
    return {
        "txt_artista": job["artista"],
        "txt_edicao": f"CONVIDA #{job['edicao']}",
        "txt_data_mes": d["mes"],
        "txt_data_dia": d["dia"],
        "txt_data_semana": d["semana"],
        "txt_data_hora": job["hora"],
    }


def gerar_formato(job, formato, logger, ajustes):
    psd = PSDImage.open(config.TEMPLATE_FILES[formato])
    variaveis = psd_reader.extrair_variaveis(psd)

    # Rodapé agora é variável: coleta geometria do PSD e oculta as camadas
    # originais somente em memória, antes da composição.
    grupo_endereco = next((l for l in psd.descendants() if l.is_group() and l.name == "ENDERECO"), None)
    grupo_linhas = next((l for l in psd.descendants() if l.is_group() and l.name == "LINHAS"), None)
    rodape_meta = {}
    if grupo_endereco:
        textos = [l for l in grupo_endereco if l.kind == "type"]
        titulo_esq = next(l for l in textos if "GETHER" in l.name.upper())
        titulo_dir = next(l for l in textos if "MORRO" in l.name.upper())
        endereco = next(l for l in textos if l not in (titulo_esq, titulo_dir))
        for slot, layer in (("txt_local_nome", titulo_esq), ("txt_local_bairro", titulo_dir), ("txt_local_endereco", endereco)):
            rodape_meta[slot] = psd_reader.meta_texto(layer, slot)
            layer.visible = False
    linhas_meta = []
    if grupo_linhas:
        for layer in grupo_linhas:
            linhas_meta.append(tuple(layer.bbox))
            layer.visible = False

    x1, y1, x2, y2 = variaveis["foto_artista"]["bbox"]
    largura, altura = x2 - x1, y2 - y1
    foto_layer = variaveis["foto_artista"]["layer_ref"]
    mascara_real_foto = psd_reader.extrair_mascara_camada(foto_layer)

    # enquadramento "auto" (default, HANDOFF_v4 §2): posiciona a foto nova
    # pelo rosto detectado, alinhado à âncora calibrada do template. Sem
    # âncora ou sem rosto detectável na foto nova, cai no fit_cover comum
    # (preparar_foto_rgba já faz isso sozinho quando foto_posicionada=None).
    foto_posicionada = None
    if job.get("enquadramento", "auto") == "auto":
        ancora = face.calibrar_se_necessario(formato, logger=logger)
        if ancora is not None:
            foto_bruta = Image.open(job["_foto_path"]).convert("RGB")
            foto_posicionada = face.posicionar_por_rosto(
                foto_bruta, largura, altura, ancora, foco_fallback=job["foco"], log=logger,
            )

    ajuste_foto = ajustes_mod.ajuste_do_slot(ajustes, formato, "foto_artista")
    if foto_posicionada is None:
        foto_bruta = Image.open(job["_foto_path"]).convert("RGB")
        foto_posicionada = util.fit_cover(foto_bruta, largura, altura, foco=job["foco"])
    foto_posicionada = compositor.ajustar_foto(foto_posicionada, ajuste_foto)
    foto_rgba = compositor.preparar_foto_rgba(
        job["_foto_path"], largura, altura,
        foco=job["foco"],
        mascara=mascara_real_foto,
        fusao_lado=config.FUSAO_LADO_POR_FORMATO[formato],
        fusao_frac=ajuste_foto.get("fusao_frac", 0.15),
        foto_posicionada=foto_posicionada,
    )

    # insere a foto nova como camada de verdade na pilha do PSD (não um
    # paste por cima) — deixa o psd-tools recompor adjustment layers, grain
    # e blend modes corretamente (ver psd_reader.compor_com_foto_nova).
    base = psd_reader.compor_com_foto_nova(psd, variaveis, foto_rgba)

    for slot, texto in _valores_texto(job).items():
        ajuste_slot = ajustes_mod.ajuste_do_slot(ajustes, formato, slot)
        compositor.desenhar_texto(base, variaveis[slot], texto, ajuste=ajuste_slot, log=logger)

    valores_rodape = {
        "txt_local_nome": job["local_nome"],
        "txt_local_bairro": job["local_bairro"],
        "txt_local_endereco": job["local_endereco"].replace("—", "-"),
    }
    for slot, texto in valores_rodape.items():
        compositor.desenhar_texto(base, rodape_meta[slot], texto,
                                  ajuste=ajustes_mod.ajuste_do_slot(ajustes, formato, slot), log=logger)

    ajuste_linhas = ajustes_mod.ajuste_do_slot(ajustes, formato, "linhas_rodape")
    draw = ImageDraw.Draw(base)
    cor_linha = ajuste_linhas.get("cor", "#C97816")
    ox, oy = ajuste_linhas.get("offset_x", 0), ajuste_linhas.get("offset_y", 0)
    espessura = int(ajuste_linhas.get("espessura", 2))
    for i, (lx1, ly1, lx2, _ly2) in enumerate(linhas_meta):
        largura = ajuste_linhas.get(f"largura_{i + 1}", lx2 - lx1)
        draw.rectangle((lx1 + ox, ly1 + oy, lx1 + ox + largura, ly1 + oy + espessura - 1), fill=cor_linha)

    ajuste_global = ajustes_mod.ajuste_do_slot(ajustes, formato, "global")
    resultado = base.convert("RGB")
    if ajuste_global.get("bordas_opacidade", 0):
        resultado = camadas.aplicar_textura_bordas(resultado, ajuste_global["bordas_opacidade"])
    if ajuste_global.get("grain_opacidade", 0):
        resultado = camadas.aplicar_grain(resultado, ajuste_global["grain_opacidade"])
    resultado = ImageEnhance.Brightness(resultado).enhance(float(ajuste_global.get("brilho", 1)))
    resultado = ImageEnhance.Contrast(resultado).enhance(float(ajuste_global.get("contraste", 1)))
    resultado = ImageEnhance.Color(resultado).enhance(float(ajuste_global.get("saturacao", 1)))

    return resultado


def main():
    parser = argparse.ArgumentParser(description="Gerador de artes FBS (PSD-driven)")
    parser.add_argument("--job", default=os.path.join("jobs", "job.json"),
                         help="caminho do job.json (default: jobs/job.json)")
    args = parser.parse_args()

    logger = util.configurar_log()
    job_path = args.job

    edicao_txt = "?"
    artista_txt = "?"
    try:
        util.validar_assets()

        if not os.path.isfile(job_path):
            raise util.JobError(f"arquivo de job não encontrado: {job_path}")
        with open(job_path, "r", encoding="utf-8") as f:
            job_bruto = json.load(f)

        edicao_txt = job_bruto.get("edicao", "?")
        artista_txt = job_bruto.get("artista", "?")

        job = util.validar_job(job_bruto)
        edicao_txt = job["edicao"]
        artista_txt = job["artista"]

        os.makedirs(config.OUTPUTS_DIR, exist_ok=True)
        ajustes = ajustes_mod.carregar_ajustes()

        resultados = {}
        tempos = {}
        for formato in job["formatos"]:
            t0 = time.time()
            resultados[formato] = gerar_formato(job, formato, logger, ajustes)
            tempos[formato] = time.time() - t0

        caminhos = {}
        for formato, img in resultados.items():
            # psd.composite() embute um perfil ICC (apply_icc=True por padrão)
            # cujos bytes variam a cada geração (timestamp interno da lib de
            # color management) mesmo com os pixels 100% idênticos — sem
            # remover, o PNG final não é byte-a-byte determinístico.
            img.info.pop("icc_profile", None)
            caminho = os.path.join(config.OUTPUTS_DIR, f"fbs{job['edicao']}_{formato}.png")
            img.save(caminho)
            caminhos[formato] = caminho

        resumo = " ".join(f"{fmt}({tempos[fmt]:.1f}s)" for fmt in job["formatos"])
        logger.info(f'JOB edicao={job["edicao"]} artista="{job["artista"]}" OK {resumo}')

        print(f"OK — edição {job['edicao']} ({job['artista']}):")
        for formato, caminho in caminhos.items():
            print(f"  {caminho}")

    except util.JobError as e:
        logger.info(f'JOB edicao={edicao_txt} artista="{artista_txt}" ERRO {e}')
        print(f"ERRO: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.info(f'JOB edicao={edicao_txt} artista="{artista_txt}" ERRO inesperado: {e}')
        print(f"ERRO inesperado: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
