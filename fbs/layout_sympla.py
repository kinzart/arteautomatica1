"""SYMPLA — 1920x1080 (ver seção 6.3 do brief + HANDOFF v2 refinamento)."""
import os
from PIL import Image, ImageDraw

from . import config, util, tratamento, camadas

W, H = config.DIMENSOES["sympla"]
MARGEM = 70
LOGO_Y = 96


def gerar(job: dict) -> Image.Image:
    paleta = util.carregar_paleta()
    dp = job["_data_ptbr"]

    canvas = camadas.fundo_solido(W, H, paleta["INK"])
    canvas = camadas.aplicar_textura_bordas(canvas)
    canvas = camadas.aplicar_vinheta_radial(canvas, paleta["INK"], forca=0.5)

    # --- foto: metade direita, fundida com o fundo na borda esquerda
    foto_x0 = int(W * 0.5)
    foto_w, foto_h = W - foto_x0, H
    foto_orig = Image.open(job["_foto_path"])
    foto_cover = util.fit_cover(foto_orig, foto_w, foto_h, foco=job["foco"])
    foto_tratada = tratamento.tratar_foto(foto_cover, paleta, bordas_fusao=("esq",), largura_frac=0.15)
    canvas = camadas.colar_foto(canvas, foto_tratada, (foto_x0, 0))

    # --- bokeh no espaço vazio atrás do nome (metade esquerda)
    canvas = camadas.colar_bokeh(canvas, (0, int(H * 0.15), foto_x0 + 100, H - 140), opacidade=0.28)

    draw = ImageDraw.Draw(canvas)

    # --- cabeçalho "★ FBS CONVIDA ★" centralizado no topo (só sympla)
    fonte_cabecalho = util.carregar_fonte("mono", 26)
    y_cabecalho = int(H * 0.035)
    largura_cabecalho = util.desenhar_texto_com_estrelas(
        draw, W / 2, y_cabecalho, "FBS CONVIDA", fonte_cabecalho, paleta["CREAM"], paleta["BS_AMBER"],
        star_size=9, gap=18,
    )
    traco_w = int(W * 0.08)
    gap_traco = 30
    x_esq1 = W / 2 - largura_cabecalho / 2 - gap_traco - traco_w
    x_esq0 = x_esq1 - traco_w
    camadas.hairline(draw, (x_esq0, y_cabecalho + 12, x_esq0 + traco_w, y_cabecalho + 13), paleta["BS_AMBER"])
    x_dir0 = W / 2 + largura_cabecalho / 2 + gap_traco
    camadas.hairline(draw, (x_dir0, y_cabecalho + 12, x_dir0 + traco_w, y_cabecalho + 13), paleta["BS_AMBER"])

    # --- logo (por altura) + data empilhada à direita
    logo = Image.open(os.path.join(config.ASSETS, "logo_bs.png")).convert("RGBA")
    logo_r = util.redimensionar_logo_por_altura(logo, 78)
    canvas.paste(logo_r, (MARGEM, LOGO_Y), logo_r)

    fonte_mesdia = util.carregar_fonte("anton", 66)
    fonte_diahora = util.carregar_fonte("mono", 26)
    fonte_gratis = util.carregar_fonte("mono", 18)

    y = LOGO_Y
    for linha_data in (dp["mes"], dp["dia"]):
        bbox = draw.textbbox((0, 0), linha_data, font=fonte_mesdia)
        tw = bbox[2] - bbox[0]
        canvas = tratamento.texturizar_texto(
            canvas, linha_data, fonte_mesdia, (W - MARGEM - tw, y - bbox[1]), paleta["CREAM"],
        )
        draw = ImageDraw.Draw(canvas)
        y += (bbox[3] - bbox[1]) * 1.05

    y += 6
    txt_dia_hora = f"{dp['semana']} {job['hora']}"
    bbox = draw.textbbox((0, 0), txt_dia_hora, font=fonte_diahora)
    draw.text((W - MARGEM - (bbox[2] - bbox[0]), y), txt_dia_hora, font=fonte_diahora, fill=paleta["BS_AMBER"])
    y += (bbox[3] - bbox[1]) + 10

    txt_gratis = "ENTRADA GRATUITA"
    bbox = draw.textbbox((0, 0), txt_gratis, font=fonte_gratis)
    draw.text((W - MARGEM - (bbox[2] - bbox[0]), y), txt_gratis, font=fonte_gratis, fill=paleta["CREAM"])

    # --- CONVIDA #N com estrela, abaixo do logo
    y_convida = LOGO_Y + 78 + 22
    fonte_mono_convida = util.carregar_fonte("mono", 28)
    util.desenhar_estrela(draw, MARGEM + 8, y_convida + 13, 9, paleta["BS_AMBER"])
    draw.text((MARGEM + 28, y_convida), f"CONVIDA #{job['edicao']}", font=fonte_mono_convida, fill=paleta["BS_AMBER"])

    # --- nome do artista, centro-esquerda, Anton texturizado
    nome_largura_max = foto_x0 - MARGEM - 40
    nome_altura_max = int(H * 0.34)
    fonte_nome, linhas_nome, _ = util.fit_text(
        draw, job["artista"], config.FONTES["anton"], tamanho_max=140,
        largura_max=nome_largura_max, altura_max=nome_altura_max, max_linhas=2,
    )
    bbox_ref = draw.textbbox((0, 0), "Ãg", font=fonte_nome)
    altura_linha = (bbox_ref[3] - bbox_ref[1]) * 1.15
    altura_bloco = altura_linha * len(linhas_nome)
    y = (H - altura_bloco) / 2 - 20
    for linha in linhas_nome:
        canvas = tratamento.texturizar_texto(canvas, linha, fonte_nome, (MARGEM, y - bbox_ref[1]), paleta["CREAM"])
        y += altura_linha
    draw = ImageDraw.Draw(canvas)

    y += 16
    fonte_archivo = util.carregar_fonte("archivo", 32)
    draw.text((MARGEM, y), "com: ", font=fonte_archivo, fill=paleta["CREAM"])
    bbox = draw.textbbox((0, 0), "com: ", font=fonte_archivo)
    util.desenhar_texto_iniciais(
        draw, (MARGEM + (bbox[2] - bbox[0]), y), job["banda_ancora"].title(),
        fonte_archivo, paleta["BS_RED"], paleta["CREAM"],
    )

    # --- barra inferior full-width: pipes + linha institucional
    y_base = H - 150
    camadas.hairline(draw, (0, y_base, W, y_base + 1), paleta["BS_AMBER"])

    itens = [job["local_nome"], job["local_bairro"], job["local_frequencia"], job["hora"], job["local_cidade"]]
    fonte_barra = util.fonte_pipes_ajustada(draw, itens, "mono", tamanho_max=30, largura_max=W - 2 * MARGEM)
    util.desenhar_texto_pipes(draw, (MARGEM, y_base + 28), itens, fonte_barra, paleta["CREAM"], paleta["BS_AMBER"])

    fonte_tag = util.carregar_fonte("mono", 24)
    util.desenhar_texto_com_estrelas(draw, W / 2, y_base + 78, job["tagline"], fonte_tag, paleta["CREAM"], paleta["BS_AMBER"])

    canvas = camadas.aplicar_grain(canvas)
    return canvas
