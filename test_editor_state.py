import json
import os
import tempfile
import unittest
from unittest import mock

from fbs import editor_state


class EditorStateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.principal = os.path.join(self.tmp.name, "ajustes.json")
        self.temporario = os.path.join(self.tmp.name, "ajustes.editor.tmp.json")
        self.backups = os.path.join(self.tmp.name, "backups")
        with open(self.principal, "w", encoding="utf-8") as arquivo:
            json.dump({"feed": {"txt_artista": {"tamanho": 100, "tracking": -20}}}, arquivo)
        self.patches = (
            mock.patch.object(editor_state, "AJUSTES_PRINCIPAL", self.principal),
            mock.patch.object(editor_state, "AJUSTES_TEMP", self.temporario),
            mock.patch.object(editor_state, "BACKUPS_DIR", self.backups),
        )
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in reversed(self.patches):
            patch.stop()
        self.tmp.cleanup()

    def test_merge_preserva_campos(self):
        editor_state.inicializar_temporario()
        editor_state.atualizar_slot("feed", "txt_artista", {"offset_x": 12})
        slot = editor_state.carregar_temporario()["feed"]["txt_artista"]
        self.assertEqual(slot, {"tamanho": 100, "tracking": -20, "offset_x": 12})

    def test_salvar_cria_backup(self):
        editor_state.inicializar_temporario()
        editor_state.atualizar_slot("feed", "txt_artista", {"tamanho": 120})
        backup = editor_state.salvar_no_principal()
        self.assertTrue(os.path.isfile(backup))
        self.assertEqual(editor_state._ler(backup)["feed"]["txt_artista"]["tamanho"], 100)
        self.assertEqual(editor_state._ler(self.principal)["feed"]["txt_artista"]["tamanho"], 120)


if __name__ == "__main__":
    unittest.main()
