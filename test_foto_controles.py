import unittest

import numpy as np
from PIL import Image

from fbs.compositor import ajustar_foto


class FotoControlesTest(unittest.TestCase):
    @staticmethod
    def _imagem_marcada():
        arr = np.zeros((50, 100, 3), dtype=np.uint8)
        arr[:, :50] = (255, 0, 0)
        arr[:, 50:] = (0, 0, 255)
        return Image.fromarray(arr)

    def test_espelha_horizontalmente(self):
        resultado = ajustar_foto(self._imagem_marcada(), {"espelhar_horizontal": True})

        self.assertEqual(resultado.getpixel((5, 25)), (0, 0, 255))
        self.assertEqual(resultado.getpixel((95, 25)), (255, 0, 0))

    def test_offset_excedente_e_limitado_sem_alterar_zoom(self):
        imagem = self._imagem_marcada()
        na_borda = ajustar_foto(imagem, {"zoom": 1.1, "offset_x": 5})
        muito_alem = ajustar_foto(imagem, {"zoom": 1.1, "offset_x": 500})

        self.assertTrue(np.array_equal(np.asarray(na_borda), np.asarray(muito_alem)))

if __name__ == "__main__":
    unittest.main()
