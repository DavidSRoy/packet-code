#!/usr/bin/env python3
"""Pipelined, resumable MAVFTP log reads through the shared Pi link.

ReadFile requests (239 bytes), at most 4 outstanding. No unbounded burst.
Uses FC LOG_ENTRY inventory, verifies FTP size and full byte coverage before
publishing .BIN. Pauses and reopens its session after arming/heartbeat loss.
"""
import os
os.environ.setdefault('MAVLINK20','1')
import argparse
import hashlib
import json
import struct
import time
import zlib
from pathlib import Path
from pymavlink import mavutil
from log_download import Link

class FTP:
    def __init__(self, link):
        self.link=link
        self.seq=int(time.time()*1000)%60000
        self.last_payload=None
    def send(self, op, session=0, offset=0, size=0, data=b''):
        self.seq=(self.seq+2)%65536
        payload=struct.pack('<HBBBBBBI',self.seq,session,op,size,0,0,0,offset)+data
        self.last_payload=payload.ljust(251,b'\0')
        self.link.m.mav.file_transfer_protocol_send(0,1,1,self.last_payload)
        return (self.seq+1)%65536
    def receive(self):
        m=self.link.receive(.01)
        if m and m.get_type()=='FILE_TRANSFER_PROTOCOL' and m.target_system==246 and m.target_component==196:
            h=struct.unpack('<HBBBBBBI',bytes(m.payload[:12]))
            return h,bytes(m.payload[12:12+h[3]])
        return None
    def control(self, op):
        self.link.wait_safe()
        seq=self.send(op)
        payload=self.last_payload
        for _ in range(10):
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                got=self.receive()
                if got and got[0][0]==seq and got[0][4]==op:
                    if got[0][2]!=128:raise RuntimeError(f'FTP control {op} failed')
                    return
            self.link.m.mav.file_transfer_protocol_send(0,1,1,payload)
        raise RuntimeError(f'FTP control {op} acknowledgement timed out')

    def open(self, path):
        self.link.wait_safe()
        seq=self.send(4,size=len(path),data=path.encode())
        payload=self.last_payload
        for attempt in range(10):
            deadline=time.monotonic()+2
            while time.monotonic()<deadline and self.link.safe():
                got=self.receive()
                if got and got[0][0]==seq and got[0][4]==4:
                    h,data=got
                    if h[2]!=128:raise RuntimeError(f'FTP open failed {path}: {data!r}')
                    return h[1],struct.unpack('<I',data[:4])[0]
            if not self.link.safe():
                self.link.wait_safe()
                self.control(2)
                return self.open(path)
            # Opening is not idempotent: retry the identical request so FC can
            # resend its cached ACK instead of trying to open an already-open fd.
            self.link.m.mav.file_transfer_protocol_send(0,1,1,payload)
        raise RuntimeError(f'FTP open timed out: {path}')

    def crc(self, path):
        self.link.wait_safe()
        seq=self.send(14,size=len(path),data=path.encode())
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            got=self.receive()
            if got and got[0][0]==seq and got[0][4]==14:
                if got[0][2]!=128 or len(got[1])!=4:
                    raise RuntimeError('FC file checksum unavailable')
                return struct.unpack('<I',got[1])[0]
        raise RuntimeError('FC file checksum timed out')

def download(ftp,lid,expected,out):
    path=f'/APM/LOGS/{lid:08d}.BIN'
    dest=out/f'{lid:08d}.BIN'
    part=dest.with_suffix('.ftp.part')
    manifest=dest.with_suffix('.json')
    session,size=ftp.open(path)
    try:
        if size!=expected:raise RuntimeError(f'log {lid}: inventory {expected} differs from FTP {size}; may still be open')
        if dest.exists() and manifest.exists():
            meta=json.loads(manifest.read_text())
            if meta.get('size')==size and hashlib.sha256(dest.read_bytes()).hexdigest()==meta.get('sha256') and meta.get('fc_crc32')==ftp.crc(path):
                print(f'log {lid}: verified existing',flush=True);return
        # Durable contiguous prefix; at most 64 KiB is re-read after interruption.
        offset=part.stat().st_size if part.exists() else 0
        if offset>size or (offset!=size and offset%239):
            part.write_bytes(b'');offset=0
        start=time.monotonic();reported=offset
        with part.open('ab') as f:
            while offset<size:
                if not ftp.link.safe():
                    ftp.send(1,session)
                    ftp.link.wait_safe()
                    ftp.control(2)
                    session,newsize=ftp.open(path)
                    if newsize!=size:raise RuntimeError('file changed while paused')
                end=min(offset+239*256,size)
                pieces={}
                todo=[pos for pos in range(offset,end,239) if pos not in pieces]
                pending={};retries={}
                while todo or pending:
                    if not ftp.link.safe():
                        # Incomplete window is retried after the FC is disarmed again.
                        break
                    while todo and len(pending)<4:
                        pos=todo.pop(0)
                        seq=ftp.send(5,session,pos,min(239,size-pos))
                        pending[seq]=(pos,time.monotonic())
                    got=ftp.receive()
                    if got:
                        h,data=got
                        if h[0] in pending and h[1]==session and h[4]==5:
                            pos,_=pending.pop(h[0])
                            if h[2]!=128 or h[7]!=pos or len(data)!=min(239,size-pos):
                                raise RuntimeError(f'log {lid}: invalid FTP reply at {pos}: {h}, {data!r}')
                            pieces[pos]=data
                    now=time.monotonic()
                    for seq,(pos,sent) in list(pending.items()):
                        if now-sent>.25:
                            pending.pop(seq)
                            retries[pos]=retries.get(pos,0)+1
                            if retries[pos]>120:raise RuntimeError(f'log {lid}: retries exhausted at {pos}')
                            todo.append(pos)
                if len(pieces)!=len(range(offset,end,239)):
                    continue
                for pos in sorted(pieces):f.write(pieces[pos])
                f.flush();offset=end
                if offset-reported>=1_000_000:
                    print(f'log {lid}: {offset}/{size} ({(offset-reported)/1e3:.0f} KB block)',flush=True);reported=offset
        remote_crc=ftp.crc(path)
        local_crc=zlib.crc32(part.read_bytes(),0xffffffff)^0xffffffff
        if local_crc!=remote_crc:
            part.unlink()
            raise RuntimeError(f'log {lid}: checksum mismatch; discarded partial copy')
        part.replace(dest)
        manifest.write_text(json.dumps({'id':lid,'size':size,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'transport':'MAVFTP ReadFile', 'fc_crc32':remote_crc},indent=2))
        print(f'log {lid}: COMPLETE {size} bytes in {time.monotonic()-start:.1f}s',flush=True)
    finally:ftp.send(1,session)

