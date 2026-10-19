"""neo2sdk — MSDK riêng cho DJI Neo 2 (tự reverse-engineer giao thức).

Kiến trúc theo convention MSDK V5:  App → MSDKManager → SDK Core → Transport.

    from neo2sdk import MSDKManager
    from neo2sdk.keys import FlightControllerKey, BatteryKey

    sdk = MSDKManager()
    sdk.connect(source="captures/cap_08_attitude.pcap")   # hoặc source="udp" khi có drone
    sdk.key_manager.listen(BatteryKey.PercentRemaining, lambda v: print("pin", v))
    sdk.start()

Trạng thái: đường ĐỌC (telemetry + video) đã hiện thực và kiểm thử offline trên pcap.
Đường ĐIỀU KHIỂN chưa làm (frame lệnh cần Frida hook động — xem notes/capture-log.md).
"""
from .sdk import MSDKManager

__all__ = ["MSDKManager"]
__version__ = "0.1.0-poc"
