import unittest

import numpy as np
from PIL import Image

from fbs.compositor import desenhar_texto


class CompositorOpacityTest(unittest.TestCase):
    META = {
        "slot": "txt_data_semana",
        "bbox": (5, 5, 190, 90),
        "tracking": 0,
        "cor_rgb": (255, 255, 255),
    }

    def _soma(self, opacidade):
        imagem = Image.new("RGBA", (200, 100), (0, 0, 0, 255))
        desenhar_texto(imagem, self.META, "TESTE", {
            "tamanho": 50, "cor": "#FFFFFF", "opacidade": opacidade,
        })
        return int(np.asarray(imagem.convert("RGB"), dtype=np.uint32).sum())

    def test_opacidade_real(self):
        invisivel = self._soma(0)
        metade = self._soma(.5)
        opaco = self._soma(1)
        self.assertEqual(invisivel, 0)
        self.assertGreater(metade, invisivel)
        self.assertLess(metade, opaco)


if __name__ == "__main__":
    unittest.main()

