"""SDK Core — giải mã khung DUML thành (key, value).

Mọi offset/ý nghĩa đã kiểm chứng thực nghiệm (xem notes/capture-log.md,
notes/tien-do-giai-ma.md). Trả về danh sách (key_path, value) để KeyManager
cập nhật cache và gọi listener.
"""
from __future__ import annotations

import math
import struct

from ..keys.keys import BatteryKey, FlightControllerKey, GimbalKey
from ..transport.duml import DumlFrame
from .values import Attitude, BatteryInfo, GimbalAttitude, Velocity3D


def _i16(buf, off):
    return struct.unpack_from("<h", buf, off)[0]


def decode(frame: DumlFrame):
    """DumlFrame -> list[(key, value)]. Rỗng nếu frame không mang telemetry đã biết."""
    p = frame.payload
    cs, ci, src, dst = frame.cmd_set, frame.cmd_id, frame.src, frame.dst
    out = []

    # Pin: module pin (0x0b) -> app. Battery Dynamic Data (layout chuẩn + 1 byte đầu).
    if src == 0x0B and cs == 0x0D and ci == 0x02 and len(p) >= 30:
        out.append((BatteryKey.Info, BatteryInfo(
            percent=p[20],
            voltage_mv=struct.unpack_from("<I", p, 1)[0],
            current_ma=struct.unpack_from("<i", p, 5)[0],
            remain_mah=struct.unpack_from("<I", p, 13)[0],
            full_mah=struct.unpack_from("<I", p, 9)[0],
            cells=p[19],
            temp_c=struct.unpack_from("<H", p, 17)[0] / 10.0,
        )))
        out.append((BatteryKey.PercentRemaining, p[20]))
        return out

    # Gimbal: gimbal (0x04) -> app.
    if src == 0x04 and cs == 0x04 and ci == 0x05 and len(p) >= 40:
        pitch = _i16(p, 0) / 10.0
        quat = struct.unpack_from("<ffff", p, 24)
        n = math.sqrt(sum(c * c for c in quat))
        out.append((GimbalKey.Attitude, GimbalAttitude(pitch, quat if 0.9 < n < 1.1 else None)))
        return out

    # Hướng + chuyển động thân drone: FC OSD General (layout chuẩn DJI).
    if cs == 0x03 and ci == 0x43 and len(p) >= 36:
        out.append((FlightControllerKey.Attitude, Attitude(
            pitch=_i16(p, 24) / 10.0, roll=_i16(p, 26) / 10.0, yaw=_i16(p, 28) / 10.0)))
        out.append((FlightControllerKey.Altitude, _i16(p, 16) / 10.0))
        out.append((FlightControllerKey.Velocity, Velocity3D(
            x=_i16(p, 18) / 10.0, y=_i16(p, 20) / 10.0, z=_i16(p, 22) / 10.0)))
        out.append((FlightControllerKey.Compass, _i16(p, 28) / 10.0))
        out.append((FlightControllerKey.FlightState, p[30] & 0x7F))
        return out

    return out
