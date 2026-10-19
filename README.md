# neo2-msdk — MSDK tự xây cho DJI Neo 2

DJI **Neo 2** chưa được MSDK V5 chính thức hỗ trợ. Dự án này **reverse-engineer giao thức**
giữa app DJI Fly và drone (qua Wi-Fi trực tiếp), rồi **tự xây một MSDK** theo convention MSDK V5
để đọc telemetry, nhận video, và (sau này) điều khiển — không cần DJI Fly.

> Nghiên cứu/giáo dục trên thiết bị của chính nhóm. Mọi thí nghiệm bay thực hiện có kiểm soát.

## Tình trạng

| Mảng | Trạng thái |
|---|---|
| Hiểu giao thức (header ngoài, DUML, tunnel) | ✅ |
| Video H.265 (không mã hóa, 960×720@30) | ✅ giải mã ra hình |
| Telemetry: pin, tư thế, độ cao, vận tốc dọc, gimbal, trạng thái bay | ✅ kiểm chứng thực nghiệm |
| **SDK đọc** (telemetry + video), Key-based như MSDK V5 | ✅ `neo2sdk/`, test offline |
| Lệnh **xin keyframe** (dựng byte chính xác) | ✅ trùng y hệt app |
| Lệnh **điều khiển bay** (virtual stick) | ⏳ cần Frida hook động ở lab |
| GPS / vận tốc ngang | ⏳ cần bay ngoài trời / bay ngang |

Không tìm thấy bằng chứng mã hóa: telemetry + video + đọc-tham-số đều plaintext.

## Cấu trúc repo

```
neo2sdk/        SDK tự xây (Transport → Core → Keys → MSDKManager). Xem neo2sdk/README.md
examples/       read_telemetry.py, save_video.py, monitor.py (dashboard)
tests/          test_sdk.py — 9 test (encode/decode round-trip, byte-exact, telemetry)
poc/            script phân tích gốc (dò trường, khảo sát giao thức, trích video)
tools/frida/    duml_sniff.js — sniffer lệnh điều khiển (sẵn cho buổi lab)
notes/          tài liệu: giao thức, nhật ký capture, báo cáo lab, đọc thêm
captures/       pcap + video (KHÔNG commit — gitignore, có hình người)
apk/            APK DJI Fly (KHÔNG commit)
```

## Dùng nhanh (offline, trên pcap đã bắt)

```bash
# Đọc telemetry qua API Key-based
python examples/read_telemetry.py captures/cap_09_flight_indoor.pcap

# Dashboard trực quan (phát lại đúng nhịp thời gian)
python examples/monitor.py captures/cap_09_flight_indoor.pcap

# Ghép video ra H.265
python examples/save_video.py captures/cap_02_idle_30s.pcap out.h265

# Chạy test
python tests/test_sdk.py
```

Khi có drone, mọi thứ chạy y hệt — chỉ đổi nguồn: `sdk.connect("udp")`.

```python
from neo2sdk import MSDKManager
from neo2sdk.keys import BatteryKey, FlightControllerKey

sdk = MSDKManager()
sdk.connect("udp")                       # cùng mạng drone
sdk.key_manager.listen(FlightControllerKey.Altitude, lambda h: print("cao", h))
sdk.start()
```

## Tài liệu

- `notes/tien-do-giai-ma.md` — sơ đồ cấu trúc gói + phương pháp + bản chất + ví dụ gói thật.
- `notes/capture-log.md` — nhật ký chi tiết từng thí nghiệm (pin, gimbal, hướng, bay, Frida…).
- `notes/bao-cao-ngay-3-6.md` — báo cáo lab.
- `notes/apk-key-catalog.md` — danh mục khả năng SDK trích từ APK.
- `HANDOVER_neo2-msdk.md` — bối cảnh và kế hoạch gốc.

## Lộ trình

- **Phase 1 (đang làm):** đọc telemetry + video + điều khiển cơ bản bằng chương trình tự revert.
  Đọc đã xong; điều khiển chờ lấy frame lệnh qua Frida.
- **Phase 2:** đóng gói thành MSDK, tích hợp vào sample app MSDK gốc (Android/Kotlin).
- **Phase 3:** mở cho người khác lập trình trên MSDK này.
