"""Utilitários: data pt-BR, paleta, fontes, estrela vetorial, fit cover, autoshrink."""
import logging
import math
import os
from functools import lru_cache

from PIL import Image, ImageFont

from . import config

MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
DIAS_SEMANA = ["SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO", "DOMINGO"]


def data_ptbr(iso_date: str) -> dict:
    """'2026-07-14' -> {'mes': 'JUL', 'dia': '14', 'semana': 'TERÇA'}"""
    import datetime

    d = datetime.date.fromisoformat(iso_date)
    return {
        "mes": MESES[d.month - 1],
        "dia": f"{d.day:02d}",
        "semana": DIAS_SEMANA[d.weekday()],
    }


def hex_to_rgb(hexcolor: str) -> tuple:
    h = hexcolor.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def carregar_paleta() -> dict:
    return {nome: hex_to_rgb(v) for nome, v in config.PALETA.items()}


@lru_cache(maxsize=None)
def carregar_fonte(nome: str, tamanho: int) -> ImageFont.FreeTypeFont:
    path = config.FONTES[nome]
    return ImageFont.truetype(path, tamanho)


def redimensionar_logo_por_altura(logo: Image.Image, altura_alvo: int) -> Image.Image:
    """Redimensiona a logo por altura (não largura) — logos podem ser quadradas ou retangulares."""
    largura_alvo = int(altura_alvo * logo.width / logo.height)
    return logo.resize((largura_alvo, altura_alvo), Image.LANCZOS)


def desenhar_texto_iniciais(draw, xy, texto, fonte, cor_inicial, cor_resto):
    """Desenha 'texto' palavra por palavra: 1ª letra de cada palavra em cor_inicial, resto em cor_resto.

    Retorna a largura total desenhada (px), pra encadear outros desenhos depois.
    """
    x, y = xy
    x0 = x
    for i, palavra in enumerate(texto.split(" ")):
        if not palavra:
            continue
        inicial, resto = palavra[0], palavra[1:]
        draw.text((x, y), inicial, font=fonte, fill=cor_inicial)
        x += _largura_texto(draw, inicial, fonte)
        if resto:
            draw.text((x, y), resto, font=fonte, fill=cor_resto)
            x += _largura_texto(draw, resto, fonte)
        if i < len(texto.split(" ")) - 1:
            x += _largura_texto(draw, " ", fonte)
    return x - x0


def desenhar_estrela(draw, x, y, size, cor):
    """★ vetorial de 5 pontas centrada em (x, y), 'size' = raio externo."""
    pontos = []
    raio_interno = size * 0.42
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        r = size if i % 2 == 0 else raio_interno
        pontos.append((x + r * math.cos(ang), y + r * math.sin(ang)))
    draw.polygon(pontos, fill=cor)


def _largura_texto(draw, texto, fonte):
    bbox = draw.textbbox((0, 0), texto, font=fonte)
    return bbox[2] - bbox[0]


def desenhar_texto_pipes(draw, xy, itens, fonte, cor_texto, cor_pipe, separador=" | "):
    """Desenha itens (lista de str) separados por 'separador', com o separador em cor_pipe."""
    x, y = xy
    for i, item in enumerate(itens):
        draw.text((x, y), item, font=fonte, fill=cor_texto)
        x += _largura_texto(draw, item, fonte)
        if i < len(itens) - 1:
            draw.text((x, y), separador, font=fonte, fill=cor_pipe)
            x += _largura_texto(draw, separador, fonte)
    return x - xy[0]


def largura_texto_pipes(draw, itens, fonte, separador=" | "):
    return _largura_texto(draw, separador.join(itens), fonte)


def fonte_pipes_ajustada(draw, itens, nome_fonte, tamanho_max, largura_max, min_size=15, passo=1, separador=" | "):
    """Reduz o tamanho da fonte até a barra de pipes caber em largura_max (1 linha só)."""
    tamanho = tamanho_max
    while tamanho > min_size:
        fonte = carregar_fonte(nome_fonte, tamanho)
        if largura_texto_pipes(draw, itens, fonte, separador) <= largura_max:
            return fonte
        tamanho -= passo
    return carregar_fonte(nome_fonte, min_size)


def desenhar_texto_com_estrelas(draw, center_x, y, texto, fonte, cor_texto, cor_estrela,
                                 star_size=7, gap=14):
    """★ texto ★ centralizado horizontalmente em center_x, estrelas vetoriais (não glifo de fonte)."""
    largura_texto = _largura_texto(draw, texto, fonte)
    bbox = draw.textbbox((0, 0), "Ãg", font=fonte)
    altura_texto = bbox[3] - bbox[1]
    largura_total = star_size * 2 + gap * 2 + largura_texto + star_size * 2
    x0 = center_x - largura_total / 2

    cy = y + altura_texto / 2 - bbox[1]
    desenhar_estrela(draw, x0 + star_size, cy, star_size, cor_estrela)
    x_texto = x0 + star_size * 2 + gap
    draw.text((x_texto, y), texto, font=fonte, fill=cor_texto)
    x_estrela2 = x_texto + largura_texto + gap + star_size
    desenhar_estrela(draw, x_estrela2, cy, star_size, cor_estrela)
    return largura_total


def quebrar_linhas(draw, texto, fonte, largura_max):
    palavras = texto.split()
    if not palavras:
        return [""]
    linhas = []
    atual = palavras[0]
    for palavra in palavras[1:]:
        teste = f"{atual} {palavra}"
        if _largura_texto(draw, teste, fonte) <= largura_max:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    linhas.append(atual)
    return linhas


