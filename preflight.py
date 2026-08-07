#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from preflight_utils import run_preflight


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ejecuta el diagnóstico previo de Smart Home UI Manager"
    )
    parser.add_argument("catalog", type=Path)
    parser.add_argument(
        "--mode",
        default="MANTENIMIENTO",
        choices=("MANTENIMIENTO", "SOLO DIAGNÓSTICO"),
    )
    args = parser.parse_args()

    summary = run_preflight(args.catalog, mode=args.mode)

    if summary.report_path is not None:
        print(
            f"[preflight] Reporte guardado: {summary.report_path}",
            flush=True,
        )
    if summary.latest_path is not None:
        print(
            f"[preflight] Último reporte: {summary.latest_path}",
            flush=True,
        )

    print(f"[preflight] Resultado: {summary.result}", flush=True)
    print(f"[preflight] Fallos críticos: {summary.failures}", flush=True)
    print(f"[preflight] Advertencias: {summary.warnings}", flush=True)

    return 1 if summary.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
