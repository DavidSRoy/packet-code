"""Check radio_levels (server.py) against RADIO_STATUS values from the 2026-10-29 flight logs.

Run from backend/:  .venv/bin/python ground_control/test_radio_levels.py
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))
from server import radio_levels  # noqa: E402

# in flight (log 144111): the laptop radio reports 125 / 73, the drone radio 126 / 60
r = radio_levels(SimpleNamespace(rssi=125, noise=73, remrssi=126, remnoise=60, rxerrors=271))
assert (r["gnd_db"], r["gnd_noise"], r["air_db"], r["air_noise"], r["rxerrors"]) == (27.4, -89, 34.7, -95, 271), r
# no report from the drone radio (log 130428): the drone side is unknown, not "0 dB"
r = radio_levels(SimpleNamespace(rssi=55, noise=54, remrssi=0, remnoise=0, rxerrors=6))
assert (r["gnd_db"], r["gnd_noise"], r["air_db"], r["air_noise"]) == (0.5, -99, None, None), r
print("radio_levels: 2 checks passed")
