"""SDK Core — dựng các lệnh điều khiển (đường ghi).

Hiện chỉ có lệnh đã giải mã trọn vẹn: **xin keyframe (I-frame)**
(0x02→0x09 set 0x01 id 0x01, payload[5] bit 0x20 = "xin ngay"; xem cap_05).

Các lệnh khác (virtual stick…) cần lấy frame qua Frida hook động — chưa làm.
Hàm ở đây chỉ DỰNG byte gói; việc GỬI do tầng transport (socket udp) đảm nhận
khi đã kết nối drone thật.
"""
from __future__ import annotations

from ..transport.duml import build_frame
from ..transport.framing import build_duml_app_packet

# Địa chỉ module (xem notes)
APP = 0x02
VIDEO_MCU = 0x09   # "HD transmission MCU air side"


def request_iframe_frame(seq: int = 0, request: bool = True) -> bytes:
    """Khung DUML xin keyframe: 0x02→0x09 set 0x01 id 0x01.

    payload 11 byte, byte[5] = 0x24 (bit 0x20 bật = xin) / 0x04 (không xin).
    Khớp mẫu quan sát ở cap_05.
    """
    x = 0x24 if request else 0x04
    payload = bytes([0, 0, 0, 0, 0, x, 0, 0, 0, x, 0])
    return build_frame(APP, VIDEO_MCU, 0x01, 0x01, payload, seq=seq)


def request_iframe_packet(session_id: int, seq: int = 0, request: bool = True) -> bytes:
    """Gói UDP 9003 hoàn chỉnh để gửi lệnh xin keyframe tới drone."""
    return build_duml_app_packet(request_iframe_frame(seq, request), session_id)