def bench_download(link, lid, expected, out):
    """Library-managed full-file burst, for disarmed maintenance only."""
    from pymavlink.mavftp import MAVFTP
    path=f'/APM/LOGS/{lid:08d}.BIN'
    dest=out/f'{lid:08d}.BIN'
    manifest=dest.with_suffix('.json')
    if dest.exists() and manifest.exists():
        meta=json.loads(manifest.read_text())
        if meta.get('size')==expected and hashlib.sha256(dest.read_bytes()).hexdigest()==meta.get('sha256') and meta.get('fc_crc32')==FTP(link).crc(path):
            print(f'log {lid}: verified existing',flush=True);return
    link.wait_safe()
    def observe(conn, msg):
        now=time.monotonic()
        if now>=link.next_hb:
            conn.mav.heartbeat_send(6,8,0,0,4);link.next_hb=now+1
        if msg.get_type()=='HEARTBEAT' and msg.get_srcSystem()==1 and msg.get_srcComponent()==1:
            link.hb=now;link.armed=bool(msg.base_mode&128)
        if link.armed or now-link.hb>10:raise RuntimeError('bench transfer interrupted: armed or FC heartbeat absent for 10s')
    link.m.message_hooks.append(observe)
    stage=dest.with_suffix('.library.part')
    start=time.monotonic()
    try:
        client=MAVFTP(link.m,1,1)
        client.ftp_settings.burst_read_size=239;client.burst_size=239
        client.ftp_settings.read_retry_time=.25;client.ftp_settings.max_backlog=4
        client.cmd_get([path,str(stage)])
        result=client.process_ftp_reply('OpenFileRO',timeout=max(600,expected/10000))
        if result.error_code or not stage.exists() or stage.stat().st_size!=expected:
            raise RuntimeError(f'log {lid}: library transfer incomplete ({result.error_code})')
    finally:
        link.m.message_hooks.remove(observe)
    ftp=FTP(link)
    remote_crc=ftp.crc(path)
    local_crc=zlib.crc32(stage.read_bytes(),0xffffffff)^0xffffffff
    if remote_crc!=local_crc:raise RuntimeError(f'log {lid}: FC checksum mismatch')
    stage.replace(dest)
    manifest.write_text(json.dumps({'id':lid,'size':expected,'fc_crc32':remote_crc,
        'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'transport':'MAVFTP burst'},indent=2))
    print(f'log {lid}: COMPLETE, FC CRC verified, {expected} bytes in {time.monotonic()-start:.1f}s',flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,default=Path.home()/'flight-data'/'bin')
    ap.add_argument('--first',type=int,default=1)
    ap.add_argument('--latest',type=int,default=0)
    ap.add_argument('--bench-burst',action='store_true',help='disarmed maintenance only; up to 478 KB already queued when arm is detected')
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    m=mavutil.mavlink_connection('udpout:127.0.0.1:14650',source_system=246,source_component=196)
    link=Link(m);link.wait_safe();m.mav.log_request_end_send(1,1)
    entries={};total=None
    for _ in range(5):
        link.wait_safe();m.mav.log_request_list_send(1,1,0,65535)
        end=time.monotonic()+5
        while time.monotonic()<end and link.safe():
            e=link.receive()
            if e and e.get_type()=='LOG_ENTRY':entries[e.id]=e.size;total=e.num_logs
            if total is not None and len(entries)==total:break
        if total is not None and len(entries)==total:break
    m.mav.log_request_end_send(1,1)
    if total is None or len(entries)!=total:raise RuntimeError('incomplete FC log inventory')
    print('inventory',json.dumps(entries),flush=True)
    ftp=FTP(link)
    ftp.control(2)  # await reset of this client's interrupted prior session
    failures=[]
    selected=sorted(entries,reverse=True)
    if a.latest:selected=selected[:a.latest]
    for lid in selected:
        if lid<a.first:continue
        try:
            if a.bench_burst:bench_download(link,lid,entries[lid],a.out)
            else:download(ftp,lid,entries[lid],a.out)
        except RuntimeError as exc:print(str(exc),flush=True);failures.append(lid)
    m.close()
    if failures:raise SystemExit(f'incomplete logs: {failures}')

if __name__=='__main__':main()
