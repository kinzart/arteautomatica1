"""Testa fbs/tratamento.py isolado com 3 fotos-teste e salva o resultado duotone."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image
from fbs import util, tratamento

paleta = util.carregar_paleta()
fotos = ["fotos/artista28.jpeg", "fotos/teste2.jpg", "fotos/teste3.jpg"]

os.makedirs("outputs/_teste_duotone", exist_ok=True)
for foto in fotos:
    img = Image.open(foto)
    tratada = tratamento.tratar_foto(img, paleta, bordas_fusao=("baixo", "esq"))
    bg = Image.new("RGB", tratada.size, paleta["INK"])
    bg.paste(tratada, (0, 0), tratada)
    nome = os.path.splitext(os.path.basename(foto))[0]
    out = f"outputs/_teste_duotone/{nome}_duotone.png"
    bg.save(out)
    print("ok:", out)
