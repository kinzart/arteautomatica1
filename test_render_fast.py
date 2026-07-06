import json
import os
import unittest

from fbs import ajustes as ajustes_mod
from fbs import config, util
from render_fast import gerar_fast


class RenderFastTest(unittest.TestCase):
    def test_renderiza_feed_sem_psd_no_caminho_quente(self):
        with open(os.path.join(config.ROOT, "jobs", "job_gonzalo.json"), "r", encoding="utf-8") as arquivo:
            job = util.validar_job(json.load(arquivo))
        imagem = gerar_fast(job, ajustes_mod.carregar_ajustes())
        self.assertEqual(imagem.size, config.DIMENSOES["feed"])
        self.assertEqual(imagem.mode, "RGB")


if __name__ == "__main__":
    unittest.main()

