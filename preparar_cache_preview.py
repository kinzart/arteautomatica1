#!/usr/bin/env python
"""Extrai do PSD os ativos estáticos usados pelo preview rápido."""
import json
import os

from fbs import config

CACHE_DIR = os.path.join(config.ROOT, "cache_preview")
BASE_PATH = os.path.join(CACHE_DIR, "base_feed.png")
SLOTS_PATH = os.path.join(CACHE_DIR, "slots_feed.json")
MASCARA_PATH = os.path.join(CACHE_DIR, "mascara_foto_feed.png")


def _serializar_meta(meta):
    return {
        "slot": str(meta["slot"]),
        "bbox": [int(v) for v in meta["bbox"]],
        "kind": str(meta.get("kind", "type")),
        "opacity": int(meta.get("opacity", 255)),
        "text": str(meta.get("text", "")),
        "tracking": float(meta.get("tracking", 0)),
        "cor_rgb": [int(v) for v in meta.get("cor_rgb", (243, 238, 227))],
    }


def preparar_cache(force=False):
    psd_path = config.TEMPLATE_FILES["feed"]
    arquivos = (BASE_PATH, SLOTS_PATH, MASCARA_PATH)
    if not force and all(os.path.isfile(p) for p in arquivos):
        try:
            with open(SLOTS_PATH, "r", encoding="utf-8") as arquivo:
                json.load(arquivo)
            cache_mtime = min(os.path.getmtime(p) for p in arquivos)
            if cache_mtime >= os.path.getmtime(psd_path):
                return arquivos
        except (OSError, json.JSONDecodeError):
            pass

    os.makedirs(CACHE_DIR, exist_ok=True)
    from psd_tools import PSDImage
    from fbs import psd_reader
    psd = PSDImage.open(psd_path)
    variaveis = psd_reader.extrair_variaveis(psd)
    foto_layer = variaveis["foto_artista"]["layer_ref"]
    mascara = psd_reader.extrair_mascara_camada(foto_layer)
    if mascara is None:
        raise RuntimeError("A camada foto_artista do PSD não possui máscara para o cache rápido")
    mascara.save(MASCARA_PATH)

    slots = {slot: _serializar_meta(meta) for slot, meta in variaveis.items() if slot != "foto_artista"}
    extras = {}
    grupos_ocultar = {"ENDERECO", "LINHAS", "ENTRADA GRATUITA", "COM BEBECO BLUES BAND"}
    for layer in psd.descendants():
        if layer.is_group() and layer.name in grupos_ocultar:
            if layer.name == "ENDERECO":
                textos = [item for item in layer if item.kind == "type"]
                for item in textos:
                    if "GETHER" in item.name.upper():
                        extras["txt_local_nome"] = _serializar_meta(psd_reader.meta_texto(item, "txt_local_nome"))
                    elif "MORRO" in item.name.upper():
                        extras["txt_local_bairro"] = _serializar_meta(psd_reader.meta_texto(item, "txt_local_bairro"))
                    else:
                        extras["txt_local_endereco"] = _serializar_meta(psd_reader.meta_texto(item, "txt_local_endereco"))
            layer.visible = False
    for meta in variaveis.values():
        meta["layer_ref"].visible = False
    base = psd.composite().convert("RGB")
    base.info.pop("icc_profile", None)
    base.save(BASE_PATH)

    dados = {
        "canvas": [int(psd.width), int(psd.height)],
        "foto_bbox": [int(v) for v in variaveis["foto_artista"]["bbox"]],
        "slots": {**slots, **extras},
        "fixos": {
            "logo_bbox": [62, 55, 256, 218],
            "floripa_xy": [200, 50],
            "entrada_bbox": [897, 361, 1039, 414],
            "banda_bbox": [53, 665, 444, 722],
            "linhas": [[53, 1167, 369, 1170], [408, 1166, 787, 1171]],
        },
        "psd_mtime": os.path.getmtime(psd_path),
    }
    slots_tmp = SLOTS_PATH + ".tmp"
    with open(slots_tmp, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")
    os.replace(slots_tmp, SLOTS_PATH)
    return arquivos


def main():
    preparar_cache(force=True)
    print(f"Cache de preview criado em: {CACHE_DIR}")


if __name__ == "__main__":
    main()
