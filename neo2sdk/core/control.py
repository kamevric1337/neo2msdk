"""SDK Core — khung đường ĐIỀU KHIỂN (virtual stick + xin quyền điều khiển).

Hình dạng API khớp đúng kiến trúc tìm được trong APK (xem notes/capture-log.md):
    RequestJoystickControlAuth  →  MobileRCHandler::SendCmd(JoystickConfig)
    SetMobileRCJoystickValue(sessionId, throttle, yaw, pitch, roll, buttons)  — 4 float.

TRẠNG THÁI: frame DUML cụ thể của các lệnh này CHƯA biết (phải lấy qua Frida hook
động — tools/frida/duml_sniff.js). Các hàm dưới đây để SẴN đúng chữ ký; phần dựng
byte (`_build_*`) sẽ điền khi có frame, giống `request_iframe_frame` đã làm xong.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class JoystickConfig:
    """4 trục cần, chuẩn hóa [-1, 1]. (Khớp 4 float của SetMobileRCJoystickValue.)"""
    throttle: float = 0.0   # lên/xuống (ga)
    yaw: float = 0.0        # xoay trái/phải
    pitch: float = 0.0      # tiến/lùi
    roll: float = 0.0       # nghiêng trái/phải

    def clamped(self) -> "JoystickConfig":
        c = lambda v: max(-1.0, min(1.0, v))
        return JoystickConfig(c(self.throttle), c(self.yaw), c(self.pitch), c(self.roll))


_NEED_FRIDA = (
    "Đường điều khiển chưa nối: frame DUML của lệnh này chưa biết. "
    "Chạy tools/frida/duml_sniff.js khi đẩy cần để lấy frame, rồi điền hàm dựng byte "
    "(xem notes/capture-log.md — kiến trúc: RequestJoystickControlAuth + MobileRCHandler::SendCmd)."
)


class FlightControl:
    """Bộ điều khiển bay. Gắn vào MSDKManager qua `sdk.flight_control`."""

    def __init__(self, manager):
        self._mgr = manager
        self._has_authority = False

    # --- quyền điều khiển (bắt buộc trước khi gửi cần) ---
    def request_control_authority(self) -> bool:
        """Xin quyền điều khiển (RequestJoystickControlAuth). CHƯA hỗ trợ."""
        raise NotImplementedError(_NEED_FRIDA)

    def release_control_authority(self) -> bool:
        raise NotImplementedError(_NEED_FRIDA)

    # --- gửi cần ---
    def send_virtual_stick(self, throttle=0.0, yaw=0.0, pitch=0.0, roll=0.0):
        """Gửi một mẫu cần (4 trục [-1,1]). CHƯA hỗ trợ (cần frame từ Frida)."""
        _cfg = JoystickConfig(throttle, yaw, pitch, roll).clamped()
        raise NotImplementedError(_NEED_FRIDA)

    # --- lệnh video đã hoạt động (đây là lệnh điều khiển DUY NHẤT đã giải mã) ---
    def request_iframe(self, request: bool = True):
        """Xin một keyframe (I-frame) ngay. Đã dựng byte chính xác; gửi khi connect('udp')."""
        return self._mgr.request_iframe(request)


class GimbalControl:
    """Điều khiển gimbal (tốc độ 3 trục). Gắn vào MSDKManager qua `sdk.gimbal_control`.

    Lệnh đã giải mã trọn vẹn và dựng byte chính xác (0x02→0x04 set 0x04 id 0x0c,
    xem core.commands.gimbal_speed_frame). GỬI cần kết nối live tới drone
    (`connect('udp')`, PC ở cùng mạng drone); dựng byte thì offline cũng được.
    """

    def __init__(self, manager):
        self._mgr = manager

    def build_speed(self, yaw: int = 0, roll: int = 0, pitch: int = 0) -> bytes:
        """Dựng gói lệnh tốc độ gimbal cho phiên hiện tại (không gửi). Giá trị THÔ ±200."""
        from .commands import gimbal_speed_packet
        self._mgr._seq = (self._mgr._seq + 1) & 0xFFFF
        return gimbal_speed_packet(self._mgr.session_id, yaw, roll, pitch, seq=self._mgr._seq)

    def send_speed(self, yaw: int = 0, roll: int = 0, pitch: int = 0):
        """Dựng + GỬI lệnh tốc độ gimbal THÔ (±200). Cần connect('udp')."""
        return self._mgr._send(self.build_speed(yaw, roll, pitch))

    def set_pitch(self, speed: float):
        """Đặt tốc độ pitch chuẩn hóa [-1, 1] (dương = ngẩng lên). Cần connect('udp')."""
        from .commands import GIMBAL_SPEED_MAX
        s = max(-1.0, min(1.0, speed))
        return self.send_speed(pitch=round(s * GIMBAL_SPEED_MAX))

    def stop(self):
        """Dừng gimbal (tốc độ 0 mọi trục)."""
        return self.send_speed(0, 0, 0)


class CameraControl:
    """Điều khiển camera. Gắn vào MSDKManager qua `sdk.camera_control`.

    `shoot_photo` đã giải mã (0x02→0x01 set 0x02 id 0x01). GỬI cần `connect('udp')`.
    """

    def __init__(self, manager):
        self._mgr = manager

    def build_shoot_photo(self, mode: int = 0x01) -> bytes:
        """Dựng gói chụp ảnh cho phiên hiện tại (không gửi)."""
        from .commands import shoot_photo_packet
        self._mgr._seq = (self._mgr._seq + 1) & 0xFFFF
        return shoot_photo_packet(self._mgr.session_id, seq=self._mgr._seq, mode=mode)

    def shoot_photo(self, mode: int = 0x01):
        """Dựng + GỬI lệnh chụp ảnh. Cần connect('udp')."""
        return self._mgr._send(self.build_shoot_photo(mode))
