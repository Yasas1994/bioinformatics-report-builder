"""Command-line interface for bioinformatics-report-builder."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path


def _render_command(args: argparse.Namespace) -> int:
    qmd = Path(args.qmd)
    if not qmd.exists():
        print(f"error: qmd file not found: {qmd}", file=sys.stderr)
        return 1

    cmd = ["quarto", "render", str(qmd), "--to", args.to]
    if args.output_dir:
        cmd.extend(["--output-dir", str(args.output_dir)])
    if args.output:
        cmd.extend(["--output", str(args.output)])

    return subprocess.call(cmd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bioinformatics-report",
        description="Build and render bioinformatics-report-builder reports.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    render = subparsers.add_parser("render", help="render a generated .qmd report")
    render.add_argument("qmd", type=Path, help="path to the .qmd file")
    render.add_argument(
        "--to",
        choices=["html", "pdf"],
        default="html",
        help="output format (default: html)",
    )
    render.add_argument(
        "--output-dir",
        type=Path,
        help="directory for rendered output",
    )
    render.add_argument(
        "--output",
        type=Path,
        help="output file name",
    )
    render.set_defaults(func=_render_command)

    args = parser.parse_args(argv)
    func: Callable[[argparse.Namespace], int] = args.func
    return func(args)


if __name__ == "__main__":
    sys.exit(main())
