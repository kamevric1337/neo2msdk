"""Tầng Transport — phân/dựng khung DUML v1 (có CRC) và lớp tunnel.

Xem notes/tien-do-giai-ma.md mục 4. Frame DUML v1:
  55 | len+ver(2) | crc8 | src | dst | seq(2) | cfg | cmd_set | cmd_id | payload... | crc16
Phần lớn frame telemetry bị bọc trong tunnel cmd_set=0x51/cmd_id=0x01 (đệ quy).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

DELIMITER = 0x55
TUNNEL_SET = 0x51
TUNNEL_ID = 0x01


# --- CRC của DUML v1 ---
def _table(poly):
    t = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ poly if c & 1 else c >> 1
        t.append(c)
    return t


_T8, _T16 = _table(0x8C), _table(0x8408)


def crc8(data, crc=0x77):
    for b in data:
        crc = _T8[(crc ^ b) & 0xFF]
    return crc


def crc16(data, crc=0x3692):
    for b in data:
        crc = (crc >> 8) ^ _T16[(crc ^ b) & 0xFF]
    return crc


@dataclass
class DumlFrame:
    src: int
    dst: int
    cmd_set: int
    cmd_id: int
    seq: int
    payload: bytes
    nested: bool          # True nếu frame này nằm trong một tunnel

    def key(self):
        return (self.src, self.dst, self.cmd_set, self.cmd_id)


def iter_frames(buf: bytes, start: int = 0, _depth: int = 0):
    """Sinh mọi DumlFrame hợp lệ (qua CRC8 + CRC16) trong buf, kể cả frame lồng.

    Dùng cho cả body kênh DUML (start=34 để bỏ 18 byte header riêng) lẫn khi
    quét toàn bộ. Mặc định start=0 quét từ đầu.
    """
    i = buf.find(b"\x55", start)
    while i != -1 and i + 13 <= len(buf):
        if crc8(buf[i:i + 3]) == buf[i + 3]:
            length = struct.unpack_from("<H", buf, i + 1)[0] & 0x03FF
            if length >= 13 and i + length <= len(buf) and \
                    crc16(buf[i:i + length - 2]) == struct.unpack_from("<H", buf, i + length - 2)[0]:
                src, dst = buf[i + 4], buf[i + 5]
                seq = struct.unpack_from("<H", buf, i + 6)[0]
                cmd_set, cmd_id = buf[i + 9], buf[i + 10]
                payload = buf[i + 11:i + length - 2]
                yield DumlFrame(src, dst, cmd_set, cmd_id, seq, payload, _depth > 0)
                if cmd_set == TUNNEL_SET and cmd_id == TUNNEL_ID and _depth < 4:
                    yield from iter_frames(payload, 0, _depth + 1)
                i += length
                continue
        i = buf.find(b"\x55", i + 1)
