#!/usr/bin/env python
"""Calibra a âncora de rosto pra cada template PSD em assets/templates/
(HANDOFF_v4 §2.2/§5). `gerar.py` já chama isso sozinho antes de gerar (e
recalibra automático se o PSD for mais novo que o .anchor.json) — rodar
esse script manualmente serve só pra inspecionar o resultado ou forçar uma
recalibração adiantada.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fbs import config, face, util


def main():
    logger = util.configurar_log()
    for formato in config.TEMPLATE_FILES:
        psd_path = config.TEMPLATE_FILES[formato]
        if not os.path.isfile(psd_path):
            print(f"{formato}: template não encontrado ({psd_path}) — pulando")
            continue
        dados = face.calibrar_se_necessario(formato, logger=logger)
        if dados is None:
            print(f"{formato}: rosto não detectado na foto original — sem âncora (fallback fit_cover)")
        else:
            print(
                f"{formato}: ancora_x_rel={dados['ancora_x_rel']:.3f} "
                f"ancora_y_rel={dados['ancora_y_rel']:.3f} "
                f"altura_rosto_px={dados['altura_rosto_px']:.1f}"
            )


if __name__ == "__main__":
    main()
