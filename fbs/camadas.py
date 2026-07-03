"""Camadas globais compartilhadas pelos 3 layouts (ver seção 6.4 do brief)."""
import os
import numpy as np
from PIL import Image

from . import config


def abrir_textura(nome_arquivo):
    return Image.open(os.path.join(config.ASSETS, nome_arquivo)).convert("RGB")


def cobrir(img, w, h):
    """Redimensiona a textura cobrindo w x h (crop central), sem depender de foco."""
    src_w, src_h = img.size
    escala = max(w / src_w, h / src_h)
    novo = img.resize((int(src_w * escala) + 1, int(src_h * escala) + 1), Image.LANCZOS)
    x = (novo.width - w) // 2
    y = (novo.height - h) // 2
    return novo.crop((x, y, x + w, y + h))


def blend_screen(base: Image.Image, overlay: Image.Image, opacidade: float) -> Image.Image:
    a = np.asarray(base.convert("RGB"), dtype=np.float32) / 255.0
    b = np.asarray(overlay.convert("RGB").resize(base.size, Image.LANCZOS), dtype=np.float32) / 255.0
    screen = 1 - (1 - a) * (1 - b)
    out = a * (1 - opacidade) + screen * opacidade
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGB")


def blend_overlay(base: Image.Image, overlay: Image.Image, opacidade: float) -> Image.Image:
    a = np.asarray(base.convert("RGB"), dtype=np.float32) / 255.0
    b = np.asarray(overlay.convert("RGB").resize(base.size, Image.LANCZOS), dtype=np.float32) / 255.0
    ov = np.where(a < 0.5, 2 * a * b, 1 - 2 * (1 - a) * (1 - b))
    out = a * (1 - opacidade) + ov * opacidade
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGB")


def blend_multiply(base: Image.Image, overlay: Image.Image, opacidade: float) -> Image.Image:
    a = np.asarray(base.convert("RGB"), dtype=np.float32) / 255.0
    b = np.asarray(overlay.convert("RGB").resize(base.size, Image.LANCZOS), dtype=np.float32) / 255.0
    mult = a * b
    out = a * (1 - opacidade) + mult * opacidade
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGB")


def fundo_solido(w, h, cor) -> Image.Image:
    return Image.new("RGB", (w, h), cor)


def aplicar_textura_bordas(canvas: Image.Image, opacidade=0.70) -> Image.Image:
    tex = cobrir(abrir_textura("textura_bordas.png"), *canvas.size)
    return blend_multiply(canvas, tex, opacidade)


def aplicar_vinheta_radial(canvas: Image.Image, cor_ink, forca=0.5) -> Image.Image:
    """Escurece as 4 bordas (gradiente radial do centro pra fora) — aumenta o 'peso' das bordas."""
    w, h = canvas.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2, h / 2
    dist = np.sqrt(((xx - cx) / (w / 2)) ** 2 + ((yy - cy) / (h / 2)) ** 2)
    alpha = np.clip((dist - 0.55) / 0.50, 0, 1) * forca
    base = np.asarray(canvas.convert("RGB"), dtype=np.float32)
    ink = np.asarray(Image.new("RGB", (w, h), cor_ink), dtype=np.float32)
    out = base * (1 - alpha[:, :, None]) + ink * alpha[:, :, None]
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def colar_bokeh(canvas: Image.Image, bbox, opacidade=0.30, feather=48) -> Image.Image:
    """bbox = (x0, y0, x1, y1) região onde o bokeh entra, com borda suave (sem costura dura)."""
    from PIL import ImageDraw, ImageFilter

    x0, y0, x1, y1 = [int(v) for v in bbox]
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return canvas
    tex = cobrir(abrir_textura("textura_bokeh.png"), w, h)
    regiao = canvas.crop((x0, y0, x1, y1))
    misturada = blend_screen(regiao, tex, opacidade)

    mascara = Image.new("L", canvas.size, 0)
    md = ImageDraw.Draw(mascara)
    md.rectangle([x0, y0, x1, y1], fill=255)
    mascara = mascara.filter(ImageFilter.GaussianBlur(feather))

    camada_full = canvas.copy()
    camada_full.paste(misturada, (x0, y0))
    return Image.composite(camada_full, canvas, mascara)


def colar_foto(canvas: Image.Image, foto_rgba: Image.Image, pos) -> Image.Image:
    resultado = canvas.copy().convert("RGBA")
    resultado.alpha_composite(foto_rgba, dest=pos)
    return resultado.convert("RGB")


def aplicar_grain(canvas: Image.Image, opacidade=0.28) -> Image.Image:
    tex = cobrir(abrir_textura("textura_grain.png"), *canvas.size)
    return blend_overlay(canvas, tex, opacidade)


def hairline(draw, box, cor, espessura=1):
    """box = (x0, y0, x1, y1) retângulo fino."""
    draw.rectangle(box, fill=cor)
