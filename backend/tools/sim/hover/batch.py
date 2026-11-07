#!/usr/bin/env python3
"""Run several hover simulations in parallel and print one table.

  python tools/sim/hover/batch.py CONFIG.json [--jobs 6] [--compare-real LOG.BIN]

CONFIG.json: a list of runs, each {"name", optional "flown", "set": [...], "p": [...], "parm": [...],
"seed", "height", "hold"} (the run.py options). Results stay in runs/<name>/result.json.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent


def cmd_for(c, inst, speedup):
    a = [sys.executable, str(HERE / "run.py"), "--name", c["name"], "--instance", str(inst), "--speedup", str(speedup),
         "--hold", str(c.get("hold", 30)), "--height", str(c.get("height", 0.02)), "--seed", str(c.get("seed", 1))]
    if c.get("flown"):
        a += ["--flown", c["flown"]]
    if c.get("custom_control"):
        a += ["--custom-control"]
    for k, flag in (("set", "--set"), ("p", "--p"), ("parm", "--parm")):
        for v in c.get(k, []):
            a += [flag, v]
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--speedup", type=int, default=4)
    ap.add_argument("--compare", action="store_true", help="also run compare.py on the dataflash logs")
    ap.add_argument("--real", default=None, help="real log for the compare table")
    a = ap.parse_args()
    cfgs = json.load(open(a.config))
    # instance I uses ports 5760+10I..5762+10I and 9002+10I: instance 14 (5900) is the macOS screen sharing port
    queue, running, free = list(cfgs), {}, [i for i in range(a.jobs + 1) if i != 14][: a.jobs]
    t0 = time.time()
    while queue or running:
        while queue and free:
            c = queue.pop(0)
            inst = free.pop(0)
            running[c["name"]] = (subprocess.Popen(cmd_for(c, inst, a.speedup), stdout=subprocess.DEVNULL,
                                                   stderr=subprocess.DEVNULL), inst)
        for n, (p, inst) in list(running.items()):
            if p.poll() is not None:
                del running[n]
                free.append(inst)
        time.sleep(1)
    print(f"{len(cfgs)} runs in {time.time() - t0:.0f} s")
    keys = ("xy_rms_mm", "xy_p95_mm", "xy_max_mm", "x_mean_mm", "y_mean_mm", "z_rms_mm", "z_max_mm", "tilt_rms_deg",
            "tilt_hp_rms_deg", "tilt_hp_p99_deg", "rate_hp_rms_dps", "tilt_peak_hz", "settle10_s")
    print(f"{'run':<28}{'status':<10}" + "".join(f"{k[:12]:>13}" for k in keys))
    logs = []
    for c in cfgs:
        f = HERE / "runs" / c["name"] / "result.json"
        if not f.exists():
            print(f"{c['name']:<28}no result")
            continue
        r = json.load(open(f))
        s = r.get("score") or {}
        print(f"{c['name']:<28}{r.get('status', '?')[:9]:<10}" + "".join(f"{(s.get(k) if s.get(k) is not None else float('nan')):>13.2f}" for k in keys))
        if r.get("dflog"):
            logs.append(r["dflog"])
    if a.compare and logs:
        out = subprocess.run([sys.executable, str(HERE / "compare.py")] + ([a.real] if a.real else []) + logs,
                             capture_output=True, text=True).stdout
        print(out)


if __name__ == "__main__":
    main()
