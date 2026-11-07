#!/usr/bin/env python3
"""Mirror Pi analysis data over Wi-Fi every 2s; never touches the flight radio.

python tools/flight_sync.py --host packet@packet-cv.local --out logs/pi
Telemetry/CV summaries transfer first; large JPEGs are optional (--frames).
Retries disconnected Wi-Fi. Pi remains the source of record. No remote deletion.
"""
import argparse
import concurrent.futures
import subprocess
import time
from pathlib import Path

def sync(host, remote, local, filters=(), compress=True):
    local.mkdir(parents=True, exist_ok=True)
    subprocess.run(['rsync','-a',*(['-z'] if compress else []),'--partial','--timeout=10','--bwlimit=1500',
                    '-e','ssh -o ConnectTimeout=5 -o BatchMode=yes',*filters,
                    f'{host}:{remote}/',str(local)+'/'], check=True, timeout=60)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--host', default='packet@packet-cv.local')
    ap.add_argument('--out', type=Path, default=Path('logs/pi'))
    ap.add_argument('--frames', action='store_true')
    ap.add_argument('--once', action='store_true')
    a=ap.parse_args()
    seen=set()
    def bulk():
        sync(a.host, '/home/packet/flight-data/bin', a.out/'bin', ('--exclude=*.part*',))
        if a.frames:
            sync(a.host, '/home/packet/rec', a.out/'rec', ('--exclude=cv.jsonl',), compress=False)
    pool=concurrent.futures.ThreadPoolExecutor(max_workers=1)
    transfer=None
    while True:
        try:
            sync(a.host, '/home/packet/flight-data/telemetry', a.out/'telemetry')
            sync(a.host, '/home/packet/rec', a.out/'rec', ('--exclude=frames/',))
            for report in sorted((a.out/'telemetry').glob('*/summary.json')):
                if report not in seen:
                    print(f'Flight summary ready: {report}', flush=True)
                    seen.add(report)
            if transfer is None or transfer.done():
                if transfer is not None:
                    try:transfer.result()
                    except (subprocess.SubprocessError,OSError) as exc:print(f'Bulk sync retry: {exc}',flush=True)
                transfer=pool.submit(bulk)
        except (subprocess.SubprocessError, OSError) as exc:
            print(f'Sync retry: {exc}', flush=True)
            if a.once:
                raise
        if a.once:
            if transfer:transfer.result()
            pool.shutdown()
            break
        time.sleep(2)

if __name__ == '__main__':
    main()
