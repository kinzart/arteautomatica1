"""FEED — 1080x1350 (ver seção 6.1 do brief + HANDOFF v2 refinamento)."""
import os
from PIL import Image, ImageDraw

from . import config, util, tratamento, camadas

W, H = config.DIMENSOES["feed"]
MARGEM = 64


def gerar(job: dict) -> Image.Image:
    paleta = util.carregar_paleta()
    dp = job["_data_ptbr"]

    canvas = camadas.fundo_solido(W, H, paleta["INK"])
    canvas = camadas.aplicar_textura_bordas(canvas)
    canvas = camadas.aplicar_vinheta_radial(canvas, paleta["INK"], forca=0.5)

    # --- foto: metade direita/inferior, fundida com o fundo (esquerda + base)
    foto_x0, foto_y0 = int(W * 0.47), int(H * 0.28)
    foto_x1, foto_y1 = W, int(H * 0.935)
    foto_w, foto_h = foto_x1 - foto_x0, foto_y1 - foto_y0
    foto_orig = Image.open(job["_foto_path"])
    foto_cover = util.fit_cover(foto_orig, foto_w, foto_h, foco=job["foco"])
    foto_tratada = tratamento.tratar_foto(foto_cover, paleta, bordas_fusao=("esq", "baixo"), largura_frac=0.15)
    canvas = camadas.colar_foto(canvas, foto_tratada, (foto_x0, foto_y0))

    # --- bokeh no espaço vazio atrás do nome (canto sup-esq/centro)
    canvas = camadas.colar_bokeh(canvas, (0, int(H * 0.20), foto_x0 + 120, int(H * 0.62)), opacidade=0.28)

    draw = ImageDraw.Draw(canvas)

    # --- logo (redimensionada por altura — a arte é quadrada, não retangular)
    logo = Image.open(os.path.join(config.ASSETS, "logo_bs.png")).convert("RGBA")
    logo_r = util.redimensionar_logo_por_altura(logo, 90)
    canvas.paste(logo_r, (MARGEM, MARGEM), logo_r)

    # --- bloco de data empilhado, alinhado à direita: MES / DIA · TERÇA HH:MM · ENTRADA GRATUITA
    fonte_mesdia = util.carregar_fonte("anton", 76)
    fonte_diahora = util.carregar_fonte("mono", 28)
    fonte_gratis = util.carregar_fonte("mono", 20)

    y = MARGEM
    for linha_data in (dp["mes"], dp["dia"]):
        bbox = draw.textbbox((0, 0), linha_data, font=fonte_mesdia)
        tw = bbox[2] - bbox[0]
        canvas = tratamento.texturizar_texto(
            canvas, linha_data, fonte_mesdia, (W - MARGEM - tw, y - bbox[1]), paleta["CREAM"],
        )
        draw = ImageDraw.Draw(canvas)
        y += (bbox[3] - bbox[1]) * 1.05

    y += 8
    txt_dia_hora = f"{dp['semana']} {job['hora']}"
    bbox = draw.textbbox((0, 0), txt_dia_hora, font=fonte_diahora)
    draw.text((W - MARGEM - (bbox[2] - bbox[0]), y), txt_dia_hora, font=fonte_diahora, fill=paleta["BS_AMBER"])
    y += (bbox[3] - bbox[1]) + 12

    txt_gratis = "ENTRADA GRATUITA"
    bbox = draw.textbbox((0, 0), txt_gratis, font=fonte_gratis)
    draw.text((W - MARGEM - (bbox[2] - bbox[0]), y), txt_gratis, font=fonte_gratis, fill=paleta["CREAM"])

    # --- CONVIDA #N com estrela, logo abaixo da logo
    y_convida = MARGEM + 90 + 22
    fonte_mono = util.carregar_fonte("mono", 30)
    txt_convida = f"CONVIDA #{job['edicao']}"
    util.desenhar_estrela(draw, MARGEM + 8, y_convida + 14, 8, paleta["BS_AMBER"])
    draw.text((MARGEM + 26, y_convida), txt_convida, font=fonte_mono, fill=paleta["BS_AMBER"])

    # --- centro: nome do artista gigante (texturizado) + chamadas
    nome_y0 = int(H * 0.30)
    nome_largura_max = foto_x0 - MARGEM - 24
    nome_altura_max = int(H * 0.34)
    fonte_nome, linhas_nome, _ = util.fit_text(
        draw, job["artista"], config.FONTES["anton"], tamanho_max=120,
        largura_max=nome_largura_max, altura_max=nome_altura_max, max_linhas=3,
    )
    bbox_ref = draw.textbbox((0, 0), "Ãg", font=fonte_nome)
    altura_linha = (bbox_ref[3] - bbox_ref[1]) * 1.15
    y = nome_y0
    for linha in linhas_nome:
        canvas = tratamento.texturizar_texto(canvas, linha, fonte_nome, (MARGEM, y - bbox_ref[1]), paleta["CREAM"])
        y += altura_linha
    draw = ImageDraw.Draw(canvas)

    y += 14
    fonte_archivo = util.carregar_fonte("archivo", 32)
    draw.text((MARGEM, y), "com: ", font=fonte_archivo, fill=paleta["CREAM"])
    bbox = draw.textbbox((0, 0), "com: ", font=fonte_archivo)
    util.desenhar_texto_iniciais(
        draw, (MARGEM + (bbox[2] - bbox[0]), y), job["banda_ancora"].title(),
        fonte_archivo, paleta["BS_RED"], paleta["CREAM"],
    )
    y += 46

    fonte_archivo_black = util.carregar_fonte("archivo_black", 30)
    draw.text((MARGEM, y), "+ JAM SESSION COM CONVIDADOS", font=fonte_archivo_black, fill=paleta["BS_AMBER"])

    # --- base: hairline + barra de pipes + linha institucional + endereço
    y_base = int(H * 0.75)
    camadas.hairline(draw, (MARGEM, y_base, W - MARGEM, y_base + 1), paleta["BS_AMBER"])

    itens = [job["local_nome"], job["local_bairro"], job["local_frequencia"], job["hora"], job["local_cidade"]]
    fonte_barra = util.fonte_pipes_ajustada(draw, itens, "mono", tamanho_max=26, largura_max=W - 2 * MARGEM)
    util.desenhar_texto_pipes(draw, (MARGEM, y_base + 26), itens, fonte_barra, paleta["CREAM"], paleta["BS_AMBER"])

    fonte_tag = util.carregar_fonte("mono", 22)
    util.desenhar_texto_com_estrelas(draw, W / 2, y_base + 66, job["tagline"], fonte_tag, paleta["CREAM"], paleta["BS_AMBER"])

    fonte_end = util.carregar_fonte("mono", 20)
    txt_end = job["local_endereco"]
    bbox = draw.textbbox((0, 0), txt_end, font=fonte_end)
    draw.text(((W - (bbox[2] - bbox[0])) / 2, y_base + 98), txt_end, font=fonte_end, fill=paleta["WARM_GRAY"])

    canvas = camadas.aplicar_grain(canvas)
    return canvas
