"""Persistência segura para o editor visual de ajustes."""
from __future__ import annotations

import copy
import datetime as dt
import json
import math
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


def _normalizar_temporario(dados):
    """Migra formatos antigos sem perder o estado de calibração do editor."""
    resultado = copy.deepcopy(dados)
    for formato, slots in resultado.items():
        if not isinstance(slots, dict):
            continue
        for ajuste in slots.values():
            if not isinstance(ajuste, dict):
                continue
            cor = ajuste.get("cor")
            if isinstance(cor, str):
                cor = cor.strip().upper()
                if len(cor) == 4 and cor.startswith("#"):
                    cor = "#" + "".join(c * 2 for c in cor[1:])
                ajuste["cor"] = cor
        foto = slots.get("foto_artista")
        if formato == "feed" and isinstance(foto, dict):
            zoom = foto.get("zoom")
            if isinstance(zoom, (int, float)) and not isinstance(zoom, bool) and zoom < 1:
                # O compositor antigo ampliava escondido para acomodar o pan.
                # Congele essa escala efetiva em centésimos antes de separar os
                # controles. ceil garante que o offset existente continue cabendo.
                try:
                    offset_x = float(foto.get("offset_x", 0))
                    offset_y = float(foto.get("offset_y", 0))
                except (TypeError, ValueError):
                    offset_x = offset_y = 0
                necessario = max(
                    1.0,
                    1.0 + 2.0 * abs(offset_x) / 831,
                    1.0 + 2.0 * abs(offset_y) / 1136,
                )
                foto["zoom"] = math.ceil(necessario * 100) / 100
    return resultado


def inicializar_temporario(forcar=False):
    if forcar or not os.path.isfile(AJUSTES_TEMP):
        _salvar_atomico(AJUSTES_TEMP, _ler(AJUSTES_PRINCIPAL))
    dados = _ler(AJUSTES_TEMP)
    normalizados = _normalizar_temporario(dados)
    if normalizados != dados:
        _salvar_atomico(AJUSTES_TEMP, normalizados)
    else:
        # Detecta temporários inválidos já na abertura, antes de iniciar render.
        ajustes_mod.carregar_ajustes(AJUSTES_TEMP)
    return normalizados


def carregar_temporario():
    return inicializar_temporario(forcar=False)


def restaurar_do_principal():
    return inicializar_temporario(forcar=True)


def substituir_temporario(dados):
    _salvar_atomico(AJUSTES_TEMP, dados)
    return _ler(AJUSTES_TEMP)


def restaurar_feed_psd():
    """Remove overrides do feed; o próximo render herda a geometria do PSD."""
    dados = carregar_temporario()
    dados["feed"] = {}
    return substituir_temporario(dados)


def atualizar_slot(formato, slot, alteracoes):
    dados = carregar_temporario()
    destino = dados.setdefault(formato, {}).setdefault(slot, {})
    for chave, valor in alteracoes.items():
        destino[chave] = valor
    _salvar_atomico(AJUSTES_TEMP, dados)
    return copy.deepcopy(destino)


def criar_backup():
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino = os.path.join(BACKUPS_DIR, f"ajustes_{timestamp}.json")
    _salvar_atomico(destino, _ler(AJUSTES_PRINCIPAL))
    return destino


def salvar_no_principal():
    dados = carregar_temporario()
    backup = criar_backup()
    _salvar_atomico(AJUSTES_PRINCIPAL, dados)
    return backup
