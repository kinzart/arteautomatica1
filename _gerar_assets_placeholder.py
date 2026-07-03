"""
Gera assets placeholder (logo + texturas + foto de teste) porque os arquivos
originais do design system (fornecidos pelo time de design) nao estavam na
pasta. Rodar uma vez; substituir os PNGs em assets/ pelos originais quando
disponiveis. Nao faz parte do pipeline de producao (gerar.py).
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
import math
import random

random.seed(7)
np.random.seed(7)

ASSETS = "assets"
INK = (11, 9, 7)
INK_ALT = (21, 17, 13)
CREAM = (243, 238, 227)
BS_RED = (255, 0, 0)
BS_AMBER = (245, 165, 36)
PALCO = (42, 32, 24)
WARM_GRAY = (117, 107, 93)
OXBLOOD = (78, 0, 0)

SIZE = 2048


def save(img, name):
    img.save(f"{ASSETS}/{name}")
    print("gerado:", name, img.size, img.mode)


# ---------------------------------------------------------------- logo_bs.png
def gen_logo():
    img = Image.new("RGBA", (1400, 500), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(f"{ASSETS}/fonts/Anton-Regular.ttf", 320)
    txt = "BS"
    bbox = d.textbbox((0, 0), txt, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (img.width - w) / 2 - bbox[0]
    y = (img.height - h) / 2 - bbox[1] - 40
    d.text((x, y), txt, font=font, fill=BS_RED + (255,))
    # underline vinho
    d.rectangle([120, 400, 1280, 414], fill=OXBLOOD + (255,))
    mono = ImageFont.truetype(f"{ASSETS}/fonts/SpaceMono-Regular.ttf", 46)
    sub = "BLUES SESSION"
    bbox2 = d.textbbox((0, 0), sub, font=mono)
    w2 = bbox2[2] - bbox2[0]
    d.text(((img.width - w2) / 2, 430), sub, font=mono, fill=CREAM + (255,))
    save(img, "logo_bs.png")


# ------------------------------------------------------------ textura_bokeh
def gen_bokeh():
    img = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    for _ in range(90):
        r = random.randint(20, 160)
        x = random.randint(0, SIZE)
        y = random.randint(0, SIZE)
        warm = random.choice([BS_AMBER, (255, 140, 40), (255, 90, 20), OXBLOOD])
        alpha = random.randint(60, 170)
        layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        ld.ellipse([x - r, y - r, x + r, y + r], fill=warm + (alpha,))
        layer = layer.filter(ImageFilter.GaussianBlur(r * 0.35))
        img = Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")
    img = img.filter(ImageFilter.GaussianBlur(3))
    save(img, "textura_bokeh.png")


# ----------------------------------------------------------- textura_bordas
def gen_bordas():
    """Papel escuro com desgaste irregular nas bordas (sem vinheta circular perfeita)."""
    noise = (np.random.rand(SIZE, SIZE) * 255).astype(np.uint8)
    base = Image.fromarray(noise, "L").filter(ImageFilter.GaussianBlur(1))

    yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
    # distancia minima ate a borda mais proxima (vinheta retangular, nao circular)
    dist_borda = np.minimum.reduce([xx, SIZE - xx, yy, SIZE - yy]) / SIZE
    vign = np.clip(dist_borda / 0.42, 0, 1)

    # varias manchas de desgaste irregulares (blobs de ruido borrado) concentradas na borda
    wear = np.zeros((SIZE, SIZE), dtype=np.float32)
    for _ in range(14):
        blob = np.random.rand(SIZE, SIZE).astype(np.float32)
        blob_img = Image.fromarray((blob * 255).astype(np.uint8), "L")
        blob_img = blob_img.filter(ImageFilter.GaussianBlur(random.randint(40, 140)))
        wear += np.asarray(blob_img, dtype=np.float32) / 255.0
    wear /= wear.max()
    # mancha so conta perto das bordas (onde vign < 1)
    wear_borda = wear * (1 - vign)

    mask = np.clip(vign - wear_borda * 0.9, 0, 1)
    mask_img = Image.fromarray((mask * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(6))

    out = Image.composite(base, Image.new("L", (SIZE, SIZE), 0), mask_img)
    save(out.convert("RGB"), "textura_bordas.png")


# ------------------------------------------------------------ textura_papel
def gen_papel():
    base = (np.random.rand(SIZE, SIZE, 1) * 40 - 20)
    beige = np.array([214, 200, 173], dtype=np.float32)
    arr = np.clip(beige.reshape(1, 1, 3) + base, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB").filter(ImageFilter.GaussianBlur(0.6))
    save(img, "textura_papel.png")


# ------------------------------------------------------------ textura_grain
def gen_grain():
    noise = (np.random.rand(SIZE, SIZE) * 255).astype(np.uint8)
    img = Image.fromarray(noise, "L").convert("RGB")
    save(img, "textura_grain.png")


# ------------------------------------------------------- foto de teste (fotos/)
def gen_foto_teste(path, w=1600, h=2000):
    img = Image.new("RGB", (w, h), (18, 14, 20))
    d = ImageDraw.Draw(img)
    # spotlight cone
    for i in range(0, h, 4):
        t = i / h
        col = (
            int(30 + 60 * (1 - t)),
            int(20 + 35 * (1 - t)),
            int(35 + 50 * (1 - t)),
        )
        d.line([(0, i), (w, i)], fill=col)
    spot = Image.new("L", (w, h), 0)
    sd = ImageDraw.Draw(spot)
    sd.ellipse([w * 0.15, -h * 0.3, w * 0.95, h * 0.75], fill=180)
    spot = spot.filter(ImageFilter.GaussianBlur(150))
    warm = Image.new("RGB", (w, h), (255, 170, 90))
    img = Image.composite(warm, img, spot.point(lambda p: int(p * 0.35)))
    # silhueta de "artista"
    d = ImageDraw.Draw(img)
    cx = w * 0.5
    d.ellipse([cx - 90, h * 0.18, cx + 90, h * 0.18 + 220], fill=(15, 11, 10))
    d.polygon(
        [
            (cx - 140, h * 0.38),
            (cx + 140, h * 0.38),
            (cx + 190, h * 0.95),
            (cx - 190, h * 0.95),
        ],
        fill=(20, 15, 14),
    )
    d.line([(cx - 160, h * 0.55), (cx - 260, h * 0.7)], fill=(25, 18, 15), width=40)
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    noise = (np.random.rand(h, w, 1) * 14 - 7)
    arr = np.clip(np.array(img, dtype=np.float32) + noise, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "RGB").save(path, quality=92)
    print("gerado foto teste:", path)


if __name__ == "__main__":
    gen_logo()
    gen_bokeh()
    gen_bordas()
    gen_papel()
    gen_grain()
    gen_foto_teste("fotos/artista28.jpg")
    gen_foto_teste("fotos/teste2.jpg", w=1400, h=1400)
    gen_foto_teste("fotos/teste3.jpg", w=2000, h=1500)
