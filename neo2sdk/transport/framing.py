"""Tầng Transport — header bọc ngoài của giao thức Neo 2 (UDP cổng 9003).

Giải mã/dựng header chung 16 byte. Xem notes/tien-do-giai-ma.md mục 3.
Mọi kết luận ở đây đã kiểm chứng trên cap_01/cap_02 (100% số gói).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

DUML_PORT = 9003

# Loại kênh (byte 6 của header)
CH_HANDSHAKE = 0x00      # gói bắt tay khi kết nối lại
CH_DUML_DRONE = 0x01     # DUML drone -> app
CH_VIDEO = 0x02          # luồng video H.265
CH_DUML_APP = 0x04       # DUML app -> drone

CHANNEL_NAME = {
    CH_HANDSHAKE: "handshake",
    CH_DUML_DRONE: "duml_drone",
    CH_VIDEO: "video",
    CH_DUML_APP: "duml_app",
}


@dataclass
class OuterPacket:
    """Một gói UDP 9003 đã bóc header ngoài."""
    length: int          # độ dài payload UDP (byte 0-1, bỏ cờ 0x8000)
    session_id: int      # byte 2-3, +1 mỗi lần kết nối lại
    video_seq: int       # byte 4-5, +8 mỗi gói video
    channel: int         # byte 6, loại kênh
    checksum_ok: bool    # byte 7 = XOR(byte 0..6)?
    body: bytes          # phần sau 16 byte header chung
    raw: bytes           # toàn bộ payload UDP

    @property
    def channel_name(self) -> str:
        return CHANNEL_NAME.get(self.channel, f"0x{self.channel:02x}")


def parse_outer(payload: bytes) -> OuterPacket | None:
    """Bóc header ngoài của một payload UDP cổng 9003. None nếu không hợp lệ."""
    if len(payload) < 16:
        return None
    b0 = struct.unpack_from("<H", payload, 0)[0]
    if (b0 & 0x8000) == 0 or (b0 & 0x7FFF) != len(payload):
        return None  # không phải gói Neo 2
    chk = 0
    for i in range(7):
        chk ^= payload[i]
    return OuterPacket(
        length=b0 & 0x7FFF,
        session_id=struct.unpack_from("<H", payload, 2)[0],
        video_seq=struct.unpack_from("<H", payload, 4)[0],
        channel=payload[6],
        checksum_ok=(chk == payload[7]),
        body=payload[16:],
        raw=payload,
    )
