"""Persistência segura para o editor visual de ajustes."""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import tempfile

from . import ajustes as ajustes_mod
from . import config

AJUSTES_PRINCIPAL = ajustes_mod.AJUSTES_PATH
AJUSTES_TEMP = os.path.join(config.ROOT, "ajustes.editor.tmp.json")
BACKUPS_DIR = os.path.join(config.ROOT, "backups")


def _ler(caminho):
    with open(caminho, "r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def _salvar_atomico(caminho, dados):
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    fd, temporario = tempfile.mkstemp(prefix=".ajustes-", suffix=".json", dir=os.path.dirname(caminho) or ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, ensure_ascii=False, indent=2)
            arquivo.write("\n")
        ajustes_mod.carregar_ajustes(temporario)
        os.replace(temporario, caminho)
    finally:
        if os.path.exists(temporario):
            os.unlink(temporario)


def inicializar_temporario(forcar=False):
    if forcar or not os.path.isfile(AJUSTES_TEMP):
        _salvar_atomico(AJUSTES_TEMP, _ler(AJUSTES_PRINCIPAL))
    return _ler(AJUSTES_TEMP)


def carregar_temporario():
    return inicializar_temporario(forcar=False)


def restaurar_do_principal():
    return inicializar_temporario(forcar=True)


def atualizar_slot(formato, slot, alteracoes):
    dados = carregar_temporario()
    destino = dados.setdefault(formato, {}).setdefault(slot, {})
    for chave, valor in alteracoes.items():
        destino[chave] = valor
    _salvar_atomico(AJUSTES_TEMP, dados)
    return copy.deepcopy(destino)


def criar_backup():
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S_%f")
    destino = os.path.join(BACKUPS_DIR, f"ajustes_{timestamp}.json")
    _salvar_atomico(destino, _ler(AJUSTES_PRINCIPAL))
    return destino


def salvar_no_principal():
    dados = carregar_temporario()
    backup = criar_backup()
    _salvar_atomico(AJUSTES_PRINCIPAL, dados)
    return backup

