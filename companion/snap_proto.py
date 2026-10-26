"""Box camera snapshots over the telemetry radio (MAVLink TUNNEL messages).

Push protocol, telemetry first:

  ground -> Pi (target 1:191)   CTRL  every 0.1 s while ground control wants pictures:
                                      allowed rate, quality, width, and which pieces of
                                      the current picture it has (bit list)
  Pi -> ground (target = sender) DATA one piece: sequence number, frame, chunk, bytes

The Pi sends the pieces of one picture evenly spaced at the allowed rate (no
bursts: the FC to radio serial link drops what it cannot carry). When the first
pass is done, it sends again only the pieces that the last CTRL says are
missing. A CTRL with the "complete" flag for the current frame starts the next
picture (the newest camera frame). The Pi sends nothing when no CTRL came for
CTRL_TIMEOUT or the rate is 0: ground control stops the CTRL messages when the
telemetry does not arrive at full rate, or when the Pi is on Wi-Fi.

Ground control sets the rate from the telemetry health and from the piece loss
(gaps in the sequence numbers).

Picture: the newest camera frame in colour, scaled to `width`, WebP at `quality`.

TUNNEL payload (max 128 bytes), payload_type PAYLOAD_TYPE:
  CTRL  B kind=3, H frame, B flags (1 = frame complete), H rate (pieces/s x 10),
        B quality, H width, B nbits, then ceil(nbits/8) bytes: bit i = piece i received
  DATA  B kind=4, H seq, H frame, H chunk, H nchunks, then up to CHUNK bytes
"""
import struct

PAYLOAD_TYPE = 39002          # private range of MAV_TUNNEL_PAYLOAD_TYPE (39001 = SSH)
CTRL, DATA = 3, 4             # (1, 2 were the old pull protocol)
CTRL_FMT = struct.Struct("<BHBHBHB")
DATA_HDR = struct.Struct("<BHHHH")
CHUNK = 128 - DATA_HDR.size   # 119 picture bytes in each message
MAX_BITS = (128 - CTRL_FMT.size) * 8
CTRL_TIMEOUT = 1.5            # s: no CTRL for this long = stop sending
COMPLETE = 1


def pack_ctrl(frame, complete, rate, quality, width, have, nbits):
    """have: set of received piece numbers of `frame`; nbits: number of pieces (0 if unknown)."""
    nbits = min(nbits, MAX_BITS)
    bits = bytearray((nbits + 7) // 8)
    for i in have:
        if i < nbits:
            bits[i // 8] |= 1 << (i % 8)
    return CTRL_FMT.pack(CTRL, frame & 0xFFFF, COMPLETE if complete else 0,
                         max(0, min(65535, int(round(rate * 10)))), quality, width, nbits) + bytes(bits)


def pack_data(seq, frame, chunk, nchunks, data):
    return DATA_HDR.pack(DATA, seq & 0xFFFF, frame & 0xFFFF, chunk, nchunks) + data


def unpack(payload):
    """Returns ("ctrl", frame, complete, rate, quality, width, have_set, nbits)
    or ("data", seq, frame, chunk, nchunks, bytes), or None."""
    if not payload:
        return None
    kind = payload[0]
    if kind == CTRL and len(payload) >= CTRL_FMT.size:
        _, frame, flags, rate10, quality, width, nbits = CTRL_FMT.unpack_from(payload)
        bits = payload[CTRL_FMT.size:CTRL_FMT.size + (nbits + 7) // 8]
        have = {i for i in range(min(nbits, len(bits) * 8)) if bits[i // 8] >> (i % 8) & 1}
        return ("ctrl", frame, bool(flags & COMPLETE), rate10 / 10.0, quality, width, have, nbits)
    if kind == DATA and len(payload) >= DATA_HDR.size:
        _, seq, frame, chunk, nchunks = DATA_HDR.unpack_from(payload)
        return ("data", seq, frame, chunk, nchunks, bytes(payload[DATA_HDR.size:]))
    return None
