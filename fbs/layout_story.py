"""STORY — 1080x1920 (ver seção 6.2 do brief + HANDOFF v2 refinamento)."""
import os
from PIL import Image, ImageDraw

from . import config, util, tratamento, camadas

W, H = config.DIMENSOES["story"]
MARGEM = 60


def gerar(job: dict) -> Image.Image:
    paleta = util.carregar_paleta()
    dp = job["_data_ptbr"]

    canvas = camadas.fundo_solido(W, H, paleta["INK"])
    canvas = camadas.aplicar_textura_bordas(canvas)
    canvas = camadas.aplicar_vinheta_radial(canvas, paleta["INK"], forca=0.5)

    # --- foto: 60% inferior do canvas, fundida no topo com o fundo
    foto_y0 = int(H * 0.40)
    foto_w, foto_h = W, H - foto_y0
    foto_orig = Image.open(job["_foto_path"])
    foto_cover = util.fit_cover(foto_orig, foto_w, foto_h, foco=job["foco"])
    foto_tratada = tratamento.tratar_foto(foto_cover, paleta, bordas_fusao=("topo",), largura_frac=0.15)
    canvas = camadas.colar_foto(canvas, foto_tratada, (0, foto_y0))

    # --- bokeh no espaço vazio atrás do nome
    canvas = camadas.colar_bokeh(canvas, (0, int(H * 0.20), W, foto_y0), opacidade=0.28)

    draw = ImageDraw.Draw(canvas)

    # --- logo topo-esq (por altura — a arte é quadrada)
    logo = Image.open(os.path.join(config.ASSETS, "logo_bs.png")).convert("RGBA")
    logo_r = util.redimensionar_logo_por_altura(logo, 96)
    canvas.paste(logo_r, (MARGEM, MARGEM), logo_r)
    logo_h = logo_r.height

    # --- bloco data topo-dir: MES / DIA (texturizado, mesmo tamanho) · TERÇA HH:MM · ENTRADA GRATUITA
    fonte_mesdia = util.carregar_fonte("anton", 86)
    fonte_mono = util.carregar_fonte("mono", 28)
    fonte_gratis = util.carregar_fonte("mono", 24)

    y = MARGEM
    for linha_data in (dp["mes"], dp["dia"]):
        bbox = draw.textbbox((0, 0), linha_data, font=fonte_mesdia)
        tw = bbox[2] - bbox[0]
        canvas = tratamento.texturizar_texto(
            canvas, linha_data, fonte_mesdia, (W - MARGEM - tw, y - bbox[1]), paleta["CREAM"],
        )
        draw = ImageDraw.Draw(canvas)
        y += (bbox[3] - bbox[1]) * 1.08

    y += 10
    txt_dia_hora = f"{dp['semana']} {job['hora']}"
    bbox = draw.textbbox((0, 0), txt_dia_hora, font=fonte_mono)
    draw.text((W - MARGEM - (bbox[2] - bbox[0]), y), txt_dia_hora, font=fonte_mono, fill=paleta["BS_AMBER"])
    y += (bbox[3] - bbox[1]) + 14

    txt_gratis = "ENTRADA GRATUITA"
    bbox = draw.textbbox((0, 0), txt_gratis, font=fonte_gratis)
    draw.text((W - MARGEM - (bbox[2] - bbox[0]), y), txt_gratis, font=fonte_gratis, fill=paleta["CREAM"])
    data_bottom_y = y + (bbox[3] - bbox[1])

    # --- CONVIDA #N com estrela, alinhado a esquerda na mesma faixa do topo
    y_convida = MARGEM + logo_h + 26
    util.desenhar_estrela(draw, MARGEM + 8, y_convida + 14, 9, paleta["BS_AMBER"])
    draw.text((MARGEM + 28, y_convida), f"CONVIDA #{job['edicao']}", font=fonte_mono, fill=paleta["BS_AMBER"])

    # --- nome do artista, Anton gigante texturizado, até 3 linhas, alinhado esq
    # (nome_y0 respeita o mais baixo entre CONVIDA e o bloco de data, pra não colidir com nenhum dos dois)
    nome_y0 = max(y_convida + 60, data_bottom_y + 40)
    nome_largura_max = W - 2 * MARGEM
    nome_altura_max = foto_y0 - nome_y0 - 20
    fonte_nome, linhas_nome, _ = util.fit_text(
        draw, job["artista"], config.FONTES["anton"], tamanho_max=140,
        largura_max=nome_largura_max, altura_max=nome_altura_max, max_linhas=3,
    )
    bbox_ref = draw.textbbox((0, 0), "Ãg", font=fonte_nome)
    altura_linha = (bbox_ref[3] - bbox_ref[1]) * 1.15
    yy = nome_y0
    for linha in linhas_nome:
        canvas = tratamento.texturizar_texto(canvas, linha, fonte_nome, (MARGEM, yy - bbox_ref[1]), paleta["CREAM"])
        yy += altura_linha
    draw = ImageDraw.Draw(canvas)

    yy += 10
    fonte_archivo = util.carregar_fonte("archivo", 30)
    draw.text((MARGEM, yy), "com: ", font=fonte_archivo, fill=paleta["CREAM"])
    bbox = draw.textbbox((0, 0), "com: ", font=fonte_archivo)
    util.desenhar_texto_iniciais(
        draw, (MARGEM + (bbox[2] - bbox[0]), yy), job["banda_ancora"].title(),
        fonte_archivo, paleta["BS_RED"], paleta["CREAM"],
    )

    # --- rodapé compacto: hairline + local/bairro + endereço (sem barra de pipes)
    y_base = H - 130
    camadas.hairline(draw, (MARGEM, y_base, W - MARGEM, y_base + 1), paleta["BS_AMBER"])

    fonte_local = util.carregar_fonte("mono", 30)
    txt_local = f"{job['local_nome']} — {job['local_bairro']}"
    draw.text((MARGEM, y_base + 24), txt_local, font=fonte_local, fill=paleta["CREAM"])

    fonte_end = util.carregar_fonte("mono", 22)
    draw.text((MARGEM, y_base + 62), job["local_endereco"], font=fonte_end, fill=paleta["WARM_GRAY"])

    canvas = camadas.aplicar_grain(canvas)
    return canvas
