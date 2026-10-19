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
| `FlightControllerKey.Status` | FlightStatus (cờ bay) | cap_09 (in_air/motors) |
| `FlightControllerKey.IsFlying` / `.AreMotorsOn` | bool | cap_09 |
| `FlightControllerKey.Location` / `.SatelliteCount` | GpsLocation / int | 🟡 cần bay ngoài trời |
| `FlightControllerKey.UltrasonicHeight` | float (m) | 🟡 |
| `GimbalKey.Attitude` | GimbalAttitude(pitch,quat) | cap_06/07 |

Toàn bộ frame OSD General được giải mã theo **layout chuẩn DJI** (pitch/roll/yaw, độ cao, vận tốc,
GPS, vệ tinh, cờ in_air/motor/gps…). Các trường 🟡 đã nối dây sẵn, sẽ có giá trị khi bay ngoài trời.

## Đường ghi (điều khiển)

- **Xin keyframe** — ✅ **dựng byte chính xác** (`sdk.build_request_iframe()` offline;
  `sdk.request_iframe()` gửi khi `connect("udp")`). Frame dựng ra **trùng y hệt từng byte**
  frame thật của DJI Fly (xem `tests/test_sdk.py::test_request_iframe_byte_exact`).
  Encoder đầy đủ: `transport.build_frame` / `build_outer` / `build_duml_app_packet`.
- **Điều khiển bay** (`ControlKey.VirtualStick`) — CHƯA: frame lệnh cần lấy qua Frida hook
  động (kiến trúc: `RequestJoystickControlAuth` + `MobileRCHandler::SendCmd`, 4 float).
  Xem `notes/capture-log.md`.
- **GPS, vận tốc ngang** — cần bay ngoài trời / bay ngang để kiểm chứng.

## Kiểm thử

`python tests/test_sdk.py` — 9 test: round-trip encode/decode (frame DUML, header ngoài,
tunnel lồng), lệnh xin keyframe **trùng byte** frame thật, và giải mã telemetry trên pcap thật.

Nền tảng giao thức: `notes/tien-do-giai-ma.md`, `notes/capture-log.md`.
