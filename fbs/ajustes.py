"""Carrega ajustes.json — overrides opcionais de tamanho/posição/textura por
slot, pra afinar o resultado sem precisar editar o PSD (BRIEF_v3 é PSD-driven
por padrão; isso é uma via de escape deliberada pra iteração rápida)."""
import json
import os

from . import config

AJUSTES_PATH = os.path.join(config.ROOT, "ajustes.json")

CAMPOS_TEXTO = {
    "tamanho", "tamanho_max", "tamanho_min", "tracking", "espacamento_linhas",
    "offset_x", "offset_y", "caixa_largura", "caixa_altura", "alinhamento",
    "cor", "opacidade", "textura", "textura_opacidade", "textura_blend",
    "quebrar_linhas", "escala_x", "escala_y", "fonte", "desgaste",
    "caixa_x", "ajustar_tracking", "preenchimento_largura", "layout_artista_auto",
    "gap_linhas_min",
}
CAMPOS_FOTO = {
    "zoom", "offset_x", "offset_y", "brilho", "contraste", "saturacao",
    "nitidez", "temperatura", "fusao_frac", "mascara_offset_x",
    "mascara_offset_y", "mascara_escala", "mascara_blur",
    "mascara_contraste", "mascara_opacidade", "mascara_inverter",
}
CAMPOS_GLOBAL = {"grain_opacidade", "bordas_opacidade", "brilho", "contraste", "saturacao"}
CAMPOS_LINHAS = {"offset_x", "offset_y", "largura_1", "largura_2", "espessura", "cor"}


def carregar_ajustes(caminho=None):
    """Retorna {formato: {slot: {...overrides...}}}. Vazio se o arquivo não existir."""
    caminho = caminho or AJUSTES_PATH
    if not os.path.isfile(caminho):
        return {}
    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)
    for formato, slots in dados.items():
        if not isinstance(slots, dict):
            raise ValueError(f"ajustes.{formato} deve ser um objeto")
        for slot, ajuste in slots.items():
            if not isinstance(ajuste, dict):
                raise ValueError(f"ajustes.{formato}.{slot} deve ser um objeto")
            permitidos = (CAMPOS_GLOBAL if slot == "global" else
                          CAMPOS_LINHAS if slot == "linhas_rodape" else
                          CAMPOS_FOTO if slot == "foto_artista" else CAMPOS_TEXTO)
            desconhecidos = set(ajuste) - permitidos
            if desconhecidos:
                raise ValueError(f"ajustes.{formato}.{slot}: comandos desconhecidos: {sorted(desconhecidos)}")
            tamanho = ajuste.get("tamanho")
            if tamanho is not None and (not isinstance(tamanho, int) or isinstance(tamanho, bool) or tamanho <= 0):
                raise ValueError(f"ajustes.{formato}.{slot}.tamanho deve ser um inteiro positivo")
            tracking = ajuste.get("tracking")
            if tracking is not None and (not isinstance(tracking, (int, float)) or isinstance(tracking, bool)):
                raise ValueError(f"ajustes.{formato}.{slot}.tracking deve ser um número")
            cor = ajuste.get("cor")
            if cor is not None and (
                not isinstance(cor, str) or len(cor) != 7 or not cor.startswith("#")
                or any(c not in "0123456789abcdefABCDEF" for c in cor[1:])
            ):
                raise ValueError(f"ajustes.{formato}.{slot}.cor deve usar #RRGGBB")
            for campo_opacidade in (
                "opacidade", "textura_opacidade", "mascara_opacidade",
                "grain_opacidade", "bordas_opacidade", "desgaste",
            ):
                valor_opacidade = ajuste.get(campo_opacidade)
                if valor_opacidade is not None and (
                    not isinstance(valor_opacidade, (int, float))
                    or isinstance(valor_opacidade, bool) or not 0 <= valor_opacidade <= 1
                ):
                    raise ValueError(
                        f"ajustes.{formato}.{slot}.{campo_opacidade} deve ficar entre 0 e 1"
                    )
            espacamento = ajuste.get("espacamento_linhas")
            if espacamento is not None and (not isinstance(espacamento, (int, float)) or isinstance(espacamento, bool) or espacamento <= 0):
                raise ValueError(f"ajustes.{formato}.{slot}.espacamento_linhas deve ser um número positivo")
            if slot == "foto_artista" and "zoom" in ajuste:
                zoom = ajuste["zoom"]
                if not isinstance(zoom, (int, float)) or isinstance(zoom, bool) or not 0 < zoom <= 5:
                    raise ValueError(
                        f"ajustes.{formato}.foto_artista.zoom deve ficar entre 0 e 5; "
                        "use 1.6 para ampliar 60%"
                    )
    return dados


def ajuste_do_slot(ajustes, formato, slot):
    return ajustes.get(formato, {}).get(slot, {})
