"""Định nghĩa Key theo convention MSDK V5 (nhóm theo component).

Trong MSDK V5, mỗi thứ đọc/điều khiển được có một Key, ví dụ
`FlightControllerKey.Attitude`, `BatteryKey.PercentRemaining`. Ở đây Key là
một object bất biến, băm được, có đường dẫn "Component.Name" để KeyManager
dùng làm khóa cache và đăng ký listener.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Key:
    component: str   # vd "FlightController", "Battery", "Gimbal"
    name: str        # vd "Attitude", "PercentRemaining"
    readable: bool = True
    writable: bool = False   # True khi làm đường điều khiển (chưa hỗ trợ)

    @property
    def path(self) -> str:
        return f"{self.component}.{self.name}"

    def __str__(self):
        return self.path


class FlightControllerKey:
    Attitude = Key("FlightController", "Attitude")          # Attitude(pitch,roll,yaw) độ
    Altitude = Key("FlightController", "Altitude")          # float, m (so với điểm cất cánh)
    Velocity = Key("FlightController", "Velocity")          # Velocity3D m/s (NED)
    Compass = Key("FlightController", "CompassHeading")     # float, độ (= yaw)
    FlightState = Key("FlightController", "FlightState")    # int (flyc_state)
    Status = Key("FlightController", "Status")              # FlightStatus (cờ bay)
    Location = Key("FlightController", "Location")          # GpsLocation (🟡 chưa kiểm chứng)
    SatelliteCount = Key("FlightController", "SatelliteCount")   # int (🟡)
    IsFlying = Key("FlightController", "IsFlying")          # bool
    AreMotorsOn = Key("FlightController", "AreMotorsOn")    # bool
    UltrasonicHeight = Key("FlightController", "UltrasonicHeight")  # float m (cảm biến siêu âm)


class BatteryKey:
    Info = Key("Battery", "Info")                          # BatteryInfo
    PercentRemaining = Key("Battery", "PercentRemaining")  # int %


class GimbalKey:
    Attitude = Key("Gimbal", "Attitude")                   # GimbalAttitude


# Đăng ký điều khiển (CHƯA hỗ trợ — frame lệnh cần Frida hook, xem capture-log).
class ControlKey:
    VirtualStick = Key("FlightController", "VirtualStick", readable=False, writable=True)
    RequestIFrame = Key("Camera", "RequestIFrame", readable=False, writable=True)


ALL_READABLE = [
    FlightControllerKey.Attitude, FlightControllerKey.Altitude,
    FlightControllerKey.Velocity, FlightControllerKey.Compass,
    FlightControllerKey.FlightState, FlightControllerKey.Status,
    FlightControllerKey.Location, FlightControllerKey.SatelliteCount,
    FlightControllerKey.IsFlying, FlightControllerKey.AreMotorsOn,
    FlightControllerKey.UltrasonicHeight,
    BatteryKey.Info, BatteryKey.PercentRemaining,
    GimbalKey.Attitude,
]
