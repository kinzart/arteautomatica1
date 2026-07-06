import unittest

from fbs.editor_history import HistoricoEditor


class EditorHistoryTest(unittest.TestCase):
    def test_desfazer_e_refazer(self):
        historico = HistoricoEditor({"valor": 1})
        historico.registrar({"valor": 2})
        historico.registrar({"valor": 3})

        self.assertEqual(historico.desfazer(), {"valor": 2})
        self.assertEqual(historico.desfazer(), {"valor": 1})
        self.assertIsNone(historico.desfazer())
        self.assertEqual(historico.refazer(), {"valor": 2})

    def test_nova_edicao_descarta_refazer(self):
        historico = HistoricoEditor({"valor": 1})
        historico.registrar({"valor": 2})
        historico.desfazer()
        historico.registrar({"valor": 4})

        self.assertFalse(historico.pode_refazer)
        self.assertEqual(historico.atual, {"valor": 4})

    def test_estado_e_copiado(self):
        estado = {"lista": [1]}
        historico = HistoricoEditor(estado)
        estado["lista"].append(2)

        self.assertEqual(historico.atual, {"lista": [1]})


if __name__ == "__main__":
    unittest.main()
