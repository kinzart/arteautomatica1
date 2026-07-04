"""Comparação auxiliar entre um PNG gerado e o gold master."""
import numpy as np
from PIL import Image


def comparar(caminho_gerado, caminho_referencia, caminho_diff=None):
    gerado = Image.open(caminho_gerado).convert("RGB")
    referencia = Image.open(caminho_referencia).convert("RGB").resize(gerado.size, Image.LANCZOS)
    a = np.asarray(gerado, dtype=np.uint8)
    b = np.asarray(referencia, dtype=np.uint8)
    diferenca = np.abs(a.astype(np.int16) - b.astype(np.int16))
    resultado = {"diferenca_media": float(diferenca.mean())}
    try:
        from skimage.metrics import structural_similarity
        resultado["ssim"] = float(structural_similarity(a, b, channel_axis=2))
    except ImportError:
        resultado["ssim"] = None
    if caminho_diff:
        Image.fromarray(np.clip(diferenca * 2, 0, 255).astype(np.uint8), "RGB").save(caminho_diff)
    return resultado

