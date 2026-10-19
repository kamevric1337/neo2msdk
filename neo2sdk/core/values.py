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
