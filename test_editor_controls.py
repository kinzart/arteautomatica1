import json
import os
import tempfile
import unittest
from types import SimpleNamespace

from editor_visual import EditorVisual
from fbs.ajustes import carregar_ajustes


class EditorControlsTest(unittest.TestCase):
    def test_quantizacao(self):
        self.assertEqual(EditorVisual._quantizar(123.04338, 1), 123)
        self.assertEqual(EditorVisual._formatar_numero(123, 1), "123")
        self.assertEqual(EditorVisual._quantizar(1.234, .1), 1.2)
        self.assertEqual(EditorVisual._formatar_numero(1.2, .1), "1.2")

    def _arquivo(self, ajuste, slot="txt_edicao"):
        fd, caminho = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump({"feed": {slot: ajuste}}, arquivo)
        self.addCleanup(lambda: os.path.exists(caminho) and os.unlink(caminho))
        return caminho

    def test_cor_invalida(self):
        with self.assertRaisesRegex(ValueError, "#RRGGBB"):
            carregar_ajustes(self._arquivo({"cor": ""}))

    def test_opacidade_fora_do_intervalo(self):
        with self.assertRaisesRegex(ValueError, "entre 0 e 1"):
            carregar_ajustes(self._arquivo({"opacidade": 2}))

    def test_opacidade_global_fora_do_intervalo(self):
        with self.assertRaisesRegex(ValueError, "entre 0 e 1"):
            carregar_ajustes(self._arquivo({"grain_opacidade": -0.1}, "global"))

    def test_valida_foto_do_job(self):
        editor = object.__new__(EditorVisual)
        editor.photo_var = SimpleNamespace(get=lambda: "assets/foto_original_pra_teste.jpeg")

        self.assertEqual(editor._validar_foto(), "assets/foto_original_pra_teste.jpeg")

    def test_rejeita_foto_inexistente(self):
        editor = object.__new__(EditorVisual)
        editor.photo_var = SimpleNamespace(get=lambda: "fotos/nao-existe.jpg")

        with self.assertRaisesRegex(ValueError, "foto não encontrada"):
            editor._validar_foto()


if __name__ == "__main__":
    unittest.main()
