"""Reliable byte stream inside MAVLink TUNNEL messages (used for SSH over the radio).

The radio drops packets, so each side numbers its data chunks, acknowledges what
it got in order, and sends again what was not acknowledged (go-back-N).

TUNNEL payload (max 128 bytes), payload_type PAYLOAD_TYPE:
  byte 0     kind: SYN, SYNACK, DATA, ACK, FIN
  byte 1-2   session id
  byte 3-4   seq: DATA = number of this chunk; others = 0
  byte 5-6   ack: the next chunk number this side expects
  byte 7..   data (DATA only, up to CHUNK bytes)
"""
import struct
import time

PAYLOAD_TYPE = 39001          # private range (32768-65535) of MAV_TUNNEL_PAYLOAD_TYPE
SYN, SYNACK, DATA, ACK, FIN = 1, 2, 3, 4, 5
HDR = struct.Struct("<BHHH")
CHUNK = 128 - HDR.size        # 121 data bytes
WINDOW = 6                    # chunks in flight; about 0.9 KB, a few radio frames
RTO = 1.2                     # s without progress before sending again


def pack(kind, session, seq=0, ack=0, data=b""):
    return HDR.pack(kind, session, seq & 0xFFFF, ack & 0xFFFF) + data


def unpack(payload):
    kind, session, seq, ack = HDR.unpack_from(payload)
    return kind, session, seq, ack, bytes(payload[HDR.size:])


class Stream:
    """One direction-pair of a session. send(payload) puts one TUNNEL on the link."""

    def __init__(self, session, send):
        self.session, self.send = session, send
        self.out = bytearray()        # bytes not yet cut into chunks
        self.unacked = []             # [(seq, data)] in flight, oldest first
        self.next_seq = 0             # number of the next new chunk
        self.expect = 0               # next chunk number we accept
        self.last_progress = time.time()
        self.need_ack = False
        self.closed = False

    def write(self, data):
        self.out += data

    def handle(self, kind, seq, ack, data):
        """Process one received packet. Returns bytes for the local side (may be b'')."""
        got = b""
        # their ack frees our chunks: ack = the next chunk they expect
        while self.unacked and 0 < ((ack - self.unacked[0][0]) & 0xFFFF) < 0x8000:
            self.unacked.pop(0)                                # chunk acked
            self.last_progress = time.time()
        if kind == DATA:
            if seq == self.expect:
                got = data
                self.expect = (self.expect + 1) & 0xFFFF
            self.need_ack = True       # ack in order data and duplicates alike
        elif kind == FIN:
            self.closed = True
        return got

    def poll(self):
        """Send new chunks, acks and retransmits. Call often."""
        now = time.time()
        if self.unacked and now - self.last_progress > RTO:
            for seq, data in self.unacked:                    # go-back-N
                self.send(pack(DATA, self.session, seq, self.expect, data))
            self.last_progress = now
            self.need_ack = False
        while self.out and len(self.unacked) < WINDOW:
            data, self.out = bytes(self.out[:CHUNK]), self.out[CHUNK:]
            seq = self.next_seq
            self.next_seq = (self.next_seq + 1) & 0xFFFF
            if not self.unacked:
                self.last_progress = now
            self.unacked.append((seq, data))
            self.send(pack(DATA, self.session, seq, self.expect, data))
            self.need_ack = False
        if self.need_ack:
            self.send(pack(ACK, self.session, 0, self.expect))
            self.need_ack = False

    def idle(self):
        return not self.out and not self.unacked
