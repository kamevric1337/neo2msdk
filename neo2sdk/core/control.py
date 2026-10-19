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
