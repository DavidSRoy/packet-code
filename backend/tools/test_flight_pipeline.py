import importlib.util
import json
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from pymavlink import mavutil

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
ld = module('log_download', ROOT/'tools/log_download.py')
sys.modules['log_download']=ld
fd = module('ftp_download', ROOT/'tools/ftp_download.py')
fr = module('flight_recorder', ROOT/'companion/flight_recorder.py')

class Message:
    def __init__(self, typ, **kw):
        self.typ = typ
        self.__dict__.update(kw)
    def get_type(self): return self.typ
    def get_srcSystem(self): return 1
    def get_srcComponent(self): return 1

class PipelineTests(unittest.TestCase):
    def test_heartbeat_freshness_and_arming(self):
        class Mav:
            stopped = 0
            def heartbeat_send(self, *args): pass
            def log_request_end_send(self, *args): self.stopped += 1
        class Conn:
            mav = Mav()
            def recv_match(self, **kw): return Message('HEARTBEAT', base_mode=self.mode)
        m=Conn(); link=ld.Link(m)
        self.assertFalse(link.safe())
        m.mode=0;link.receive();self.assertTrue(link.safe())
        m.mode=128;link.receive();self.assertFalse(link.safe());self.assertEqual(m.mav.stopped,1)
        m.mode=0;link.receive();link.hb-=3;self.assertFalse(link.safe())

    def test_reordered_packets_and_verified_resume(self):
        data=bytes(range(256))*3
        class Fake:
            def __init__(self): self.m=self;self.mav=self;self.q=[];self.requests=0
            def safe(self): return True
            def wait_safe(self): pass
            def log_request_data_send(self, sysid, compid, lid, offset, count):
                self.requests+=1
                self.q=[Message('LOG_DATA',id=lid,ofs=p,count=len(data[p:p+90]),data=data[p:p+90]) for p in range(offset,offset+count,90)][::-1]
            def receive(self, timeout=.1):
                return self.q.pop(0) if self.q else None
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);f=Fake()
            # Simulate a prior process that committed one complete 90-byte chunk.
            (out/'00000009.part').write_bytes(data[:90])
            (out/'00000009.part.json').write_text(json.dumps({'id':9,'size':len(data),'time_utc':1794027130}))
            ld.download(f,9,len(data),1794027130,out)
            self.assertEqual((out/'00000009.BIN').read_bytes(),data)
            requests=f.requests
            ld.download(f,9,len(data),1794027130,out)
            self.assertEqual(f.requests,requests)
            self.assertFalse((out/'00000009.part').exists())

    def test_lost_open_ack_reuses_identical_request(self):
        sent=[];clock=[0];replies=[]
        class Mav:
            def file_transfer_protocol_send(self,*args):
                payload=args[-1];sent.append(payload)
                if len(sent)>1:
                    seq=struct.unpack('<H',payload[:2])[0]
                    replies.append(((seq+1,0,128,4,4,0,0,0),struct.pack('<I',100)))
        class Link:
            def __init__(self):self.m=self;self.mav=Mav()
            def wait_safe(self):pass
            def safe(self):return True
        ftp=fd.FTP(Link())
        def receive():
            clock[0]+=.5
            return replies.pop(0) if replies else None
        ftp.receive=receive
        with patch.object(fd.time,'monotonic',lambda:clock[0]):
            self.assertEqual(ftp.open('/APM/LOGS/00000050.BIN'),(0,100))
        self.assertEqual(len(sent),2)
        self.assertEqual(sent[0],sent[1])

    def test_ftp_pipeline_reorders_and_checks_crc(self):
        import zlib
        data=bytes(range(256))*10
        class Fake:
            def __init__(self):self.link=self;self.q=[];self.seq=0
            def safe(self):return True
            def wait_safe(self):pass
            def open(self,path):return 0,len(data)
            def send(self,op,session=0,offset=0,size=0,data=b''):
                self.seq+=2
                if op==5:self.q.insert(0,(self.seq,offset,size))
                return self.seq
            def receive(self):
                seq,pos,size=self.q.pop(0)
                return (seq,0,128,size,5,0,0,pos),data[pos:pos+size]
            def crc(self,path):return zlib.crc32(data,0xffffffff)^0xffffffff
        with tempfile.TemporaryDirectory() as tmp:
            fd.download(Fake(),50,len(data),Path(tmp))
            self.assertEqual((Path(tmp)/'00000050.BIN').read_bytes(),data)
            meta=json.loads((Path(tmp)/'00000050.json').read_text())
            self.assertIn('fc_crc32',meta)

    def test_attitude_wobble_band(self):
        import math
        stats=fr.Summary();stats.handover=0
        stats.attitude=[(1+i/50,0,0,math.radians(2)*math.sin(2*math.pi*4*i/50),0) for i in range(251)]
        result=stats.attitude_summary()
        self.assertEqual(result['status'],'available')
        self.assertAlmostEqual(result['roll_pitch_rate_3_5_to_5_5_hz_rms_deg_s'][0],math.sqrt(2),places=2)

    def test_camera_coordinates_and_partial_record(self):
        started=1794027130
        stats=fr.Summary();stats.handover=started+2
        stats.targets=[(started+3, .02, .03)]
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/time.strftime('%Y%m%d-%H%M%S',time.localtime(started))
            directory.mkdir()
            rows=[{'t_cap':started+3.1,'boxes':[{'drone_m':[.03,-.03,.4]}]},
                  {'t_cap':started+3.2,'boxes':[]}]
            (directory/'cv.jsonl').write_text('\n'.join(json.dumps(x) for x in rows)+'\n{')
            result=fr.camera_summary(Path(tmp),stats,started,started+4)
            self.assertEqual(result['samples'],1)
            self.assertAlmostEqual(result['horizontal_rms_m'],.01)
            self.assertEqual(result['missing_frames'],1)

    def test_bulk_replies_do_not_reach_camera(self):
        import socket, os
        def port():
            sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sock.bind(('127.0.0.1',0));value=sock.getsockname()[1];sock.close();return value
        fc_port, local_port=port(),port()
        env=os.environ.copy();env['MAVLINK20']='1'
        p=subprocess.Popen([sys.executable,str(ROOT/'companion/mav_tunnel.py'),'--dev',f'udpin:127.0.0.1:{fc_port}','--local',f'udpin:127.0.0.1:{local_port}'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        fc=mavutil.mavlink_connection(f'udpout:127.0.0.1:{fc_port}',source_system=1,source_component=1)
        camera=mavutil.mavlink_connection(f'udpout:127.0.0.1:{local_port}',source_system=1,source_component=191)
        downloader=mavutil.mavlink_connection(f'udpout:127.0.0.1:{local_port}',source_system=246,source_component=196)
        try:
            time.sleep(.6)
            camera.mav.heartbeat_send(18,8,0,0,4)
            frames=downloader.mav.heartbeat_encode(6,8,0,0,4).pack(downloader.mav)
            frames+=downloader.mav.log_request_data_encode(1,1,50,0,90).pack(downloader.mav)
            downloader.write(frames)
            camera.mav.heartbeat_send(18,8,0,0,4)
            time.sleep(.1)
            fc.mav.heartbeat_send(2,3,0,0,4)
            fc.mav.log_data_send(50,0,90,[7]*90)
            self.assertIsNotNone(downloader.recv_match(type='LOG_DATA',blocking=True,timeout=2))
            self.assertIsNone(camera.recv_match(type='LOG_DATA',blocking=True,timeout=.3))
            fc.mav.heartbeat_send(2,3,0,0,4)
            self.assertIsNotNone(camera.recv_match(type='HEARTBEAT',blocking=True,timeout=2))
        finally:
            p.terminate();stdout,stderr=p.communicate(timeout=3)
            for link in (fc,camera,downloader):link.close()
            self.assertNotIn(b'Traceback',stderr,stderr.decode())

    def test_recorder_real_udp_landing_summary(self):
        import socket
        sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
        with tempfile.TemporaryDirectory() as tmp:
            p=subprocess.Popen([sys.executable,str(ROOT/'companion/flight_recorder.py'),'--link',f'udpin:127.0.0.1:{port}','--out',tmp],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            m=mavutil.mavlink_connection(f'udpout:127.0.0.1:{port}',source_system=1,source_component=1)
            try:
                time.sleep(.6)
                for mode in [0,128,128,0]:
                    m.mav.heartbeat_send(2,3,mode,0,4)
                    time.sleep(.15)
                deadline=time.monotonic()+2
                reports=[]
                while not reports and time.monotonic()<deadline:
                    reports=list(Path(tmp).glob('*/summary.json'));time.sleep(.02)
                self.assertEqual(len(reports),1)
                report=json.loads(reports[0].read_text());self.assertEqual(report['status'],'disarmed')
                self.assertIsNone(report['horizontal_rms_m'])
                self.assertTrue((reports[0].parent/'telemetry.tlog').stat().st_size>0)
                log=mavutil.mavlink_connection(str(reports[0].parent/'telemetry.tlog'))
                count=0
                while log.recv_match(type='HEARTBEAT'): count+=1
                self.assertEqual(count,4)
            finally:
                p.terminate();p.communicate(timeout=3);m.close()

if __name__=='__main__': unittest.main()
