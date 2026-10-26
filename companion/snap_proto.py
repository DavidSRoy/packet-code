"""Box camera snapshots over the telemetry radio (MAVLink TUNNEL messages).

Pull protocol: ground control asks for picture pieces only while the telemetry
arrives at its full rate, so the telemetry always comes first. The Pi never
sends a piece that nobody asked for.

  ground -> Pi (target 1:191)   REQ   frame, first chunk, count, quality, width
  Pi -> ground (target = asker) DATA  frame, chunk, number of chunks, bytes

REQ with frame 0 (or an unknown frame) asks for a new picture: the Pi takes
the newest camera frame, makes it grey, scales it to `width` and encodes it as
WebP at `quality` (JPEG before 2026-10-25; the receiver checks the file header).

TUNNEL payload (max 128 bytes), payload_type PAYLOAD_TYPE:
  REQ   B kind=1, H frame, H first, B count, B quality, H width
  DATA  B kind=2, H frame, H chunk, H nchunks, then up to CHUNK bytes
"""
import struct

PAYLOAD_TYPE = 39002          # private range of MAV_TUNNEL_PAYLOAD_TYPE (39001 = SSH)
REQ, DATA = 1, 2
REQ_FMT = struct.Struct("<BHHBBH")
DATA_HDR = struct.Struct("<BHHH")
CHUNK = 128 - DATA_HDR.size   # 121 picture bytes in each message


def pack_req(frame, first, count, quality, width):
    return REQ_FMT.pack(REQ, frame & 0xFFFF, first, count, quality, width)


def pack_data(frame, chunk, nchunks, data):
    return DATA_HDR.pack(DATA, frame & 0xFFFF, chunk, nchunks) + data


def unpack(payload):
    """Returns ("req", frame, first, count, quality, width) or ("data", frame, chunk, nchunks, bytes)."""
    kind = payload[0]
    if kind == REQ and len(payload) >= REQ_FMT.size:
        _, frame, first, count, quality, width = REQ_FMT.unpack_from(payload)
        return ("req", frame, first, count, quality, width)
    if kind == DATA and len(payload) >= DATA_HDR.size:
        _, frame, chunk, nchunks = DATA_HDR.unpack_from(payload)
        return ("data", frame, chunk, nchunks, bytes(payload[DATA_HDR.size:]))
    return None
