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
- [x] Xác nhận kênh video (gói lớn) có mã hóa hay không — KHÔNG mã hóa, H.265 960x720, đã giải mã
      ra hình bằng ffmpeg (xem cuối file).

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
- Frame DUML hợp lệ xuất hiện cả trong một số gói lớn của kênh điều khiển (vd. cap_02: 578/17180
  gói lớn drone→app), không chỉ gói < 200 byte. (Bản trước ghi "~859k gói có ≥1 frame" là SAI —
  859 516 là tổng số gói > 34 byte được quét, không phải số gói có frame.)

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
  - ĐÃ giải mã thực bằng ffmpeg — xem mục "Giải mã video bằng ffmpeg" bên dưới.
- Gói drone→app loại "khác" (byte6=0x02, < 1000 byte, 473 gói ở cap_02) = gói cuối của khung hình
  video (ngắn hơn), không phải kênh riêng.

### Kết nối lại (cap_01, t=63.73s)
- Gói đầu tiên sau gián đoạn là app→drone byte6=`0x00` (bắt tay), ID phiên chuyển sang `0xabb1`.
- +0.058s app gửi thẳng (không qua tunnel) `set 0x00 id 0x01` tới `0x0e`, `0x1f`, `0xa2`, `0x00`
  và `set 0x07 id 0x93` tới `0x07` → nghi là lệnh hỏi phiên bản / đăng ký thiết bị.
- +0.160s drone bắt đầu đẩy lại telemetry qua tunnel như bình thường.

