#!/usr/bin/env python
import argparse
import os

from fbs import config
from fbs.visual_compare import comparar


def main():
    parser = argparse.ArgumentParser(description="Compara um PNG com o gold master FBS")
    parser.add_argument("gerado", nargs="?", default=os.path.join(config.OUTPUTS_DIR, "fbs27_feed.png"))
    parser.add_argument("--referencia", default=os.path.join(config.ASSETS, "referencias", "fbs_goldmaster.png"))
    parser.add_argument("--diff", default=os.path.join(config.OUTPUTS_DIR, "_diff_goldmaster.png"))
    args = parser.parse_args()
    metricas = comparar(args.gerado, args.referencia, args.diff)
    print(f"Diferença média: {metricas['diferenca_media']:.4f}/255")
    if metricas["ssim"] is not None:
        print(f"SSIM: {metricas['ssim']:.6f}")
    print(f"Diff: {args.diff}")


if __name__ == "__main__":
    main()

