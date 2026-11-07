#!/usr/bin/env python3
"""Pi flight telemetry recorder. Requests telemetry intervals only while disarmed.

Receives the existing shared MAVLink stream; writes timestamped tlogs with a 5s
pre-arm buffer. Publishes summary.json atomically on disarm, without waiting for
DataFlash. Metrics are FC estimates, NOT independent camera/ground-truth errors.
"""
import os
os.environ.setdefault("MAVLINK20", "1")
import argparse
import bisect
import collections
import json
import math
import struct
import time
from pathlib import Path
from pymavlink import mavutil

class Summary:
    def __init__(self):
        self.error2 = []
        self.volts = []
        self.target = None
        self.targets = []
        self.handover = None
        self.events = []
        self.types = collections.Counter()

    def add(self, msg, now):
        typ = msg.get_type()
        self.types[typ] += 1
        if msg.get_srcSystem() != 1 or msg.get_srcComponent() != 1:
            return
        if typ == 'POSITION_TARGET_LOCAL_NED' and msg.coordinate_frame == 1 and not msg.type_mask & 3:
            self.target = (now, msg.x, msg.y)
            self.targets.append(self.target)
        elif typ == 'LOCAL_POSITION_NED' and self.target and now-self.target[0] < 1:
            e2 = (msg.x-self.target[1])**2+(msg.y-self.target[2])**2
            if math.isfinite(e2):
                self.error2.append(e2)
        elif typ == 'STATUSTEXT':
            self.events.append({'t':now, 'text':msg.text})
            if 'handed over' in msg.text and self.handover is None:
                self.handover = now
        elif typ == 'SYS_STATUS' and 0 < msg.voltage_battery < 65535:
            self.volts.append(msg.voltage_battery/1000)

    def result(self):
        return {'measurement': 'FC estimate versus reported target; includes takeoff and landing',
                'horizontal_rms_m': math.sqrt(sum(self.error2)/len(self.error2)) if self.error2 else None,
                'tracking_samples': len(self.error2),
                'minimum_pack_voltage': min(self.volts) if self.volts else None,
                'message_counts': dict(self.types),
                'events': self.events,
                'limitations': 'Existing telemetry rates only; high-rate IMU and actuator analysis requires DataFlash. Camera truth comparison is separate.'}


def camera_summary(rec_dir, stats, started, ended):
    """Score available CV against received targets, explicitly not independent truth."""
    candidates = []
    for directory in rec_dir.glob('*'):
        try:
            stamp = time.mktime(time.strptime(directory.name, '%Y%m%d-%H%M%S'))
        except ValueError:
            continue
        if abs(stamp-started) < 5:
            candidates.append((abs(stamp-started), directory/'cv.jsonl'))
    if not candidates or not stats.targets or stats.handover is None:
        return {'status':'unavailable', 'reason':'missing matching CV, handover, or target telemetry'}
    path = min(candidates)[1]
    target_times = [row[0] for row in stats.targets]
    errors, times = [], []
    missing = 0
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return {'status':'unavailable', 'reason':'CV recording not yet readable'}
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue  # writer may still be appending the last record
        t = row['t_cap']
        if not stats.handover+1 <= t <= ended:
            continue
        if not row['boxes']:
            missing += 1
            continue
        index = bisect.bisect_right(target_times, t)-1
        if index < 0 or t-target_times[index] > 1:
            continue
        pos = row['boxes'][0]['drone_m']
        target = stats.targets[index]
        error = math.hypot(pos[0]-target[1], -pos[1]-target[2])
        if math.isfinite(error):
            errors.append(error)
            times.append(t)
    if not errors:
        return {'status':'unavailable', 'reason':'no aligned post-handover camera samples'}
    ordered = sorted(errors)
    return {'status':'available', 'samples':len(errors), 'missing_frames':missing,
            'horizontal_rms_m':math.sqrt(sum(e*e for e in errors)/len(errors)),
            'horizontal_p95_m':ordered[min(len(ordered)-1, math.ceil(.95*len(ordered))-1)],
            'horizontal_max_m':max(errors),
            'max_valid_frame_gap_s':max((b-a for a,b in zip(times,times[1:])),default=None),
            'recording':str(path),
            'window':'handover + 1 second through disarm; includes commanded moves and landing',
            'limitations':'Control camera, not independent truth. Targets aligned by Pi receipt time; no latency correction. Latest buffered CV frames may not yet be available.'}


def publish(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--link', default='udpout:127.0.0.1:14650')
    ap.add_argument('--out', type=Path, default=Path.home()/'flight-data'/'telemetry')
    ap.add_argument('--rec-dir', type=Path, default=Path.home()/'rec')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    m = mavutil.mavlink_connection(a.link, source_system=246, source_component=197)
    pre = collections.deque(maxlen=10000)
    active = None
    fp = None
    next_hb = 0
    next_flush = 0
    next_rates = 0
    stats = None
    started = None
    try:
        while True:
            now = time.time()
            if now >= next_hb:
                m.mav.heartbeat_send(18, 8, 0, 0, 4)
                next_hb = now+1
            msg = m.recv_match(blocking=True, timeout=0.1)
            now = time.time()  # actual receive time, not the beginning of a blocking wait
            if msg is None:
                if fp and now >= next_flush:
                    fp.flush()
                    next_flush = now+0.25
                continue
            typ = msg.get_type()
            if typ in ('BAD_DATA', 'LOG_DATA', 'LOG_ENTRY', 'FILE_TRANSFER_PROTOCOL'):
                continue
            record = struct.pack('>Q', int(now*1e6)) + bytes(msg.get_msgbuf())
            is_fc_hb = typ == 'HEARTBEAT' and msg.get_srcSystem() == 1 and msg.get_srcComponent() == 1
            if is_fc_hb:
                armed = bool(msg.base_mode & 128)
                if not armed and now >= next_rates:
                    # Per-link subscriptions; never touch parameters or flight commands.
                    for message_id, hz in ((32,10), (85,10), (1,2), (147,2), (241,5), (36,10), (83,10)):
                        m.mav.command_long_send(1, 1, 511, 0, message_id, int(1e6/hz), 0, 0, 0, 0, 0)
                    next_rates = now+30
                if armed and fp is None:
                    active = a.out / (time.strftime('%Y%m%d-%H%M%S') + f'-{int(now*1000)%1000:03d}')
                    active.mkdir()
                    fp = (active/'telemetry.tlog').open('wb')
                    for stamp, data in pre:
                        if now-stamp <= 5:
                            fp.write(data)
                    started = now
                    stats = Summary()
                    publish(active/'state.json', {'status':'armed', 'started':started})
                    print(f'armed: {active}', flush=True)
            if fp:
                fp.write(record)
                stats.add(msg, now)
                if now >= next_flush:
                    fp.flush()
                    next_flush = now+0.25
                if is_fc_hb and not armed:
                    fp.close()
                    fp = None
                    report = stats.result() | {'started':started, 'landed':now, 'status':'disarmed', 'duration_s':now-started}
                    report['camera_tracking'] = camera_summary(a.rec_dir, stats, started, now)
                    publish(active/'summary.json', report)
                    publish(active/'state.json', {'status':'disarmed', 'started':started, 'ended':now})
                    print(f'disarmed: summary ready {active}', flush=True)
            pre.append((now, record))
            while pre and now-pre[0][0] > 5:
                pre.popleft()
            # Never infer landing from heartbeat loss: an interrupted flight stays unfinalized.
    finally:
        if fp:
            fp.close()
        m.close()

if __name__ == '__main__':
    main()
