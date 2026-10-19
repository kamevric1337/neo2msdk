"""SDK Core — các kiểu giá trị telemetry (tương tự value types của MSDK V5)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Attitude:
    """Tư thế (độ). Dùng cho cả thân drone lẫn gimbal."""
    pitch: float
    roll: float
    yaw: float


@dataclass
class Velocity3D:
    """Vận tốc theo 3 trục (m/s), quy ước NED (z dương = đi xuống)."""
    x: float
    y: float
    z: float


@dataclass
class BatteryInfo:
    percent: int
    voltage_mv: int
    current_ma: int        # âm = đang xả
    remain_mah: int
    full_mah: int
    cells: int
    temp_c: float          # ≈ (đơn vị tạm 0.1°C)


@dataclass
class GimbalAttitude:
    pitch: float           # độ; âm = chúc xuống
    quaternion: tuple      # (w, x, y, z) hoặc None


@dataclass
class GpsLocation:
    """Vị trí GPS (độ). CHƯA kiểm chứng — cần bay ngoài trời có tín hiệu."""
    latitude: float
    longitude: float


@dataclass
class FlightStatus:
    """Trạng thái bay, bóc từ OSD controller_state (layout chuẩn DJI).

    flyc_state, in_air, motors_on đã kiểm chứng (cap_09). Phần GPS chưa (trong nhà).
    """
    flyc_state: int
    in_air: bool
    on_ground: bool
    motors_on: bool
    gps_used: bool
    gps_level: int         # 0-5, mức tín hiệu GPS
    satellites: int        # số vệ tinh
    gohome_state: int
    battery_req_gohome: bool
    battery_req_land: bool
