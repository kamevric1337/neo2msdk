# neo2sdk — Tài liệu API

Tham chiếu API cho MSDK tự xây của DJI Neo 2. Phiên bản `0.1.0` (PoC, đường đọc).
Tổng quan kiến trúc: `neo2sdk/README.md`. Nền tảng giao thức: `notes/tien-do-giai-ma.md`.

Quy ước trạng thái: ✅ đã kiểm chứng thực nghiệm · 🟡 theo chuẩn, chưa kiểm chứng (cần bay) ·
🔜 đã có khung API, chờ frame (Frida).

---

## Mục lục
1. [Bắt đầu](#1-bắt-đầu)
2. [MSDKManager](#2-msdkmanager)
3. [KeyManager & Key](#3-keymanager--key)
4. [Danh mục Key](#4-danh-mục-key)
5. [Kiểu giá trị](#5-kiểu-giá-trị)
6. [FlightControl (điều khiển)](#6-flightcontrol-điều-khiển)
7. [Video](#7-video)
8. [Tầng Transport (nâng cao)](#8-tầng-transport-nâng-cao)
9. [Lệnh (core.commands)](#9-lệnh-corecommands)
10. [Công thức thường dùng](#10-công-thức-thường-dùng)

---

## 1. Bắt đầu

```python
from neo2sdk import MSDKManager
from neo2sdk.keys import FlightControllerKey, BatteryKey

sdk = MSDKManager()
sdk.connect("captures/cap_09_flight_indoor.pcap")   # offline; hoặc "udp" khi có drone
sdk.key_manager.listen(BatteryKey.PercentRemaining, lambda v: print("pin", v))
sdk.start()                                          # chạy đến hết pcap (hoặc mãi với udp)
print(sdk.key_manager.get_value(FlightControllerKey.Attitude))
```

Lõi SDK chỉ dùng **thư viện chuẩn Python** (không phụ thuộc ngoài). Yêu cầu Python ≥ 3.9.

---

## 2. MSDKManager

Điểm vào tầng cao nhất. Vòng đọc: `nguồn gói → parse header → demux kênh → telemetry/video`.

```python
sdk = MSDKManager()
```

**Thuộc tính**
| Tên | Kiểu | Ý nghĩa |
|---|---|---|
| `key_manager` | `KeyManager` | API Key-based (đọc telemetry) |
| `flight_control` | `FlightControl` | API điều khiển (xem §6) |
| `video` | `VideoDecoder` | bộ giải mã video (xem §7) |
| `session_id` | `int` | ID phiên hiện tại, cập nhật từ gói đến (cần để dựng lệnh gửi) |
| `stats` | `dict` | `{packets, duml_frames, telemetry_updates, video_packets}` |

**Phương thức**

### `connect(source) → self`
Chọn nguồn gói.
- `source="đường/dẫn.pcap"` — đọc file đã bắt (offline, dev/test).
- `source="udp"` — nhận trực tiếp từ drone (cùng mạng 192.168.2.x).
- `source=<iterable>` — nguồn tự cấp, sinh `(timestamp, udp_payload_bytes)`.
  (vd `PcapSource(path, realtime=True)` để phát đúng nhịp thời gian thật.)

### `on_video(callback) → self`
Đăng ký nhận từng chunk bitstream H.265. `callback(chunk: bytes)`.

### `start(background=False) → self`
Chạy vòng đọc. `background=True` chạy luồng nền (không chặn; dùng cho `udp` hoặc dashboard).
Với pcap (không realtime) thì chạy tới hết file rồi trả về.

### `stop()`
Dừng vòng đọc (và join luồng nền nếu có).

### `build_request_iframe(request=True) → bytes`
Dựng **gói** xin keyframe cho `session_id` hiện tại, **không gửi**. Dùng được offline.
`request=False` để gửi cờ "thôi xin".

### `request_iframe(request=True) → bool`
Dựng **và GỬI** lệnh xin keyframe (cần `connect("udp")`). Ném `RuntimeError` nếu chưa kết nối live.

---

## 3. KeyManager & Key

API đọc telemetry theo kiểu MSDK V5: cache giá trị mới nhất + listener.

```python
km = sdk.key_manager
```

### `get_value(key: Key) → value | None`
Giá trị mới nhất của `key` (None nếu chưa có).

### `listen(key: Key, callback)`
Đăng ký `callback(value)` — gọi mỗi lần `key` có giá trị mới. Listener lỗi không làm sập vòng đọc.

### `remove_listener(key: Key, callback)`
Gỡ một listener đã đăng ký.

### `set_value(key: Key, value)`
Ghi (điều khiển). **Chưa hỗ trợ** — ném `NotImplementedError` (đường điều khiển cần Frida).

### Lớp `Key`
Bất biến, băm được. Thuộc tính: `component`, `name`, `path` (`"Component.Name"`), `readable`, `writable`.

---

## 4. Danh mục Key

Import: `from neo2sdk.keys import FlightControllerKey, BatteryKey, GimbalKey, SystemKey`

### `FlightControllerKey`
| Key | Kiểu giá trị | TT |
|---|---|:---:|
| `.Attitude` | `Attitude` (pitch,roll,yaw °) | ✅ |
| `.Altitude` | `float` (m, so với điểm cất cánh) | ✅ |
| `.Velocity` | `Velocity3D` (m/s, NED) | ✅ dọc / 🟡 ngang |
| `.CompassHeading` | `float` (độ) | ✅ |
| `.FlightState` | `int` (flyc_state; 6=đất, 43=bay) | ✅ |
| `.Status` | `FlightStatus` (cờ bay đầy đủ) | ✅ in_air/motor |
| `.IsFlying` / `.AreMotorsOn` | `bool` | ✅ |
| `.Location` | `GpsLocation` (độ) | 🟡 cần ngoài trời |
| `.SatelliteCount` | `int` | 🟡 |
| `.UltrasonicHeight` | `float` (m) | 🟡 |

### `BatteryKey`
| Key | Kiểu giá trị | TT |
|---|---|:---:|
| `.Info` | `BatteryInfo` (đầy đủ) | ✅ |
| `.PercentRemaining` | `int` (%) | ✅ |

### `GimbalKey`
| Key | Kiểu giá trị | TT |
|---|---|:---:|
| `.Attitude` | `GimbalAttitude` (pitch, quaternion) | ✅ |

### `SystemKey`
| Key | Kiểu giá trị | TT |
|---|---|:---:|
| `.ComponentTemperatures` | `dict{str: list[float °C]}` (wifi/esc/imu/baro…) | ✅ |

`ALL_READABLE` — danh sách mọi key đọc được (tiện lặp để log hết).

---

## 5. Kiểu giá trị

Import: `from neo2sdk.core import Attitude, Velocity3D, BatteryInfo, GimbalAttitude, GpsLocation, FlightStatus`

```python
Attitude(pitch: float, roll: float, yaw: float)              # độ
Velocity3D(x: float, y: float, z: float)                     # m/s, NED (z>0 = đi xuống)
BatteryInfo(percent, voltage_mv, current_ma, remain_mah,     # current<0 = đang xả
            full_mah, cells, temp_c)
GimbalAttitude(pitch: float, quaternion: tuple|None)         # (w,x,y,z)
GpsLocation(latitude: float, longitude: float)               # độ
FlightStatus(flyc_state, in_air, on_ground, motors_on,
             gps_used, gps_level, satellites, gohome_state,
             battery_req_gohome, battery_req_land)
```

---

## 6. FlightControl (điều khiển)

`sdk.flight_control` — API điều khiển bay. Hình dạng khớp kiến trúc tìm trong APK
(`RequestJoystickControlAuth` + `MobileRCHandler::SendCmd`, 4 float).

| Phương thức | TT | Ghi chú |
|---|:---:|---|
| `request_iframe(request=True)` | ✅ | xin keyframe (gửi khi live) |
| `request_control_authority()` | 🔜 | xin quyền điều khiển — ném `NotImplementedError` |
| `release_control_authority()` | 🔜 | trả quyền |
| `send_virtual_stick(throttle, yaw, pitch, roll)` | 🔜 | 4 trục [-1,1]; cần frame từ Frida |

`JoystickConfig(throttle, yaw, pitch, roll)` — `.clamped()` kẹp về [-1,1].

> 🔜 = khung sẵn, **thiếu frame DUML** của lệnh BAY (phải bay mới bắt được). Lấy bằng
> `tools/duml_tx_watch.py` (tcpdump, không tiêm app — DJI Fly có chống debug nên Frida bị app tự kill)
> khi đẩy cần, rồi điền hàm dựng byte trong `core/commands.py` (mẫu: `gimbal_speed_frame`).

### GimbalControl — `sdk.gimbal_control`

Điều khiển tốc độ gimbal. Lệnh đã **giải mã + dựng byte chính xác** (frame `0x02→0x04 set 0x04 id 0x0c`).

| Phương thức | TT | Ghi chú |
|---|:---:|---|
| `set_pitch(s)` | ✅ | pitch chuẩn hóa `s∈[-1,1]` (dương=ngẩng lên); gửi khi live |
| `send_speed(yaw, roll, pitch)` | ✅ | tốc độ THÔ mỗi trục, kẹp ±200; gửi khi live |
| `stop()` | ✅ | tốc độ 0 mọi trục |
| `build_speed(yaw, roll, pitch)` | ✅ | chỉ DỰNG gói (offline), không gửi |

payload 8 byte = `yaw|roll|pitch` (i16 LE) `| 0x80 | 0x00`; hết cỡ ±200 (kiểm chứng Ngày 9).
GỬI cần `connect('udp')` (PC cùng mạng drone 192.168.2.x); `build_speed` thì offline cũng được.

### CameraControl — `sdk.camera_control`

| Phương thức | TT | Ghi chú |
|---|:---:|---|
| `shoot_photo(mode=1)` | ✅ | chụp ảnh — `0x02→0x01 set 0x02 id 0x01`, payload `01`; gửi khi live |
| `start_record()` / `stop_record()` | ✅ | quay video — `set 0x02 id 0x02`, payload `01`/`00`; gửi khi live |
| `build_shoot_photo(mode=1)` / `build_record(start)` | ✅ | chỉ DỰNG gói (offline) |

---

## 7. Video

`sdk.video` là `VideoDecoder`. Dùng `sdk.on_video(cb)` để nhận chunk H.265 (Annex-B), ghi ra `.h265`
rồi phát bằng ffmpeg.

```python
f = open("out.h265", "wb")
sdk.on_video(f.write)
sdk.start(); f.close()
```

Thuộc tính: `video.bytes_out`, `video.lost_packets`.
Lưu ý: drone không gửi keyframe định kỳ → bản ghi giữa phiên mờ rồi rõ dần (xem
`notes/tien-do-giai-ma.md` §6.1). Cần bộ tham số VPS/SPS/PPS từ lúc mở phiên/kết nối lại để giải mã sạch.

---

## 8. Tầng Transport (nâng cao)

Khi cần thao tác byte thô (vd phân tích, tự dựng công cụ).

Import: `from neo2sdk.transport import parse_outer, build_outer, build_duml_app_packet,
iter_frames, build_frame, crc8, crc16, PcapSource, UdpSource`

### Header ngoài
```python
parse_outer(payload: bytes) -> OuterPacket | None
# OuterPacket: length, session_id, video_seq, channel, channel_name, checksum_ok, body, raw

build_outer(channel, body, session_id, video_seq=0, video_ack=0) -> bytes
build_duml_app_packet(frame, session_id, video_ack=0) -> bytes   # gói app->drone mang 1 khung DUML
```
Hằng số kênh: `CH_HANDSHAKE=0x00, CH_DUML_DRONE=0x01, CH_VIDEO=0x02, CH_DUML_APP=0x04`.

### Khung DUML
```python
iter_frames(buf: bytes, start=0) -> Iterator[DumlFrame]   # qua CRC8+CRC16, kể cả frame lồng tunnel
# DumlFrame: src, dst, cmd_set, cmd_id, seq, payload, nested; .key()=(src,dst,cmd_set,cmd_id)

build_frame(src, dst, cmd_set, cmd_id, payload=b"", seq=0,
            encrypt=0, ack=0, pack_type=0) -> bytes        # tự tính CRC, version=1
crc8(data, crc=0x77) ; crc16(data, crc=0x3692)
```

### Nguồn gói
```python
PcapSource(path, realtime=False)   # realtime=True: phát đúng nhịp thời gian thật
UdpSource(bind_host="0.0.0.0", bind_port=9003)   # .send(packet) gửi tới 192.168.2.1:9003
```
Cả hai lặp ra `(timestamp: float, udp_payload: bytes)`.

---

## 9. Lệnh (core.commands)

```python
from neo2sdk.core.commands import request_iframe_frame, request_iframe_packet

request_iframe_frame(seq=0, request=True) -> bytes     # khung DUML (trùng byte y hệt app)
request_iframe_packet(session_id, seq=0, request=True) -> bytes   # gói UDP hoàn chỉnh

from neo2sdk.core.commands import gimbal_speed_frame, gimbal_speed_packet
gimbal_speed_frame(yaw=0, roll=0, pitch=0, seq=0) -> bytes             # khung DUML gimbal (±200)
gimbal_speed_packet(session_id, yaw=0, roll=0, pitch=0, seq=0) -> bytes  # gói UDP hoàn chỉnh

from neo2sdk.core.commands import shoot_photo_frame, shoot_photo_packet, record_frame, record_packet
shoot_photo_frame(seq=0, mode=0x01) -> bytes              # khung DUML chụp ảnh
shoot_photo_packet(session_id, seq=0, mode=0x01) -> bytes # gói UDP hoàn chỉnh
record_frame(seq=0, start=True) -> bytes                  # khung DUML quay (start/stop)
record_packet(session_id, seq=0, start=True) -> bytes     # gói UDP hoàn chỉnh
```
Bốn lệnh điều khiển đã giải mã trọn vẹn và dựng byte chính xác: **xin keyframe**, **tốc độ
gimbal**, **chụp ảnh**, **quay video** (đều có test khớp byte payload mẫu thật). Lệnh bay chờ bắt khi bay.

---

## 10. Công thức thường dùng

**Đọc một giá trị một lần (sau khi chạy):**
```python
sdk = MSDKManager().connect("x.pcap"); sdk.start()
print(sdk.key_manager.get_value(FlightControllerKey.Altitude))
```

**Theo dõi realtime nền (cho dashboard / udp):**
```python
sdk.connect("udp").start(background=True)
while True:
    print(sdk.key_manager.get_value(BatteryKey.PercentRemaining)); time.sleep(1)
```

**Log mọi key ra console:**
```python
from neo2sdk.keys import ALL_READABLE
for k in ALL_READABLE:
    sdk.key_manager.listen(k, lambda v, k=k: print(k.path, v))
```

**Chuyển offline → live:** chỉ đổi `connect("x.pcap")` thành `connect("udp")`. Phần còn lại giữ nguyên.

Ví dụ đầy đủ: `examples/read_telemetry.py`, `save_video.py`, `monitor.py`, `log_csv.py`.
