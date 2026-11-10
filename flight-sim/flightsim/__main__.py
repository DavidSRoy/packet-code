import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from flightsim.bootstrap import run_bootstrap
from flightsim.compare import compare, describe, summarize
from flightsim.config import load_cluster
from flightsim.hover import HoverRun, run_hover
from flightsim.remote import RemoteError


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m flightsim")
    commands = parser.add_subparsers(dest="command", required=True)
    hover = commands.add_parser("hover", help="closed-loop hover on Isaac frames, run on the cluster")
    hover.add_argument("--camera", required=True, help="profile name in profiles/cameras")
    hover.add_argument("--compute", required=True, help="profile name in profiles/compute")
    hover.add_argument("--height", type=float, required=True, help="hover height above the start, m")
    hover.add_argument("--hold", type=float, required=True, help="hold time at height, s")
    hover.add_argument("--seed", type=int, default=0)
    hover.add_argument("--name", help="run name; default hover-<timestamp>")
    commands.add_parser("bootstrap", help="prepare the cluster: images, ArduPilot build, Python environment (idempotent)")
    cmp = commands.add_parser("compare", help="differences between two result folders (B minus A)")
    cmp.add_argument("a", type=Path)
    cmp.add_argument("b", type=Path)
    args = parser.parse_args(list(argv))
    if args.command == "compare":
        try:
            sa, sb, diff = summarize(args.a), summarize(args.b), compare(args.a, args.b)
        except (FileNotFoundError, ValueError) as exc:
            print(exc, file=sys.stderr)
            return 1
        for label, folder in (("A", args.a), ("B", args.b)):
            status, in_hold = describe(folder)
            print(f"{label}: {status}; detection over {'the hold window' if in_hold else 'all frames (no hold)'}")
        for key in diff:
            print(f"{key:15s} A {sa[key]:9.3f}  B {sb[key]:9.3f}  B-A {diff[key]:9.3f}")
        return 0
    if args.command == "bootstrap":
        try:
            folder = run_bootstrap(load_cluster())
        except (RemoteError, FileNotFoundError) as exc:
            print(exc, file=sys.stderr)
            return 1
        print(folder)
        return 0
    name = args.name or time.strftime("hover-%Y%m%d-%H%M%S")
    run = HoverRun(args.camera, args.compute, args.height, args.hold, args.seed, name)
    try:
        folder = run_hover(load_cluster(), run)
    except (RemoteError, FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(folder)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
