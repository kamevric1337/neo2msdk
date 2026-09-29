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

> **ĐÍNH CHÍNH (parse lại bằng CRC, xem mục "Cấu trúc gói cổng 9003 — parse lại cap_01/cap_02"
> ở cuối file):** các nhận định dưới đây về byte 2-3 / 6-7 / 8-11, "78 5d" là timestamp, và
> "gói lớn là video chưa rõ có mã hóa" đã được thay thế. Giữ nguyên bên dưới làm lịch sử.

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
- [x] Viết dissector Lua nhỏ (hoặc dùng Python/scapy trong `poc\`) tách header 34 byte rồi parse
      các frame DUML phía sau trên cổng 9003. → `poc/duml_survey.py` (Python, kiểm CRC).
- [x] Xác định ý nghĩa từng trường trong header 34 byte bằng cách capture dài hơn / nhiều lần,
      xem trường nào tăng đều (sequence/timestamp) và trường nào cố định (ID phiên). → xem cuối file.
- [ ] Đối chiếu cmd set/cmd id của các frame DUML tìm được với `dji-dumlv1-flyc.lua`,
      `dji-dumlv1-general.lua`, `dji-dumlv1-gimbal.lua`, `dji-dumlv1-camera.lua` để tìm trường
      pin (battery), vì `dji-dumlv1-proto.lua` chỉ có phần lõi giao thức, chưa có định nghĩa
      các cmd set cụ thể.
- [x] Xác nhận kênh video (gói lớn) có mã hóa hay không — KHÔNG mã hóa, H.265 960x720 (xem cuối file).
      Còn nên giải mã thử bằng ffmpeg để chốt 100%.

## cap_01_connect.pcap
- Thời điểm: 2026-09-29, ngay sau cap_02_idle_30s
- Hành động: tắt Wi-Fi trên điện thoại, đợi vài giây, bật lại, chờ tự kết nối lại và xem video
  trở lại. tcpdump chạy nền trước khi tắt Wi-Fi, dừng sau khi video hiện lại.
- Kích thước: 27 005 416 bytes, 20649 frame, thời lượng capture ~74.7s
- Protocol hierarchy thấy thêm (so với lúc idle): EAPOL (8 frame — bắt tay WPA), DHCP (9 frame),
  ARP (38 frame), cùng DNS/TLS/HTTP/NTP lạc — traffic nền của điện thoại khi Wi-Fi vừa lên lại,
  không liên quan tới Neo 2.
- **Mốc thời gian quan trọng** (frame.time_relative, giây thứ mấy kể từ lúc bắt đầu capture):
  - t=23.7s: gói cuối cùng tới/từ port 9003 trước khi mất kết nối (khớp lúc tắt Wi-Fi)
  - t=42.75s–42.94s: bắt tay EAPOL (4 message) + DHCP Request/ACK — nhưng đây là **kết nối
    nhầm vào mạng khác**: ARP ngay sau đó cho thấy điện thoại có IP `192.168.2.77` nói chuyện
    với `192.168.2.253` (không phải `192.168.2.1` của Neo 2). Có polling ARP lặp lại nhiều lần
    tới `192.168.2.1` không có trả lời trong khoảng t=43–62s → đúng là chưa nối lại được Neo 2.
  - t=63.12s–63.34s: bắt tay EAPOL + DHCP Discover/Offer/Request/ACK lần 2 — lần này đúng mạng
    Neo 2, điện thoại nhận lại IP cũ `192.168.2.12`.
  - t=63.7s: gói đầu tiên tới/từ port 9003 xuất hiện trở lại (drone 192.168.2.1).
  - **Tổng thời gian gián đoạn traffic với drone: ~40 giây** (23.7s → 63.7s), phần lớn do điện
    thoại tự nối nhầm mạng khác trước khi quay lại đúng Neo 2.
- Ý nghĩa: khi test capture "mất kết nối / nối lại" thực tế trên máy này, nên tắt hẳn Wi-Fi của
  mạng khác (hoặc đứng ngoài vùng phủ của mạng đó) để tránh nhiễu kết quả, hoặc chấp nhận độ trễ
  ~40s do hành vi tự chọn mạng của Android.

## cap_04_battery_drain.pcap
- Bắt đầu ghi: 2026-09-29 13:16:56 (giờ điện thoại, lệnh `date` qua adb)
- Mốc % pin quan sát trên app DJI Fly (nguồn: người dùng đọc màn hình, đối chiếu giờ điện thoại):
  - 79% → 78%: xảy ra khoảng 13:16:27 (ước lượng, người dùng báo "khoảng 20s trước" lúc 13:16:47)
    — mốc này XẢY RA TRƯỚC khi bắt đầu ghi (13:16:56), không nằm trong pcap, chỉ ghi để tham khảo
    tốc độ giảm pin.
  - 78% → 77%: người dùng báo lúc công cụ `adb shell` đang lỗi tạm thời (transient classifier
    error), không lấy được giờ ngay lúc đó. Giờ điện thoại lấy được ngay khi công cụ hoạt động
    lại: 13:20:22 — mốc 77% xảy ra TRƯỚC thời điểm này, sai số ước lượng khoảng 1-2 phút do độ
    trễ chờ công cụ. Coi mốc này là kém chính xác hơn các mốc khác, không dùng để tính chính xác
    tốc độ giảm pin.
  - 77% → 76%: người dùng báo lúc công cụ `adb shell` lại lỗi tạm thời lần nữa (kéo dài qua nhiều
    lần thử, cộng thêm gián đoạn do đổi chế độ quyền `/permissions`). Giờ điện thoại lấy được khi
    công cụ hoạt động lại: 13:24:24 — mốc 76% xảy ra TRƯỚC thời điểm này, sai số ước lượng khá lớn
    (có thể vài phút) do khoảng gián đoạn công cụ kéo dài. Coi mốc này kém chính xác nhất trong
    các mốc đã ghi.
  - 76% → ... → 72%: KHÔNG bắt được từng mốc trung gian (75/74/73%) — trong lúc này người dùng
    và Claude đang xử lý sự cố công cụ + đổi cấu hình `/permissions`, không theo dõi màn hình
    liên tục. Người dùng chỉ báo lại đã thấy 72% sau khi quay lại theo dõi. Không có giờ chính
    xác cho các mốc này.
  - 70% → 69%: người dùng báo xảy ra ĐÚNG lúc gửi tin nhắn báo — nhưng công cụ `adb shell` (cả
    Bash và PowerShell) đều lỗi tại thời điểm đó nên không lấy được giờ điện thoại ngay. Cần lấy
    bù giờ khi công cụ ổn định trở lại và coi đây là mốc tốt thứ nhì (biết chính xác THỜI ĐIỂM
    tương đối so với tin nhắn, chỉ thiếu giờ tuyệt đối).
    - Lấy bù (khi resume session): adb hoạt động lại, giờ điện thoại 13:35:01 — mốc 69% xảy ra
      TRƯỚC thời điểm này (không rõ bao lâu, do gián đoạn giữa hai session). tcpdump vẫn đang chạy
      (PID 9542), file pcap ~972 MB lúc 13:35:04 → capture KHÔNG bị ngắt.
  - 69% → ... → 66%: các mốc 68/67% KHÔNG bắt được (nằm trong khoảng gián đoạn giữa hai session).
    Người dùng báo pin đang 66% (đọc trạng thái, không phải khoảnh khắc chuyển mốc) — giờ điện
    thoại lúc nhận tin: 13:35:33. Đây KHÔNG phải thời điểm 67→66%, chỉ biết mốc đó xảy ra trước
    13:35:33.
  - 66% → 65%: người dùng báo "giờ 65 r" — giờ điện thoại lúc nhận tin: 13:35:50. Chỉ 17s sau
    lần đọc 66% (13:35:33), nhanh bất thường so với các mốc trước (vài phút/1%). Cách báo ("đã 65
    rồi") không chắc là khoảnh khắc chuyển mốc → coi 13:35:50 là giới hạn trên, mốc 65% nằm trong
    khoảng (13:35:33, 13:35:50]. Có thể 66% đã hiển thị từ lâu trước 13:35:33.
  - 65% → 64%: người dùng báo "64 rồi" — giờ điện thoại lúc nhận tin: 13:37:22 (92s sau lần báo
    65%). Chưa rõ người dùng báo ngay khi số nhảy hay vài giây sau → tạm coi 13:37:22 là giới hạn
    trên, sai số dự kiến nhỏ (vài giây) nếu người dùng đang canh màn hình.
    → Người dùng xác nhận: KHÔNG báo ngay lúc số nhảy → mốc 64% chỉ là giới hạn trên
      (xảy ra trong khoảng (13:35:50, 13:37:22]). Mốc chính xác đầu tiên sẽ là 64% → 63%.
  - 64% → 63%: **MỐC CHÍNH XÁC** — người dùng canh màn hình, nhắn "63" ngay khi số nhảy. Giờ
    điện thoại: 13:38:22 (sai số vài giây: thời gian gõ tin + độ trễ adb). Mốc tham chiếu tốt nhất
    để đối chiếu với pcap.
  - 63% → 62%: **MỐC CHÍNH XÁC** — người dùng nhắn "62" ngay khi số nhảy. Giờ điện thoại:
    13:39:53 (sai số vài giây). Cách mốc 63% 91s → tốc độ ~1.5 phút/1%, khớp với khoảng 65→64.
- Dừng ghi: 13:39:57 (SIGINT tới tcpdump PID 9542), ngay sau mốc 62%.
- Kết quả: 1 229 911 847 byte (~1.23 GB), ~899k gói, gói đầu 13:16:54.84, gói cuối 13:39:56.74.
  Đã kéo về `captures/cap_04_battery_drain.pcap`.
- Gợi ý phân tích: tìm trong các gói DUML một byte đổi 0x40→0x3F quanh 13:38:22 VÀ 0x3F→0x3E
  quanh 13:39:53 (hai mốc chính xác). Các mốc khác chỉ dùng để kiểm tra chéo.

### Kết quả phân tích cap_04: ĐÃ TÌM RA trường % pin
Script: `poc/find_battery_field.py` (stdlib, ~50s cho file 1.23 GB).

**Sửa hiểu biết cũ về cổng 9003** (xem phần cap_02 ở trên):
- Frame DUML KHÔNG chỉ nối liền nhau từ byte 34. Frame `cmd_set 0x51 / cmd_id 0x01`
  (`0x27→0xee`, `0x3b→0xe9`, chiếm phần lớn frame) là **tunnel**: payload của nó chứa các frame
  DUML khác. Các frame thật nằm ở nhiều offset (34, 45 = 34+11, …).
- Cách parse đúng: quét mọi `0x55`, nhận frame khi qua CRC8 header (init 0x77, poly 0x8C
  reflected) và CRC16 (init 0x3692, poly 0x8408 reflected). Trên 30k gói nhỏ: 76 245 frame qua
  cả 2 CRC, chỉ 107 qua CRC8 mà trượt CRC16 → tiêu chí rất sạch.
- Frame DUML hợp lệ xuất hiện cả trong các gói lớn (~859k gói có ≥1 frame), không chỉ gói < 200 byte.

**Trường % pin** (khớp cả 2 mốc chính xác, giảm đơn điệu 78→62, đổi đúng 16 lần):
1. `src=0x0b (pin) → dst=0x02 (app)`, `cmd_set=0x0d`, `cmd_id=0x02`, payload dài 44 byte,
   **payload[20]** = % pin (uint8). Gửi ~1 lần/giây. → Nguồn gốc, dùng cái này.
2. `src=0x03 (flight controller) → dst=0x02` và `→ dst=0x0e`, `cmd_set=0x03`, `cmd_id=0x55`,
   payload dài 10 byte, **payload[8]** = % pin. Luôn trễ ~0.05–1s sau (1) → FC chuyển tiếp lại.
   (Tên "FlyC Limit State Get" trong `dji-dumlv1-flyc.lua` là của dòng drone cũ, không áp dụng.)

Thời điểm chuyển mốc trong pcap (nguồn 1): 78→77 13:17:55.8 · 77→76 13:19:32.2 · 76→75 13:21:08.7 ·
75→74 13:22:25.0 · 74→73 13:23:59.7 · 73→72 13:25:35.1 · 72→71 13:27:09.7 · 71→70 13:28:24.8 ·
70→69 13:29:57.3 · 69→68 13:31:30.8 · 68→67 13:32:45.3 · 67→66 13:34:00.0 · 66→65 13:35:32.2 ·
65→64 13:37:03.7 · 64→63 13:38:17.3 · 63→62 13:39:48.7. Tốc độ ~75–97s/1%.

Đối chiếu với mốc người dùng: hai mốc chính xác trễ **4.9s** (63) và **4.3s** (62) so với pcap →
tổng độ trễ hiển thị app + phản ứng + gõ tin + adb ≈ 4–5s, nhất quán. Mọi mốc không chính xác đều
khớp giới hạn trên đã ghi (vd. 64% trong pcap 13:37:03.7, người dùng báo 13:37:22 → trễ ~18s, đúng
với việc người dùng xác nhận không báo ngay). Lần đọc "66%" lúc 13:35:33 xảy ra 1s sau khi pcap đã
sang 65 → nằm trong độ trễ hiển thị ~4–5s, hợp lý.

Mẫu payload 0x0d/0x02 (44 byte), trước/sau mốc 63%:
```
13:38:16.239 00 57 1e 00 00 55 fd ff ff 67 06 00 00 18 04 00 00 ff 01 02 40 00 00 00 00 03 80 00 00 13 01 64 00 00 f0 80 08 01 00 00 40 80 6b 00
13:38:17.251 00 58 1e 00 00 64 fd ff ff 67 06 00 00 15 04 00 00 ff 01 02 3f 00 00 00 00 03 80 00 00 13 01 64 00 00 f0 80 08 01 00 00 40 80 6b 00
```
Giả thuyết CHƯA kiểm chứng cho các trường khác (cần capture có sạc/tải khác nhau để xác nhận):
- payload[1:3] u16 LE = 7767→7768 → điện áp mV (~7.77 V, hợp với pin 2S)?
- payload[5:9] i32 LE = -683 / -668 → dòng mA (âm = xả)?
- payload[13:15] u16 LE = 1048→1045 → dung lượng còn lại mAh?
- payload[31] = 100 → sức khỏe pin %?

- [x] Tìm trường pin (việc Ngày 4) — xong.
- [x] Cập nhật parser cho cap_01/cap_02 theo cách quét CRC mới; xem lại các nhận định về header 34 byte.

## Cấu trúc gói cổng 9003 — parse lại cap_01/cap_02
Script: `poc/duml_survey.py` (chạy trong `poc/`). Mọi kết luận dưới đây đúng 100% số gói trên cả
cap_01 và cap_02 trừ khi ghi khác.

### Header chung 16 byte đầu (mọi gói, cả hai chiều)
| Byte | Ý nghĩa | Bằng chứng |
|---|---|---|
| 0-1 | u16 LE = `0x8000 \| độ dài payload UDP` (bit 15 luôn bật) | khớp 19356/19356 (cap_02), 19826/19826 (cap_01) |
| 2-3 | ID phiên kết nối, **tăng 1 mỗi lần kết nối lại**: `0xabb0` → `0xabb1` đúng ở gói đầu tiên sau khi nối lại (cap_01, t=63.73s); cap_04 vẫn `0xabb1` | cap_01 |
| 4-5 | Kênh video: số thứ tự gói, **+8 mỗi gói** (17072/17075 bước). Kênh khác: 0 | bước ≠8 = mất gói/nối lại |
| 6 | **Loại kênh**: `0x01` drone→app DUML/keep-alive · `0x02` drone→app video · `0x04` app→drone DUML/keep-alive · `0x00` gói bắt tay khi nối lại (1 gói/chiều, cap_01) | |
| 7 | **Checksum = XOR byte 0..6** | 19356/19356, 19825/19825 |
| 8-11 | app→drone: hai u16 bằng nhau = **seq video mới nhất app đã nhận (ACK)** — hiệu số với seq video mới nhất trong pcap: trung vị 0, p90 0. drone→app kênh 1: cặp giá trị seq video (chưa rõ nghĩa chính xác). Kênh video: [8:10] = seq gói đầu của khung hình?, [10:12] = seq của chính gói | |
| 12-15 | thường 0 | |

(Nhận định cũ "byte 8-11 không đổi, có thể là ID phiên" là SAI — chỉ không đổi trong vài gói liền nhau.
Nhận định cũ "byte 6-7 là sequence" là SAI — byte 6 là loại kênh, byte 7 là checksum.)

### Kênh DUML (byte6 = 0x01 / 0x04): header 34 byte
- Byte 16-31: gần như luôn `78 5d 78 5d 00 00 00 00 78 5d 78 5d 00 00 00 00` (không phải timestamp —
  không đổi trong cả capture 23 phút cap_04). Chưa rõ nghĩa.
- Byte 32-33: u16 LE = độ dài phần sau header (khớp 99.9% gói app→drone và mọi gói DUML drone→app).
- Sau byte 34: các frame DUML nối liền nhau (918/927 gói nhỏ app→drone "kín"), hoặc không có gì
  (gói 34 byte = keep-alive).
- Frame cấp ngoài gần như luôn là tunnel `0x27→0xee` (drone→app) / `0x3b→0xe9` (app→drone)
  `cmd_set 0x51 cmd_id 0x01`, chứa frame DUML thật bên trong. Ngoài tunnel chỉ có vài lệnh gửi
  thẳng: `0x02→0xa9 set 0x01 id 0x0a` (app, ~20/s), `0x07→0x02 set 0x07 id 0x94` (~1/s).
- Frame lồng phổ biến (drone→app): `0x92→0x02 set 0x23 id 0xb2`, `0x28→0x02 set 0x00 id 0x99`,
  `0x03→0x0e set 0x03 id 0x43` (FC OSD?), `0x04→0x02 set 0x04 id 0x05` (gimbal?), `0x01→0x02 set
  0x02 id 0x80`, … ~10 Hz. Pin: `0x0b→0x02 set 0x0d id 0x02` (xem phần cap_04).

### Kênh video (byte6 = 0x02): header 20 byte, **H.265 KHÔNG mã hóa**
- Byte 16-19: trường riêng của video (vd. `f8 13 60 6d`, `f8 93 60 6d`, `f8 13 61 6d`), chưa giải mã.
- Byte 20+: luồng H.265 Annex-B, ghép liền `payload[20:]` các gói kênh 2 là ra bitstream hợp lệ.
  Gói bắt đầu khung hình có `00 00 00 01` ngay tại byte 20 (908 gói / 30.2s ≈ **30 fps**).
- Kiểm tra trên cap_01 (ghép ra `captures/cap_01_video.h265`, 23.96 MB):
  - SPS: profile Main, level 5.0, 4:2:0, **960x720**.
  - Mỗi khung: AUD (35) → TRAIL_R (1) → 2× SUFFIX_SEI (40); 1093 khung. Sau khi nối lại có
    VPS/SPS/PPS (32/33/34) + IDR (20) / CRA (21).
  - 0 vi phạm emulation-prevention trong 24 MB — dữ liệu mã hóa sẽ gây vài vi phạm ngẫu nhiên.
  - ~40 start code lạ (loại NAL hiếm/sai header) — nghi do mất gói / đoạn nối lại, CHƯA kiểm chứng.
  - Chưa giải mã thực bằng ffmpeg (máy chưa cài) — bước chốt còn lại.
- Gói drone→app loại "khác" (byte6=0x02, < 1000 byte, 473 gói ở cap_02) = gói cuối của khung hình
  video (ngắn hơn), không phải kênh riêng.

### Kết nối lại (cap_01, t=63.73s)
- Gói đầu tiên sau gián đoạn là app→drone byte6=`0x00` (bắt tay), ID phiên chuyển sang `0xabb1`.
- +0.058s app gửi thẳng (không qua tunnel) `set 0x00 id 0x01` tới `0x0e`, `0x1f`, `0xa2`, `0x00`
  và `set 0x07 id 0x93` tới `0x07` → nghi là lệnh hỏi phiên bản / đăng ký thiết bị.
- +0.160s drone bắt đầu đẩy lại telemetry qua tunnel như bình thường.
