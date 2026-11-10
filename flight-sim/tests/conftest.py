import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[2] / "backend"

for _dir in (
    _BACKEND,
    _BACKEND / "companion",
    _BACKEND / "tools" / "sim",
    _BACKEND / "tools" / "sim" / "hover",
):
    if str(_dir) not in sys.path:
        sys.path.append(str(_dir))
