# neo2sdk — MSDK riêng cho DJI Neo 2 (PoC)

SDK tự xây từ giao thức đã reverse-engineer, theo convention **MSDK V5**
(Key-based, phân tầng). Giai đoạn PoC: **đường ĐỌC (telemetry + video) đã chạy**,
kiểm thử offline trên các pcap đã bắt. Đường ĐIỀU KHIỂN chưa làm.

## Kiến trúc (App → MSDKManager → SDK Core → Transport)

```
  App / ví dụ
      │  key_manager.listen(key, cb) · get_value(key) · on_video(cb)
┌─────▼─────────────────────────────────────────────┐
│ MSDKManager (sdk.py)   — vòng đọc, demux theo kênh │
├────────────────────────────────────────────────────┤
│ Keys (keys/)           — Key + KeyManager (cache,   │
│                          listener) như MSDK V5      │
├────────────────────────────────────────────────────┤
│ SDK Core (core/)       — decode telemetry → value;  │
│                          VideoDecoder (H.265)       │
├────────────────────────────────────────────────────┤
│ Transport (transport/) — nguồn gói (pcap/udp);      │
│                          header ngoài; khung DUML    │
│                          (+CRC, tunnel)             │
└────────────────────────────────────────────────────┘
```

## Dùng nhanh

```python
from neo2sdk import MSDKManager
from neo2sdk.keys import BatteryKey, FlightControllerKey

sdk = MSDKManager()
sdk.connect("captures/cap_09_flight_indoor.pcap")   # offline; đổi "udp" khi có drone
sdk.key_manager.listen(BatteryKey.PercentRemaining, lambda v: print("pin", v))
sdk.key_manager.listen(FlightControllerKey.Altitude, lambda h: print("cao", h))
sdk.start()
print(sdk.key_manager.get_value(FlightControllerKey.Attitude))
```

Ví dụ đầy đủ: `examples/read_telemetry.py`, `examples/save_video.py`.

## Key hiện có (đường đọc)

| Key | Kiểu giá trị | Nguồn (đã kiểm chứng) |
|---|---|---|
| `BatteryKey.Info` / `.PercentRemaining` | BatteryInfo / int | cap_04 |
| `FlightControllerKey.Attitude` | Attitude(pitch,roll,yaw) | cap_08 |
| `FlightControllerKey.Altitude` | float (m) | cap_09 |
| `FlightControllerKey.Velocity` | Velocity3D (NED) | cap_09 (vgz) |
| `FlightControllerKey.Compass` | float (độ) | cap_08 |
| `FlightControllerKey.FlightState` | int | cap_09 |
| `GimbalKey.Attitude` | GimbalAttitude(pitch,quat) | cap_06/07 |

## Chưa hỗ trợ
- **Điều khiển bay** (`ControlKey.VirtualStick`) — frame lệnh cần lấy qua Frida hook
  động (kiến trúc: `RequestJoystickControlAuth` + `MobileRCHandler::SendCmd`, 4 float).
  Xem `notes/capture-log.md`.
- **Xin keyframe** (`ControlKey.RequestIFrame`) — đã biết frame (`0x02→0x09 0x01/0x01`,
  bit 0x20), nhưng gửi gói thuộc đường điều khiển, chưa nối dây.
- **GPS, vận tốc ngang** — cần bay ngoài trời / bay ngang để kiểm chứng.

Nền tảng giao thức: `notes/tien-do-giai-ma.md`, `notes/capture-log.md`.
