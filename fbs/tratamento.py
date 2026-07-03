"""Tratamento de foto — duotone âmbar ("o bonitão") + máscara de fusão de bordas."""
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageDraw

from . import camadas


def _lut_duotone(cor_sombra, cor_meio, cor_luz):
    """LUT 256x3: 0..127 interpola sombra->meio, 128..255 interpola meio->luz."""
    lut = np.zeros((256, 3), dtype=np.float32)
    sombra = np.array(cor_sombra, dtype=np.float32)
    meio = np.array(cor_meio, dtype=np.float32)
    luz = np.array(cor_luz, dtype=np.float32)
    t1 = np.linspace(0, 1, 128)[:, None]
    lut[:128] = sombra * (1 - t1) + meio * t1
    t2 = np.linspace(0, 1, 128)[:, None]
    lut[128:] = meio * (1 - t2) + luz * t2
    return lut


def _curva_s(arr, forca=1.15):
    """Curva em S suave centrada em 0.5 — aumenta contraste no meio-tom."""
    x = arr / 255.0
    y = x + (x - 0.5) * (forca - 1.0) * (1 - np.abs(2 * x - 1))
    return np.clip(y, 0, 1) * 255.0


def _mascara_vinheta(w, h, forca=0.6):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2, h / 2
    dist = np.sqrt(((xx - cx) / (w / 2)) ** 2 + ((yy - cy) / (h / 2)) ** 2)
    falloff = np.clip(1.0 - forca * np.clip(dist - 0.35, 0, None), 1 - forca, 1.0)
    return falloff


def mascara_fusao(w, h, bordas=("baixo",), largura_frac=0.22):
    """Alpha 0..1 que esmaece a foto nas bordas indicadas ('baixo','esq','dir','topo')."""
    alpha = np.ones((h, w), dtype=np.float32)
    if "baixo" in bordas:
        banda = int(h * largura_frac)
        grad = np.linspace(1, 0, banda)
        alpha[h - banda:h, :] *= grad[:, None]
    if "topo" in bordas:
        banda = int(h * largura_frac)
        grad = np.linspace(0, 1, banda)
        alpha[0:banda, :] *= grad[:, None]
    if "esq" in bordas:
        banda = int(w * largura_frac)
        grad = np.linspace(0, 1, banda)
        alpha[:, 0:banda] *= grad[None, :]
    if "dir" in bordas:
        banda = int(w * largura_frac)
        grad = np.linspace(1, 0, banda)
        alpha[:, w - banda:w] *= grad[None, :]
    return alpha


def tratar_foto(img: Image.Image, paleta: dict, bordas_fusao=("baixo",),
                 forca_vinheta=0.6, forca_curva=1.15, largura_frac=0.15) -> Image.Image:
    """Pipeline completo (ver seção 4 do brief). Retorna RGBA pronta pra colar."""
    img = img.convert("RGB")

    # 1. auto tone
    img = ImageOps.autocontrast(img, cutoff=1)

    # 2. escurecer base (luminância x0.75) + 3. converter para L
    l = np.asarray(img.convert("L"), dtype=np.float32) * 0.75
    l = np.clip(l, 0, 255)

    # 4. contraste editorial (curva em S)
    l = _curva_s(l, forca_curva)

    # 3. duotone âmbar via LUT
    lut = _lut_duotone(paleta["INK"], paleta["PALCO"], paleta["BS_AMBER"])
    idx = l.astype(np.uint8)
    rgb = lut[idx]  # (h, w, 3) float

    # 5. vinheta
    h, w = l.shape
    vinheta = _mascara_vinheta(w, h, forca_vinheta)
    rgb = rgb * vinheta[:, :, None]
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    tratada = Image.fromarray(rgb, "RGB").filter(ImageFilter.GaussianBlur(0.4))

    # 6. máscara de fusão -> alpha (mais agressiva no lado que encosta no texto)
    alpha = mascara_fusao(w, h, bordas=bordas_fusao, largura_frac=largura_frac)
    alpha_img = Image.fromarray((alpha * 255).astype(np.uint8), "L")

    resultado = tratada.convert("RGBA")
    resultado.putalpha(alpha_img)
    return resultado


def texturizar_texto(canvas: Image.Image, texto: str, fonte, xy, cor_base, forca=0.7, desgaste=0.25) -> Image.Image:
    """Desenha 'texto' com textura de papel envelhecido dentro das letras (ver Ajuste 1).

    1. máscara = letras em branco puro
    2. cor_base multiplicada pela textura_papel (opacidade 'forca') -> preenchimento texturizado
    3. desgaste: mistura textura_bordas (dessaturada) no canal alpha da máscara, corroendo
       levemente as bordas das letras (tinta seca / desgaste)
    """
    w, h = canvas.size

    mascara = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mascara).text(xy, texto, font=fonte, fill=255)

    papel = camadas.cobrir(camadas.abrir_textura("textura_papel.png"), w, h)
    cor_layer = Image.new("RGB", (w, h), cor_base)
    preenchimento = camadas.blend_multiply(cor_layer, papel, forca)

    if desgaste > 0:
        bordas = camadas.cobrir(camadas.abrir_textura("textura_bordas.png"), w, h).convert("L")
        bordas_arr = np.asarray(bordas, dtype=np.float32) / 255.0
        mask_arr = np.asarray(mascara, dtype=np.float32) / 255.0
        mask_arr = mask_arr * (1 - desgaste + desgaste * bordas_arr)
        mascara = Image.fromarray(np.clip(mask_arr * 255, 0, 255).astype(np.uint8), "L")

    resultado = canvas.copy()
    resultado.paste(preenchimento, (0, 0), mascara)
    return resultado
