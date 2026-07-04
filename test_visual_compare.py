import os
import tempfile
import unittest

from PIL import Image

from fbs.visual_compare import comparar


class VisualCompareTest(unittest.TestCase):
    def test_imagens_iguais(self):
        with tempfile.TemporaryDirectory() as pasta:
            imagem = os.path.join(pasta, "imagem.png")
            diff = os.path.join(pasta, "diff.png")
            Image.new("RGB", (32, 40), (20, 30, 40)).save(imagem)
            metricas = comparar(imagem, imagem, diff)
            self.assertEqual(metricas["diferenca_media"], 0)
            if metricas["ssim"] is not None:
                self.assertEqual(metricas["ssim"], 1)
            self.assertTrue(os.path.isfile(diff))


if __name__ == "__main__":
    unittest.main()

