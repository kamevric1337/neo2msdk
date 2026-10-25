"""SDK Core — dựng các lệnh điều khiển (đường ghi).

Hiện chỉ có lệnh đã giải mã trọn vẹn: **xin keyframe (I-frame)**
(0x02→0x09 set 0x01 id 0x01, payload[5] bit 0x20 = "xin ngay"; xem cap_05).

Các lệnh khác (virtual stick…) cần lấy frame qua Frida hook động — chưa làm.
Hàm ở đây chỉ DỰNG byte gói; việc GỬI do tầng transport (socket udp) đảm nhận
khi đã kết nối drone thật.
"""
from __future__ import annotations

import struct

from ..transport.duml import build_frame
from ..transport.framing import build_duml_app_packet

# Địa chỉ module (xem notes)
APP = 0x02
VIDEO_MCU = 0x09   # "HD transmission MCU air side"
GIMBAL = 0x04      # module gimbal
CAMERA = 0x01      # module camera (nhận cmd_set 0x02)

# Lệnh gimbal: giá trị tốc độ mỗi trục bão hòa ở ±200 (quan sát khi kéo thanh hết cỡ).
GIMBAL_SPEED_MAX = 200
GIMBAL_CTRL_FLAG = 0x80   # byte[6], cố định trên mọi mẫu (cờ bật điều khiển)


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


def gimbal_speed_frame(yaw: int = 0, roll: int = 0, pitch: int = 0, seq: int = 0) -> bytes:
    """Khung DUML điều khiển tốc độ gimbal: 0x02→0x04 set 0x04 id 0x0c.

    payload 8 byte: yaw(i16 LE) | roll(i16 LE) | pitch(i16 LE) | 0x80 | 0x00.
    Mỗi trục là tốc độ, hết cỡ ở ±GIMBAL_SPEED_MAX (±200). Dương = lên, âm = xuống
    (kiểm chứng: kéo thanh pitch xuống → âm dần tới -200, kéo lên → dương tới +200;
    yaw/roll giữ 0 khi chỉ động pitch). Xem notes/capture-log.md (Ngày 9).
    """
    c = lambda v: max(-GIMBAL_SPEED_MAX, min(GIMBAL_SPEED_MAX, int(v)))
    payload = struct.pack("<hhh", c(yaw), c(roll), c(pitch)) + bytes([GIMBAL_CTRL_FLAG, 0x00])
    return build_frame(APP, GIMBAL, 0x04, 0x0c, payload, seq=seq)


def gimbal_speed_packet(session_id: int, yaw: int = 0, roll: int = 0,
                        pitch: int = 0, seq: int = 0) -> bytes:
    """Gói UDP 9003 hoàn chỉnh để gửi lệnh tốc độ gimbal tới drone."""
    return build_duml_app_packet(gimbal_speed_frame(yaw, roll, pitch, seq), session_id)


def shoot_photo_frame(seq: int = 0, mode: int = 0x01) -> bytes:
    """Khung DUML chụp ảnh: 0x02→0x01 set 0x02 id 0x01 (Camera / Shoot Photo).

    payload 1 byte = mode (quan sát = 0x01 khi bấm nút chụp đơn). Xem notes (Ngày 9).
    """
    return build_frame(APP, CAMERA, 0x02, 0x01, bytes([mode & 0xFF]), seq=seq)


def shoot_photo_packet(session_id: int, seq: int = 0, mode: int = 0x01) -> bytes:
    """Gói UDP 9003 hoàn chỉnh để gửi lệnh chụp ảnh tới drone."""
    return build_duml_app_packet(shoot_photo_frame(seq, mode), session_id)


def record_frame(seq: int = 0, start: bool = True) -> bytes:
    """Khung DUML quay video: 0x02→0x01 set 0x02 id 0x02 (Camera / Start-Stop Record).

    payload 1 byte = 0x01 bắt đầu quay / 0x00 dừng. Xem notes (Ngày 9).
    """
    return build_frame(APP, CAMERA, 0x02, 0x02, bytes([0x01 if start else 0x00]), seq=seq)


def record_packet(session_id: int, seq: int = 0, start: bool = True) -> bytes:
    """Gói UDP 9003 hoàn chỉnh để gửi lệnh bắt đầu/dừng quay tới drone."""
    return build_duml_app_packet(record_frame(seq, start), session_id)
