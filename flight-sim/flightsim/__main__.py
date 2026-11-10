import argparse
import sys
import time
from collections.abc import Sequence

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
    args = parser.parse_args(list(argv))
    name = args.name or time.strftime("hover-%Y%m%d-%H%M%S")
    run = HoverRun(args.camera, args.compute, args.height, args.hold, args.seed, name)
    try:
        folder = run_hover(load_cluster(), run)
    except (RemoteError, FileNotFoundError) as exc:
        print(exc, file=sys.stderr)
        return 1
    print(folder)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