### Giải mã video bằng ffmpeg — CHỐT: video KHÔNG mã hóa
- ffmpeg 9.0.2 cài qua `winget install Gyan.FFmpeg --scope user` (choco lỗi vì cần quyền admin).
  Binary: `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_...\ffmpeg-9.0.2-full_build\bin\`
  (PATH chỉ có hiệu lực ở shell mới).
- Script: `poc/extract_video.py` (ghép `payload[20:]` kênh 0x02, tùy chọn `--params` mượn VPS/SPS/PPS).
- ffprobe: `hevc`, profile Main, 960x720, yuv420p. Giải mã ra ảnh camera drone rõ nét (cảnh trong
  phòng) → xác nhận 100% luồng video là H.265 thô, không mã hóa. Ảnh trích nằm ở
  `captures/frames_cap01/`, `captures/frames_cap04/` (gitignored — có người trong khung hình).
- **Drone KHÔNG gửi keyframe định kỳ:** VPS/SPS/PPS + IDR chỉ xuất hiện khi mở phiên / nối lại
  (cap_01 t≈63.7s). cap_02 (30s) và cap_04 (23 phút) không có bộ tham số hay IDR nào. Giải mã
  giữa phiên: mượn bộ tham số của phiên khác (`--params captures/cap_01.h265` — dùng được, nghĩa là
  cấu hình encoder giống nhau giữa các phiên) + `ffmpeg -flags2 +showall -err_detect ignore_err`.
  Ảnh bắt đầu xám rồi hiện dần qua các khối intra trong P-frame (khung 15, 60 còn mờ; khung 600 gần
  rõ, vẫn còn vài vùng khối) → phục hồi kiểu intra-refresh chậm. Hệ quả cho SDK: khi tự nhận video
  giữa phiên phải chờ vài chục giây mới có hình sạch, hoặc tìm lệnh DUML yêu cầu I-frame (nhiều khả
  năng app gửi lệnh này khi nối lại — chưa xác định).
- Kết quả đếm khung (`ffprobe -count_frames`, có `+showall`):
  - cap_01: 324 khung (chỉ đoạn sau VPS lúc nối lại; ~23.7s trước đó không giải mã vì bộ tham số
    nằm sau trong file — chạy lại với `--params` nếu cần). 26 chỗ nhảy seq (phần lớn quanh lúc
    mất kết nối).
  - cap_02: 905/905 khung (khớp đúng 905 TRAIL_R đếm được), 2 chỗ nhảy seq.
  - cap_04: 41 442 khung trong ~1382s (13:16:54.8 → 13:39:56.7) = 30.0 fps, giải mã hết cả capture
    23 phút chỉ với bộ tham số mượn từ cap_01. 55 chỗ nhảy seq trong 782 326 gói video.

# Ngày 4

## cap_05_keyframe.pcap
- Mục tiêu: tìm lệnh DUML app gửi để yêu cầu keyframe (IDR) — đối chiếu lệnh app→drone ngay trước
  mỗi lần VPS/SPS/PPS + IDR xuất hiện với giai đoạn bình thường.
- Bắt đầu ghi: 2026-10-02 14:15:22 (giờ điện thoại), tcpdump PID 29992,
  `/sdcard/cap_05_keyframe.pcap`. DJI Fly đã kết nối Neo 2 và đang xem video từ trước.
- Mốc thao tác (giờ điện thoại):
  - Bước 1 (nền, không thao tác): 14:15:22 → 14:16:46 (~84s, dài hơn 30s dự kiến — không sao,
    nền dài hơn càng tốt). Người dùng nhắn lúc 14:16:46.
  - Bước 2 (Home, DJI Fly ra nền): người dùng nhắn "2" lúc 14:17:11.
  - Bước 3 (mở lại DJI Fly, video hiện lại): người dùng nhắn "3" lúc 14:17:35.
  - Bước 4 (Album rồi quay lại camera, video hiện lại): người dùng nhắn "4" lúc 14:17:57.
  - Bước 5 (Home ~10s rồi mở lại, video hiện lại): người dùng nhắn "5" lúc 14:18:31.
- Dừng ghi: 14:18:37 (SIGINT), ~6s sau bước 5. File ~164 MB, đã kéo về `captures/cap_05_keyframe.pcap`.

### Kết quả phân tích cap_05: lệnh xin keyframe (ứng viên rất mạnh, CHƯA thử chủ động)
Script: `poc/keyframe_events.py`. ID phiên giữ nguyên `0xd54c` suốt capture (ra nền / Album KHÔNG
làm app nối lại). Video chỉ ngắt khi vào Album (14:17:45.26 → 14:17:52.07, 6.8s); lúc app ra nền
drone vẫn gửi video bình thường.

Ba lần VPS + IDR, khớp bước 3/4/5 (người dùng báo trễ ~5s, giống thí nghiệm pin):
14:17:29.977 · 14:17:52.065 · 14:18:25.620. Trong nền (14:15:22–14:17:11, 109s) không có cái nào.

Trước mỗi lần, app gửi một **cặp lệnh cùng seq DUML** — cả hai đều KHÔNG xuất hiện trong nền:
1. `0x02→0xe9 set 0x18 id 0x47` (gửi thẳng, ngoài tunnel), payload 10 byte
   `00 08 [b2 b3 b4] 00 [cờ] 00 00 00` — b2..b4 (u24 LE) tăng ~1/ms → nghi là bộ đếm thời gian;
   cờ = `01` (xin) / `00`.
2. `0x02→0x09 set 0x01 id 0x01` (trong tunnel), payload 11 byte `00 00 00 00 00 [X] 00 00 00 [X] 00`,
   X = `0x24` khi cờ = 01, `0x04` khi cờ = 00 → **bit 0x20 nghi là "xin keyframe"**.
- Module `0x09` trả ACK `0x09→0x02 set 0x01 id 0x01 attr 0x80`, payload `00` (OK).
- App gửi từng loạt: 1–3 cặp X=0x24 rồi vài cặp X=0x04, cách nhau ~50 ms, sau đó ngừng.
- 5/5 loạt X=0x24 (3 ở cap_05, 2 ở cap_01 lúc nối lại) đều được đáp bằng VPS+IDR sau 0.01–0.7s.
  Ở cap_05 bước 4 (Album), VPS tới 0.67s sau, đúng lúc video chạy lại sau khi bị ngắt.
- Lưu ý: lúc mở phiên (cap_01, 13:13:51.75) drone TỰ gửi VPS trước khi app xin; trong lúc nối lại
  cũng có vài VPS không đi sau X=0x24 → drone có thể tự gửi keyframe lúc khởi động luồng.
- Chưa biết lệnh nào trong cặp thật sự kích hoạt keyframe, hay phải có cả hai. Module `0x09` nghi
  là bộ mã hóa video / truyền hình; `0xe9` là đầu tunnel phía drone.
- **Bước kiểm chứng cần làm:** tự gửi lại (replay) cặp lệnh với X=0x24 khi đang xem video giữa
  phiên, xem drone có gửi VPS+IDR không; thử riêng từng lệnh. Cần tự dựng header ngoài 34 byte
  (ID phiên, checksum XOR, độ dài), seq DUML mới và CRC — đây là lần đầu GỬI gói tới drone.

### Đối chiếu APK: xác nhận lệnh xin keyframe (Việc 1, Ngày 4)
Công cụ: giải nén .so từ APK + đọc chuỗi (strings) + disassemble ARM64 (capstone) trong
`tools`/script tạm. KHÔNG gửi gì tới drone — chỉ đọc tĩnh.

**Bằng chứng tên hàm/khóa trong SDK (khớp đúng cặp lệnh tìm được ở cap_05):**
- `libsdk_jni.so`, `libsdk_key_value.so`: khóa/hành động **`AppRequestIFrame`**.
- `libsdk_jni.so` có symbol `uav::sdk::CameraAbstraction::ActionAppRequestIFrame(...)` → hành động
  "app xin I-frame" thuộc nhóm **Camera**.
- `libsdk_jni.so`: `uav::sdk::BaseAbstraction::SendActionPack<uav::core::app_request_i_frame>` và
  kiểu phản hồi `uav_camera_get_app_request_i_frame_rsp` → có lệnh gửi đi tên `app_request_i_frame`
  kèm gói phản hồi riêng (khớp ACK `0x09→0x02` quan sát được).
- `libsdk_jni.so`: `uav::sdk::PigeonLiveViewIFrameRequest::RequestIFrame()`.
- `libsdk_key_value.so`: `RequireIFrameMsg`, `IFrameInfo`, **`PM430RequestIFrame`** (PM430 = tên mã
  nền tảng, nhiều khả năng của chính Neo 2), `RequireIFrame`.
- `libuav_video_jni.so` (lớp giải mã video phía app):
  - `[VideoStreamActionFeature][Demand-I] sendRequestNewIFrame___too fast` → app tự giới hạn tần
    suất xin I-frame. **Khớp đúng** hành vi quan sát ở cap_05: app bắn 1–3 lần cờ=01 rồi thôi.
  - `isDecodingFailRequestIFrame` → app xin I-frame khi giải mã lỗi (vd. vào/ra Album, mất gói).
  - `requestBlackIFrame`, `GetBlackIFrame`, `DummyIFrame` → app có "I-frame đen" dựng sẵn để hiện
    tạm trong lúc chờ keyframe thật (giải thích vì sao đôi khi màn hình có khung đen/xám ngắn).

**Disassemble hàm dựng lệnh (libsdk_jni.so ~0x1f70560):** hàm đẩy một mục vào hàng đợi lệnh với
`cmd_id = 0x47` (`strh w12,[x8]` với w12=0x47) và hằng số `0x18` (`w11=0x18`) gần đó — khớp
`cmd_set 0x18 / cmd_id 0x47` của lệnh `0x02→0xe9` ở cap_05. (Chưa lần hết chuỗi gọi tới tận nơi
đặt cmd_set, nhưng cặp hằng số + tên hàm `AppRequestIFrame` ở cùng vùng là đủ mạnh.)

**Kết luận Việc 1:** gần như chắc chắn cặp lệnh ở cap_05 là **lệnh app xin I-frame (keyframe)**:
- `0x02→0xe9 set 0x18 id 0x47` + `0x02→0x09 set 0x01 id 0x01`, byte payload `0x24` (bit 0x20 bật)
  = "xin ngay", `0x04` = không xin.
- Đích `0x09` = "HD transmission MCU air side" (bộ truyền hình trên drone) theo bảng DUML — hợp lý.
- Vẫn nên replay để chốt 100% và biết lệnh nào trong cặp là bắt buộc, nhưng KHÔNG còn là suy đoán
  thuần: tên hàm trong SDK xác nhận cơ chế tồn tại và đúng ngữ cảnh (xin khi lỗi giải mã, có giới
  hạn tần suất).

(Ghi chú: `libdatajar.so` 205 MB là ELF bọc nhiều tài nguyên nén, không phải dex; tên lớp Kotlin
`com/mtmd/video/stream/GDRIFrame`, `uav/sdk/keyvalue/value/camera/IFrameInfo` nằm trong đó.)

### Dissector Wireshark cho giao thức Neo 2 (Việc 4, Ngày 4)
File: `tools/dji-dissectors/dji-neo2-udp.lua`. Đăng ký trên `udp.port == 9003`, đã thêm dòng
`dofile('dji-neo2-udp.lua')` vào `%APPDATA%\Wireshark\plugins\init.lua` (nạp sau dji-dumlv1-proto).
Giải mã: header ngoài (độ dài, ID phiên, seq video, loại kênh, checksum XOR + cờ hợp lệ, ACK),
đi theo frame DUML kể cả frame lồng trong tunnel 0x51/0x01 (đệ quy, kiểm CRC8 để tìm biên), và
gọi lại `dji_dumlv1_main_dissector` cho chi tiết từng frame. Chú thích 2 trường đã kiểm chứng:
`dji_neo2.battery_pct` và `dji_neo2.keyframe_request`.
Kiểm thử bằng tshark trên cap_02/cap_05: 0 lỗi dissector, phân bố kênh khớp khảo sát Python
(cap_02: 1324 kênh 0x01, 17075 video, 957 kênh 0x04), 3 lần keyframe_request==1 ở cap_05 đúng
3 mốc thao tác. Bộ lọc hữu ích: `dji_neo2.keyframe_request==1`, `dji_neo2.battery_pct`,
`dji_neo2.checksum_ok==0`, `dji_neo2.channel==2`.

Kiểm chứng trên file lớn (cap_04, 1.23 GB): dissector đọc đúng `dji_neo2.battery_pct`, giảm đơn
điệu 67→66→65→64→63→62 theo số frame tăng, khớp kết quả Python. Checksum: 0 gói sai thật trên
cap_02 (con số "1" khi đếm trước đó là dòng "debug: Tools Menu Handler" lọt vào stdout, không phải
gói). Kết luận: toàn bộ gói 9003 có checksum XOR hợp lệ — dissector dùng được cho cả lab.

# Ngày 5

## cap_06_gimbal.pcap
- Mục tiêu: tìm trường góc nghiêng gimbal (pitch) trong telemetry bằng phương pháp thay đổi có
  kiểm soát (như tìm trường pin). Drone đặt yên dưới đất, KHÔNG cất cánh, động cơ tắt.
- Bắt đầu ghi: 2026-10-02, tcpdump PID 8834, `/sdcard/cap_06_gimbal.pcap`. DJI Fly đã kết nối.
- Mốc thao tác (giờ điện thoại):
  - Bước 1 (gimbal NẰM NGANG 0°, giữ ~10s): 16:08:15
  - Bước 2 (gimbal XUỐNG hết cỡ, giữ ~10s): 16:09:16
  - Bước 3 (gimbal LÊN hết cỡ, giữ ~10s): 16:09:45
  - Bước 4 (gimbal về NẰM NGANG 0°, giữ ~10s): 16:10:11
- Dừng ghi: 16:10:19 (SIGINT). File ~330 MB, đã kéo về `captures/cap_06_gimbal.pcap`.
- Kỳ vọng: một trường i16 LE trong telemetry gimbal (nghi src=0x04) hoặc FC bám theo pitch:
  ~0 ở bước 1 & 4, âm lớn (hoặc dương) ở bước 2 (xuống), ngược dấu ở bước 3 (lên). Độ trễ app
  ~4-5s như thí nghiệm pin.

### Kết quả phân tích cap_06: ĐÃ TÌM RA trường góc gimbal (pitch)
Script: `poc/gimbal_field.py` (+ phân tích quaternion). Drone nằm yên dưới đất cả buổi → mọi field
đổi giá trị giữa 4 cửa sổ giữ yên đều do gimbal. Phương pháp: field phải PHẲNG trong mỗi lần giữ,
KHÁC nhau giữa các lần (tỉ lệ biên độ/nhiễu cao).

**Frame gimbal: `src=0x04 (Gimbal) → dst=0x02 (App)`, `cmd_set=0x04`, `cmd_id=0x05`, payload 50 byte.**
Hai trường bám theo góc, xác nhận chéo lẫn nhau:

1. **payload[0:2] = i16 LE = pitch gimbal, đơn vị 0.1° (decidegree).**
   - B1 ngang=0 (0.0°) · B2 xuống=-728 (-72.8°) · B3 lên=+1024 (+102.4°) · B4 ngang=0 (0.0°).
   - Dấu: âm = chúc xuống, dương = ngẩng lên. Về đúng 0 khi để ngang (cả 2 lần).

2. **payload[24:40] = quaternion hướng camera (w,x,y,z, mỗi số float32 LE).** |q|=1.000 cả 4 bước.
   - B1/B4 ngang: (0.787, 0, 0, -0.618) trùng khít nhau → pitch Euler = -0.0°.
   - B2 xuống: pitch = -72.8° (khớp chính xác trường (1)).
   - B3 lên: Euler cho +77.6° kèm roll 180° (gấp Euler) → tức pitch thực 180-77.6 = 102.4°, khớp
     trường (1) = +1024. Thành phần z≈-0.617 không đổi ở 2 mốc ngang = hướng mũi drone (yaw cố định
     ~-76°, hợp lý vì drone không xoay).

Đối chiếu độ trễ: giá trị telemetry trên dây phản ánh góc gần như tức thời (đọc trực tiếp, không
qua hiển thị app), nên không có độ trễ ~5s như thí nghiệm pin (độ trễ pin là do app cập nhật số).

Các field "cùng dấu ở cả xuống và lên" (vd. 0x04/0x05 off=9 = 0/16384/16384/0) là cờ "gimbal lệch
khỏi vị trí giữa", không phải góc có dấu.

- [x] Gán trường gimbal pitch (việc Ngày 5) — xong, xác nhận bằng 2 trường độc lập.
- [ ] Gán trường hướng drone (yaw/pitch/roll IMU) — xoay drone bằng tay khi tắt động cơ (chưa làm).

## cap_07_gimbal2.pcap — lặp lại cap_06 để xác nhận trường gimbal
- Bắt đầu ghi: 2026-10-02 16:18:51, tcpdump PID 9492, `/sdcard/cap_07_gimbal2.pcap`. Drone yên dưới đất.
- Mốc thao tác (giờ điện thoại):
  - Bước 1 (gimbal NẰM NGANG 0°): 16:19:25
  - Bước 2 (gimbal XUỐNG hết cỡ): 16:19:58
  - Bước 3 (gimbal LÊN hết cỡ): 16:20:31
  - Bước 4 (gimbal về NẰM NGANG 0°): 16:21:06
- Dừng ghi: ~16:21:08 (SIGINT). File ~119 MB, đã kéo về `captures/cap_07_gimbal2.pcap`.
- **XÁC NHẬN LẠI trường gimbal** (cả payload[0:2] i16 0.1° và quaternion payload[24:40] khớp nhau
  tuyệt đối ở cả 4 mốc):
  - B1 ngang: -0.1° · B2 xuống: **-90.0°** (tròn, hết tầm) · B3 lên: **+70.0°** · B4 ngang: -0.5°.
  - Lần này gimbal lên chỉ +70° nên Euler không bị gấp như cap_06 → quaternion và i16 trùng khít.
  - Kết luận chắc chắn: `0x04→0x02 set=0x04 id=0x05`, payload[0:2] = pitch (0.1°), payload[24:40]
    = quaternion hướng camera. Tầm pitch gimbal quan sát: khoảng -90° (chúc thẳng xuống) đến +70..+102°.
- Dissector `dji-neo2-udp.lua` đã thêm trường `dji_neo2.gimbal_pitch_ddeg`; tshark đọc đúng ở các
  cửa sổ giữ yên (lúc gimbal đang quay nhanh thì hiện giá trị quá độ, bình thường).

## cap_08_attitude.pcap — tìm trường hướng drone (yaw/pitch/roll IMU)
- Drone động cơ TẮT, cầm/nghiêng bằng tay. Mục tiêu: tách 3 trường yaw/pitch/roll bằng cách đổi
  từng trục một từ tư thế phẳng.
- Bắt đầu ghi: 2026-10-02 16:23:59, tcpdump PID 9686, `/sdcard/cap_08_attitude.pcap`.
- Mốc thao tác (giờ điện thoại):
  - Bước 1 (PHẲNG, mũi hướng trước - gốc): 16:24:54
  - Bước 2 (XOAY NGANG ~90° CW, yaw): 16:25:23
  - Bước 3 (CHÚC MŨI XUỐNG ~45°, pitch): 16:32:00
  - Bước 4 (NGHIÊNG TRÁI ~45°, roll): 16:32:43
  - Bước 5 (PHẲNG lại như gốc): 16:33:12
- Dừng ghi: ~16:33:1x (SIGINT). File ~481 MB, đã kéo về `captures/cap_08_attitude.pcap`.

### Kết quả: hướng thân drone nằm trong FC OSD General, LAYOUT CHUẨN DJI
Frame `src=0x03 (FC) → dst=0x0e set=0x03 id=0x43` ("OSD General Data"), payload 85 byte, đẩy ~10 Hz.
Trùng khớp cấu trúc `flyc_osd_general` trong `dji-dumlv1-flyc.lua` (offset tính từ đầu payload sau
11 byte header DUML):
- **payload[24:26] = pitch (i16, 0.1°)**
- **payload[26:28] = roll  (i16, 0.1°)**
- **payload[28:30] = yaw   (i16, 0.1°, = hướng la bàn)**

Kiểm chứng cap_08 (đổi từng trục một từ phẳng; đơn vị độ):
| bước | pitch | roll | yaw |
|---|---|---|---|
| B1 phẳng    | -2.5  | +0.2  | -70.5 |
| B2 xoay 90° | -2.3  | +0.1  | **+28.8** (Δ≈+99°) |
| B3 chúc mũi | **+34.1** | -3.7 | -64.0 |
| B4 nghiêng trái | -3.1 | **+42.5** | -72.0 |
| B5 phẳng    | -2.6  | +0.0  | -67.1 |

Mỗi trục chỉ đổi mạnh ở đúng bước của nó; B1≈B5 (về gần tư thế gốc). pitch/roll phẳng ~0° (lệch
nhỏ do đặt tay + drone kê không hoàn toàn cân). → kết luận chắc chắn.

Hệ quả lớn: Neo 2 dùng **layout OSD General chuẩn DJI** → dissector DUML có sẵn tự parse đúng
pitch/roll/yaw, và các trường cùng frame (lat/lon [0:16] double, relative_height [16:18], vận tốc
vgx/vgy/vgz [18:24], flyc_state, GPS…) nhiều khả năng cũng chuẩn — sẽ kiểm khi bay thật. Vì
dissector `dji-neo2-udp.lua` đã bàn giao frame lồng cho `dji_dumlv1_main_dissector`, các trường này
tự hiện trong Wireshark, KHÔNG cần thêm code.

- [x] Gán trường hướng drone (yaw/pitch/roll) — xong, FC OSD General chuẩn DJI, offset 24/26/28.

### Tổng kết trường telemetry đã xác định (Ngày 3-5)
| Đại lượng | Frame (src→dst set/id) | Vị trí payload | Đơn vị | Bản ghi |
|---|---|---|---|---|
| % pin | 0x0b→0x02 0x0d/0x02 | [20] u8 | % | cap_04 |
| Xin keyframe | 0x02→0x09 0x01/0x01 | [5] bit 0x20 | cờ | cap_05 |
| Gimbal pitch | 0x04→0x02 0x04/0x05 | [0:2] i16 + quat [24:40] | 0.1° | cap_06/07 |
| Drone pitch | 0x03→0x0e 0x03/0x43 | [24:26] i16 | 0.1° | cap_08 |
| Drone roll | 0x03→0x0e 0x03/0x43 | [26:28] i16 | 0.1° | cap_08 |
| Drone yaw | 0x03→0x0e 0x03/0x43 | [28:30] i16 | 0.1° | cap_08 |
