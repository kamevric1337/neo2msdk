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
| `FlightControllerKey.SatelliteCount` | int | ✅ verify live (5-6 sat trong nhà) |
| `FlightControllerKey.Location` | GpsLocation | ✅ đúng offset; = 0,0 tới khi drone có fix GPS |
| `FlightControllerKey.UltrasonicHeight` | float (m) | 🟡 |
| `GimbalKey.Attitude` | GimbalAttitude(pitch,quat) | cap_06/07 |

Toàn bộ frame OSD General được giải mã theo **layout chuẩn DJI** (pitch/roll/yaw, độ cao, vận tốc,
GPS, vệ tinh, cờ in_air/motor/gps…). GPS đã kiểm chứng live trong nhà (số vệ tinh + cờ gps_used
đúng; lat/lon = 0,0 vì drone chưa đủ sat để có fix — sẽ ra toạ độ thật khi có fix). Các trường 🟡
còn lại đã nối dây sẵn, sẽ có giá trị khi đủ điều kiện.

## Đường ghi (điều khiển)

- **Xin keyframe** — ✅ **dựng byte chính xác** (`sdk.build_request_iframe()` offline;
  `sdk.request_iframe()` gửi khi `connect("udp")`). Frame dựng ra **trùng y hệt từng byte**
  frame thật của DJI Fly (xem `tests/test_sdk.py::test_request_iframe_byte_exact`).
  Encoder đầy đủ: `transport.build_frame` / `build_outer` / `build_duml_app_packet`.
- **Điều khiển gimbal** — ✅ **đã giải mã + dựng byte** (`sdk.gimbal_control.set_pitch(s)` với
  `s∈[-1,1]`, hoặc `.send_speed(yaw,roll,pitch)` thô ±200, `.stop()`). Frame
  `0x02→0x04 set 0x04 id 0x0c`, payload = yaw|roll|pitch (i16 LE) | 0x80 | 0x00; tốc độ mỗi
  trục bão hòa ±200. Kiểm chứng bằng tcpdump khi kéo thanh gimbal (Ngày 9). GỬI cần
  `connect('udp')` (PC cùng mạng drone); dựng byte thì offline cũng được.
- **Chụp ảnh** — ✅ **đã giải mã + dựng byte** (`sdk.camera_control.shoot_photo()`). Frame
  `0x02→0x01 set 0x02 id 0x01`, payload `01` (Camera / Shoot Photo chuẩn DJI). Kiểm chứng
  bằng tcpdump khi bấm nút chụp (Ngày 9). GỬI cần `connect('udp')`.
- **Điều khiển bay** — khung API đã sẵn (`sdk.flight_control.send_virtual_stick(throttle,
  yaw, pitch, roll)`, `request_control_authority()`), đúng hình dạng tìm trong APK (4 float
  + auth). Nhưng **frame DUML chưa biết** (phải bay mới bắt được) → các hàm này báo "cần
  Frida". Phương pháp bắt lệnh: `tools/duml_tx_watch.py` (tcpdump, không tiêm app) — thao
  tác MỘT trục chậm, frame nào payload biến thiên mượt = lệnh đó (như đã làm với gimbal).
- **GPS, vận tốc ngang** — cần bay ngoài trời / bay ngang để kiểm chứng.

## Kiểm thử

`python tests/test_sdk.py` — 9 test: round-trip encode/decode (frame DUML, header ngoài,
tunnel lồng), lệnh xin keyframe **trùng byte** frame thật, và giải mã telemetry trên pcap thật.

Nền tảng giao thức: `notes/tien-do-giai-ma.md`, `notes/capture-log.md`.