def fit_text(draw, texto, fonte_path, tamanho_max, largura_max, altura_max,
             min_ratio=0.55, max_linhas=3, passo=4, log=None):
    """Reduz o tamanho da fonte até o texto caber em largura_max x altura_max.

    Retorna (fonte, linhas, tamanho).
    """
    tamanho = tamanho_max
    tamanho_min = max(1, int(tamanho_max * min_ratio))
    melhor = None
    while tamanho >= tamanho_min:
        fonte = ImageFont.truetype(fonte_path, tamanho)
        linhas = quebrar_linhas(draw, texto, fonte, largura_max)
        bbox = draw.textbbox((0, 0), "Ãg", font=fonte)
        altura_linha = (bbox[3] - bbox[1]) * 1.15
        altura_total = altura_linha * len(linhas)
        largura_ok = all(_largura_texto(draw, l, fonte) <= largura_max for l in linhas)
        melhor = (fonte, linhas, tamanho)
        if len(linhas) <= max_linhas and largura_ok and altura_total <= altura_max:
            return fonte, linhas, tamanho
        tamanho -= passo
    if log:
        log.warning(
            "fit_text: '%s' não coube em %dx%d — usando tamanho mínimo %d",
            texto, largura_max, altura_max, tamanho_min,
        )
    # rede de segurança: nunca devolve mais linhas que max_linhas, mesmo no mínimo
    fonte, linhas, tamanho = melhor
    if len(linhas) > max_linhas:
        cabeca, resto = linhas[:max_linhas - 1], linhas[max_linhas - 1:]
        linhas = cabeca + [" ".join(resto)]
        melhor = (fonte, linhas, tamanho)
    return melhor


def cmyk_to_rgb(cmyk) -> tuple:
    """[c, m, y, k] floats 0.0-1.0 (podem passar de 1.0 em vermelhos saturados) -> (r, g, b)."""
    c, m, y, k = [max(0.0, min(1.0, v)) for v in cmyk]
    r = int(255 * (1 - c) * (1 - k))
    g = int(255 * (1 - m) * (1 - k))
    b = int(255 * (1 - y) * (1 - k))
    return (r, g, b)


def draw_text_tracked(draw, xy, text, font, fill, tracking=0, **text_kwargs):
    """Desenha texto com tracking (Pillow não tem isso nativo).

    tracking em milésimos de EM (formato PS/AI): 20 = 20/1000 * font_size px extra por char.
    Retorna a largura total desenhada.
    """
    extra = (tracking / 1000) * font.size
    x, y = xy
    for char in text:
        draw.text((x, y), char, font=font, fill=fill, **text_kwargs)
        x += font.getlength(char) + extra
    return x - xy[0]


def fit_cover(img: Image.Image, target_w: int, target_h: int, foco: str = "topo") -> Image.Image:
    """Escala proporcionalmente até cobrir target_w x target_h e corta.

    Âncora horizontal: sempre centro.
    Âncora vertical: 'topo' alinha o topo (rostos no terço superior); 'centro' centraliza.
    """
    src_w, src_h = img.size
    escala = max(target_w / src_w, target_h / src_h)
    novo_w, novo_h = math.ceil(src_w * escala), math.ceil(src_h * escala)
    img_redim = img.resize((novo_w, novo_h), Image.LANCZOS)

    x = (novo_w - target_w) / 2
    if foco == "centro":
        y = (novo_h - target_h) / 2
    else:  # topo
        y = 0
    x = min(max(x, 0), novo_w - target_w)
    y = min(max(y, 0), novo_h - target_h)
    return img_redim.crop((int(x), int(y), int(x) + target_w, int(y) + target_h))


def configurar_log() -> logging.Logger:
    os.makedirs(config.LOGS_DIR, exist_ok=True)
    logger = logging.getLogger("fbs")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
    return logger


class JobError(Exception):
    pass


def validar_assets():
    faltando = [p for p in config.ASSET_FILES if not os.path.isfile(p)]
    if faltando:
        raise JobError("Assets faltando: " + ", ".join(faltando))


def validar_job(job: dict) -> dict:
    for campo in config.CAMPOS_OBRIGATORIOS:
        if campo not in job or job[campo] in (None, ""):
            raise JobError(f"campo obrigatório faltando: {campo}")

    job = {**config.DEFAULTS, **job}

    try:
        job["_data_ptbr"] = data_ptbr(job["data"])
    except Exception as e:
        raise JobError(f"data inválida '{job.get('data')}': {e}")

    if job["foco"] not in ("topo", "centro"):
        raise JobError(f"foco inválido: {job['foco']} (use 'topo' ou 'centro')")

    if job["enquadramento"] not in ("auto", "manual"):
        raise JobError(f"enquadramento inválido: {job['enquadramento']} (use 'auto' ou 'manual')")

    foto_path = job["foto"]
    if not os.path.isabs(foto_path):
        foto_path = os.path.join(config.ROOT, foto_path)
    if not os.path.isfile(foto_path):
        raise JobError(f"foto não encontrada: {job['foto']}")
    job["_foto_path"] = foto_path

    formatos_validos = set(config.DIMENSOES.keys())
    invalidos = set(job["formatos"]) - formatos_validos
    if invalidos:
        raise JobError(f"formatos inválidos: {invalidos}")

    faltando_psd = [
        f for f in job["formatos"]
        if not os.path.isfile(config.TEMPLATE_FILES[f])
    ]
    if faltando_psd:
        raise JobError(
            "template PSD não encontrado para: " + ", ".join(faltando_psd)
            + " (esperado em " + ", ".join(config.TEMPLATE_FILES[f] for f in faltando_psd) + ")"
        )

    return job
