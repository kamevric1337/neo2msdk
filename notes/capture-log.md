# Capture log (Ngày 3)

Kịch bản: điện thoại (192.168.2.12) ↔ Neo 2 (192.168.2.1) qua Wi-Fi trực tiếp, không dùng RC.
Drone MAC: 4c:43:f6:d8:b6:3a. Không có default route trên điện thoại khi ở mạng này, chỉ có
route nội bộ 192.168.2.0/24 dev wlan0.

## cap_02_idle_30s.pcap
- Thời điểm: 2026-09-29, ~13:06:46 → 13:07:16 (30.19s)
- Hành động: không thao tác gì trên app, đã kết nối và đang xem video sẵn từ trước khi bắt đầu capture
- Lệnh: `tcpdump -i wlan0 -s 0 -w /sdcard/cap_02_idle_30s.pcap` (chạy nền qua `su`, dừng bằng SIGINT)
- Kích thước: 26 841 642 bytes, 19452 frame
- Protocol hierarchy: eth > ip > {udp: 19356 frame, tcp: 62 frame, icmp: 30 frame} + arp: 4 frame
- **Chỉ có 1 luồng UDP**: `192.168.2.1:9003 <-> 192.168.2.12:41390`
  - Chiều drone→điện thoại (port 9003 src): 18399 frame / ~26 MB — nghi là video
  - Chiều điện thoại→drone: 957 frame / ~199 kB — nghi là điều khiển/heartbeat

### Phát hiện cấu trúc payload trên cổng 9003 (quan trọng cho Ngày 4/6)

Có **hai kiểu gói** khác hẳn nhau trên cùng 1 cổng UDP:

**Kiểu A — gói nhỏ/vừa (< ~200 byte), có cấu trúc rõ:**
- Bắt đầu bằng **header ngoài cố định 34 byte**, sau đó mới là các frame DUML nối tiếp nhau
  (mỗi frame bắt đầu bằng `0x55`, đúng Phụ lục B của HANDOVER).
- Ví dụ header 34 byte quan sát được (hex): `22 80 b0 ab 00 00 01 b8 68 c2 f8 c2 00 00 00 00
  78 5d 78 5d 00 00 00 00 78 5d 78 5d 00 00 00 00 00 00`
- So sánh nhiều gói: byte 8-11 (`68 c2 f8 c2`) và byte 2-3 (`b0 ab`) **không đổi** trong suốt
  30 giây capture → có thể là ID phiên/thiết bị. Byte 0-1 và 6-7 thay đổi nhẹ giữa các gói →
  có thể là số thứ tự/sequence. Cặp giá trị lặp lại "78 5d 78 5d" (little-endian = 0x5d78 =
  23928) xuất hiện 2 lần trong header → có thể là timestamp/counter không đổi trong cửa sổ
  capture ngắn này, cần capture dài hơn để xác nhận có tăng theo thời gian không.
- Một số gói chỉ có đúng 34 byte (chỉ header, không có frame DUML nào theo sau) → có thể là
  gói "keep-alive" thuần.
- **Chưa gán được dissector tự động**: `dji-dumlv1-proto.lua` (từ o-gs/dji-firmware-tools) chỉ
  đăng ký heuristic cho `usb.bulk` và `tcp`, KHÔNG có `udp`. Đã thêm dòng
  `DJI_DUMLv1_PROTO:register_heuristic("udp", heuristic_dissector)` vào cuối file (chỉ sửa bản
  local trong `tools\dji-dissectors`, không phải thay đổi lên upstream). Do heuristic chỉ kiểm
  tra byte đầu tiên của buffer UDP phải là `0x55`, và ở đây có 34 byte header đứng trước, nên
  **heuristic vẫn chưa tự nhận diện được** — cần viết thêm 1 dissector Lua nhỏ tách 34 byte đầu
  rồi gọi `dji_dumlv1_main_dissector` cho phần còn lại, hoặc dùng "Decode As" thủ công với
  offset trong Wireshark. Việc này để làm tiếp ở Ngày 4.

**Kiểu B — gói lớn (~1470-1490 byte):**
- Dữ liệu byte ngẫu nhiên hoàn toàn, không thấy `0x55` lặp lại, không có mẫu nào lặp lại giữa
  các gói kế tiếp.
- Nhiều khả năng đây là **luồng video đã nén (H.264/H.265)** — video nén vốn có entropy cao,
  trông giống ngẫu nhiên dù KHÔNG mã hóa. Chưa thể kết luận có mã hóa hay không chỉ từ việc này;
  cần đối chiếu với code APK ở Ngày 5 để biết drone có mã hóa kênh video hay không.

### Việc cần làm tiếp (Ngày 4)
- [ ] Viết dissector Lua nhỏ (hoặc dùng Python/scapy trong `poc\`) tách header 34 byte rồi parse
      các frame DUML phía sau trên cổng 9003.
- [ ] Xác định ý nghĩa từng trường trong header 34 byte bằng cách capture dài hơn / nhiều lần,
      xem trường nào tăng đều (sequence/timestamp) và trường nào cố định (ID phiên).
- [ ] Đối chiếu cmd set/cmd id của các frame DUML tìm được với `dji-dumlv1-flyc.lua`,
      `dji-dumlv1-general.lua`, `dji-dumlv1-gimbal.lua`, `dji-dumlv1-camera.lua` để tìm trường
      pin (battery), vì `dji-dumlv1-proto.lua` chỉ có phần lõi giao thức, chưa có định nghĩa
      các cmd set cụ thể.
- [ ] Xác nhận kênh video (gói lớn) có mã hóa hay không — đối chiếu Ngày 5.
