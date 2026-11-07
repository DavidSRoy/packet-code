#!/usr/bin/env python3
"""Install the laptop Wi-Fi archive as a macOS login service. No drone changes."""
import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

def main():
    if sys.platform != 'darwin':
        raise SystemExit('This installer is for macOS; run flight_sync.py directly elsewhere.')
    root=Path(__file__).resolve().parents[1]
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--host',default='packet@packet-cv.local')
    ap.add_argument('--out',type=Path,default=root/'logs/pi')
    a=ap.parse_args()
    label='com.packet.flight-sync'
    logs=Path.home()/'Library/Logs/Packet';logs.mkdir(parents=True,exist_ok=True)
    agents=Path.home()/'Library/LaunchAgents';agents.mkdir(parents=True,exist_ok=True)
    plist=agents/f'{label}.plist'
    config={'Label':label,'ProgramArguments':[sys.executable,str(root/'tools/flight_sync.py'),
        '--host',a.host,'--frames','--out',str(a.out.resolve())],
        'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':10,
        'StandardOutPath':str(logs/'flight-sync.log'),'StandardErrorPath':str(logs/'flight-sync-error.log')}
    plist.write_bytes(plistlib.dumps(config))
    domain=f'gui/{os.getuid()}'
    subprocess.run(['launchctl','bootout',f'{domain}/{label}'],check=False,capture_output=True)
    subprocess.run(['launchctl','bootstrap',domain,str(plist)],check=True)
    print(f'Installed {label}; archive: {a.out.resolve()}')

if __name__=='__main__':main()
