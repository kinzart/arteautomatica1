import unittest

from fbs.compositor import _quebrar_artista_duas_linhas


class LayoutArtistaTest(unittest.TestCase):
    def test_duas_palavras(self):
        self.assertEqual(_quebrar_artista_duas_linhas("Green Téa"), ["GREEN", "TÉA"])

    def test_tres_palavras(self):
        self.assertEqual(
            _quebrar_artista_duas_linhas("Bebeco Blues Band"),
            ["BEBECO", "BLUES BAND"],
        )

    def test_primeira_menor_que_terceira(self):
        self.assertEqual(
            _quebrar_artista_duas_linhas("Ana Clara Nascimento"),
            ["ANA CLARA", "NASCIMENTO"],
        )

    def test_nome_longo_balanceado(self):
        self.assertEqual(
            _quebrar_artista_duas_linhas("Maria Aparecida dos Santos"),
            ["MARIA APARECIDA", "DOS SANTOS"],
        )


if __name__ == "__main__":
    unittest.main()
