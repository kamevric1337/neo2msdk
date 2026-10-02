# Báo cáo tiến độ: Phân tích giao thức DJI Fly ↔ DJI Neo 2 qua Wi-Fi

**Giai đoạn:** Phase 1 – PoC, Ngày 3 (bắt gói và phân tích lưu lượng)
**Thời gian thực hiện:** 29/09/2026
**Người thực hiện:** _(điền tên)_

---

## Thuật ngữ

Phần này giải thích các thuật ngữ kỹ thuật dùng trong báo cáo, xếp theo nhóm để dễ tra cứu.

### Dự án và công cụ

| Thuật ngữ | Giải thích |
|---|---|
| **SDK / MSDK** | *Software Development Kit*: bộ thư viện giúp lập trình viên viết ứng dụng cho một thiết bị. **MSDK** (Mobile SDK) là bộ SDK chính thức của DJI cho Android/iOS; bản hiện tại là MSDK V5, nhưng chưa hỗ trợ Neo 2. |
| **PoC** | *Proof of Concept*: bản thử nghiệm nhỏ để chứng minh một hướng làm là khả thi, chưa phải sản phẩm hoàn chỉnh. |
| **DJI Fly** | App chính thức của DJI để điều khiển drone và xem hình từ camera. |
| **APK** | File cài đặt app trên Android. |
| **Dịch ngược** (*reverse engineering*) | Phân tích một sản phẩm có sẵn (app, giao thức) để hiểu cách nó hoạt động khi không có tài liệu. |
| **Root / Magisk** | *Root* là quyền quản trị cao nhất trên Android. Magisk là công cụ phổ biến để cấp quyền root; ở đây cần root để chạy `tcpdump`. |
| **adb** | *Android Debug Bridge*: công cụ điều khiển điện thoại Android từ máy tính qua cáp USB. |
| **RC** | *Remote Controller*: tay điều khiển của drone. Trong thí nghiệm này không dùng RC, điện thoại nối thẳng với drone qua Wi-Fi. |
| **Chế độ monitor** | Chế độ đặc biệt của card Wi-Fi cho phép nghe toàn bộ sóng Wi-Fi xung quanh. Nhờ bắt gói ngay trên điện thoại nên không cần tới chế độ này. |

### Mạng và bắt gói

| Thuật ngữ | Giải thích |
|---|---|
| **Gói tin** (*packet*) | Đơn vị dữ liệu nhỏ nhất được gửi qua mạng. Mỗi lần drone hay app "nói" gì đó là gửi đi một hoặc nhiều gói. |
| **IP / subnet** | Địa chỉ IP (vd. `192.168.2.1`) xác định một thiết bị trong mạng. `192.168.2.0/24` là một mạng con (subnet) gồm các địa chỉ `192.168.2.x`. |
| **UDP** | Một giao thức truyền dữ liệu qua mạng: gửi nhanh, không đảm bảo gói đến nơi hay đến đúng thứ tự. Thường dùng cho video và điều khiển thời gian thực. |
| **Cổng** (*port*) | Số hiệu (vd. `9003`) giúp phân biệt các luồng dữ liệu khác nhau trên cùng một thiết bị. |
| **Luồng** | Toàn bộ các gói trao đổi giữa hai cặp địa chỉ + cổng cố định. |
| **Bắt gói** (*capture*) | Ghi lại toàn bộ gói tin đi qua một giao diện mạng để phân tích sau. |
| **tcpdump** | Công cụ dòng lệnh để bắt gói, có sẵn trên điện thoại dùng trong thí nghiệm. |
| **pcap** | Định dạng file chuẩn chứa các gói tin đã bắt, kèm thời điểm của từng gói. |
| **Wireshark** | Phần mềm có giao diện đồ họa để mở file pcap và xem chi tiết từng gói. |
| **Dissector** | Plugin của Wireshark dạy nó cách "đọc hiểu" một giao thức cụ thể, ví dụ tách các trường của DUML. |
| **TLS / mã hóa** | TLS là giao thức mã hóa phổ biến trên Internet. Dữ liệu đã mã hóa thì không đọc được nếu không có khóa. |

### Cấu trúc dữ liệu

| Thuật ngữ | Giải thích |
|---|---|
| **Byte** | Đơn vị dữ liệu 8 bit, giá trị từ 0 đến 255. "Byte thứ 20" nghĩa là byte ở vị trí 20, **đếm từ 0**. |
| **Hệ hex / `0x..`** | Cách viết số theo hệ 16, thường dùng khi làm việc với byte. Ví dụ `0x40` = 64, `0x3F` = 63, `0x55` = 85. |
| **Header** | Phần đầu của một gói hay frame, chứa thông tin quản lý: độ dài, loại dữ liệu, số thứ tự… |
| **Payload** | Phần dữ liệu thật mà gói hay frame mang theo, nằm sau header. |
| **Frame** | Một khối dữ liệu hoàn chỉnh có header và payload riêng. Một gói UDP có thể chứa nhiều frame. |
| **Checksum / CRC** | Giá trị kiểm tra tính toàn vẹn: bên gửi tính từ dữ liệu rồi gửi kèm, bên nhận tính lại để phát hiện lỗi. **CRC8/CRC16** là hai loại CRC dài 8 và 16 bit. **XOR** là một phép tính bit đơn giản, dùng làm checksum ở header ngoài. |
| **Số thứ tự** (*sequence number*) | Con số tăng dần theo từng gói, giúp bên nhận biết gói nào bị mất hoặc đến sai thứ tự. |
| **ACK** | *Acknowledgement*: thông báo của bên nhận rằng "tôi đã nhận được tới gói số X". |
| **ID phiên** | Con số định danh một lần kết nối. Mỗi lần kết nối lại, drone dùng một ID mới. |
| **Keep-alive** | Gói gửi định kỳ, không mang dữ liệu, chỉ để báo "tôi vẫn còn kết nối". |
| **Bắt tay** (*handshake*) | Các gói trao đổi đầu tiên khi mở kết nối, để hai bên nhận ra nhau và thống nhất thông số. |

### Giao thức DJI

| Thuật ngữ | Giải thích |
|---|---|
| **DUML** | Giao thức nội bộ mà các thành phần trong hệ thống DJI (app, flight controller, pin, gimbal, camera…) dùng để trao đổi lệnh và dữ liệu. Mỗi frame DUML bắt đầu bằng byte `0x55`. Cộng đồng đã tìm hiểu giao thức này từ các dòng drone cũ. |
| **Module / địa chỉ nguồn–đích** | Mỗi thành phần trong hệ thống có một địa chỉ riêng, ví dụ `0x02` là app, `0x03` là flight controller, `0x0b` là pin. Mỗi frame DUML ghi rõ gửi từ đâu tới đâu. |
| **cmd_set / cmd_id** | Hai byte xác định loại lệnh trong frame DUML: `cmd_set` là nhóm lệnh, `cmd_id` là lệnh cụ thể trong nhóm đó. |
| **Tunnel** | Frame "bọc" chứa bên trong nó các frame DUML khác, giống phong bì đựng nhiều lá thư. Neo 2 dùng tunnel `cmd_set 0x51 / cmd_id 0x01`. |
| **Telemetry** | Dữ liệu trạng thái drone gửi liên tục về app: pin, độ cao, tư thế, góc gimbal… |
| **Flight controller** | Bộ điều khiển bay, "bộ não" của drone. |
| **Gimbal** | Cơ cấu giữ camera, giúp hình ổn định khi drone rung lắc. |
| **Hz** | Số lần mỗi giây. "Gửi 10 Hz" nghĩa là gửi 10 lần mỗi giây. |

### Video

| Thuật ngữ | Giải thích |
|---|---|
| **H.265 / HEVC** | Chuẩn nén video hiện đại (hai tên gọi của cùng một chuẩn). Video nén nhìn qua giống dữ liệu ngẫu nhiên dù không hề bị mã hóa. |
| **Codec / giải mã** | *Codec* là bộ nén và giải nén video. *Giải mã* (decode) ở đây là giải nén để ra lại hình ảnh, khác với giải mã mật mã. |
| **ffmpeg / ffprobe** | Bộ công cụ xử lý video mã nguồn mở: `ffmpeg` giải mã và chuyển đổi, `ffprobe` đọc thông số. |
| **Khung hình** (*frame*) / **fps** | Một ảnh tĩnh trong video. *fps* là số khung hình mỗi giây; 30 fps là mức phổ biến. |
| **Keyframe / IDR** | Khung hình đầy đủ, giải mã được độc lập. **IDR** là loại keyframe trong H.265. |
| **P-frame** | Khung hình chỉ lưu phần *thay đổi* so với khung trước, nên nhỏ hơn nhiều nhưng cần khung trước mới giải mã được. |
| **Khối intra / intra-refresh** | *Khối intra* là một vùng nhỏ trong P-frame được lưu đầy đủ, không phụ thuộc khung trước. *Intra-refresh* là cách làm mới dần toàn bộ hình ảnh bằng các khối intra rải qua nhiều khung, thay vì gửi keyframe. |
| **VPS / SPS / PPS** | Ba khối "bộ tham số" của H.265, chứa thông tin như độ phân giải, cấu hình nén. Thiếu chúng thì decoder không giải mã được. |
| **NAL** | Đơn vị dữ liệu cơ bản trong luồng H.265. Mỗi khung hình, mỗi bộ tham số là một hoặc nhiều NAL. |
| **Profile Main / 4:2:0** | *Profile Main* là cấu hình H.265 phổ biến nhất. *4:2:0* là cách lưu màu tiết kiệm dung lượng, chuẩn cho video thông thường. |
| **960×720** | Độ phân giải: 960 điểm ảnh chiều ngang, 720 điểm ảnh chiều dọc. |

### Đơn vị pin

| Thuật ngữ | Giải thích |
|---|---|
| **V / mA / mAh** | Vôn (điện áp), mili-ampe (dòng điện), mili-ampe-giờ (dung lượng pin). |

---

## 1. Tóm tắt

DJI Neo 2 hiện chưa được MSDK V5 chính thức hỗ trợ, nên nhóm chọn hướng tìm hiểu giao thức giữa app
DJI Fly và drone để sau này tự xây một SDK riêng. Báo cáo này trình bày kết quả của ngày làm việc
đầu tiên với dữ liệu thật: bắt gói trên điện thoại trong lúc app đang kết nối trực tiếp với drone qua
Wi-Fi, sau đó phân tích offline.

Các kết quả chính:

1. **Toàn bộ giao tiếp đi qua một luồng UDP duy nhất** (drone `192.168.2.1:9003` ↔ điện thoại), và
   **không bị mã hóa**, kể cả phần điều khiển lẫn phần video.
2. **Đã giải được lớp header bao ngoài** của mỗi gói: độ dài, ID phiên, loại kênh, checksum, số thứ
   tự video và ACK từ phía app.
3. Bên trong kênh điều khiển là các **frame DUML** quen thuộc của DJI, phần lớn được **bọc trong một
   frame "tunnel"** (`cmd_set 0x51 / cmd_id 0x01`).
4. **Đã xác định được trường phần trăm pin** trong telemetry, kiểm chứng bằng một thí nghiệm theo dõi
   pin tụt trong 23 phút.
5. **Luồng video là H.265 thô (960×720, 30 fps)**, đã ghép lại và giải mã ra hình bằng ffmpeg. Drone
   không gửi keyframe định kỳ, điều này ảnh hưởng trực tiếp tới thiết kế phần nhận video của SDK.

---

## 2. Thiết lập thí nghiệm

| Thành phần | Chi tiết |
|---|---|
| Drone | DJI Neo 2, kết nối trực tiếp qua Wi-Fi (không dùng tay điều khiển RC) |
| Điện thoại | Samsung Galaxy S20 FE (SM-G780G), Android 13, đã root bằng Magisk |
| App | DJI Fly chính hãng, bản 1.21.10 (`dji.go.v5`) |
| Công cụ bắt gói | `tcpdump` có sẵn trên điện thoại, chạy với quyền root trên `wlan0` |
| Phân tích | Wireshark 4.6.8 + dissector DUML của cộng đồng (o-gs/dji-firmware-tools), script Python tự viết, ffmpeg 9.0.2 |

Mạng giữa điện thoại và drone là một mạng nội bộ `192.168.2.0/24`: drone ở `192.168.2.1`, điện thoại
nhận `192.168.2.12`. Bắt gói ngay trên điện thoại giúp thấy được toàn bộ lưu lượng hai chiều mà
không cần card Wi-Fi ở chế độ monitor.

Ba bản ghi đã thực hiện:

| Bản ghi | Kịch bản | Thời lượng | Dung lượng |
|---|---|---|---|
| `cap_02_idle_30s` | App đang xem video, không thao tác gì | 30 giây | 27 MB |
| `cap_01_connect` | Tắt Wi-Fi điện thoại rồi bật lại, chờ app tự kết nối lại | 75 giây | 27 MB |
| `cap_04_battery_drain` | Để drone chạy, ghi lại các mốc % pin hiển thị trên app | 23 phút | 1,23 GB |

---

## 3. Kết quả

### 3.1. Tổng quan lưu lượng

Khi app đang kết nối, gần như mọi thứ đều nằm trên **một luồng UDP duy nhất** giữa cổng 9003 của
drone và một cổng ngẫu nhiên trên điện thoại. Lưu lượng lệch hẳn về một phía: trong 30 giây, chiều
drone → điện thoại khoảng 26 MB (chủ yếu là video), còn chiều ngược lại chỉ khoảng 200 kB (lệnh và
xác nhận).

Không thấy dấu hiệu của TLS hay bất kỳ lớp mã hóa nào trên luồng này. Các frame DUML đọc được trực
tiếp và qua được kiểm tra CRC; luồng video giải mã được ra hình (mục 3.5).

### 3.2. Header bao ngoài của mỗi gói

Mỗi gói UDP bắt đầu bằng một header riêng của DJI, không thuộc DUML. 16 byte đầu có chung cấu trúc
cho mọi gói. Các ý nghĩa dưới đây được kiểm tra trên **toàn bộ** gói của hai bản ghi cap_01 và
cap_02 (khoảng 39 nghìn gói), và đều khớp 100% trừ chỗ có ghi chú:

| Byte | Ý nghĩa |
|---|---|
| 0–1 | Độ dài gói, cộng thêm bit cờ `0x8000` |
| 2–3 | **ID phiên kết nối**, tăng 1 mỗi lần kết nối lại (`0xabb0` → `0xabb1` đúng lúc app nối lại) |
| 4–5 | Số thứ tự gói video, tăng 8 sau mỗi gói (bằng 0 ở các kênh khác) |
| 6 | **Loại kênh**: `0x01` điều khiển drone→app, `0x02` video, `0x04` điều khiển app→drone, `0x00` gói bắt tay khi nối lại |
| 7 | **Checksum**: XOR của byte 0 đến 6 |
| 8–11 | Ở chiều app→drone là **số thứ tự gói video mới nhất app đã nhận** (ACK); ở các kênh khác chưa rõ hết ý nghĩa |

Kênh điều khiển có thêm 18 byte nữa (tổng cộng 34 byte), trong đó byte 32–33 là độ dài phần dữ liệu
phía sau. Kênh video chỉ dùng 20 byte header rồi tới dữ liệu hình ngay.

Các gói chỉ gồm đúng 34 byte header và không có dữ liệu xuất hiện đều đặn ở cả hai chiều, nhiều khả
năng là gói giữ kết nối (keep-alive).

### 3.3. Kênh điều khiển: frame DUML và lớp tunnel

Sau header là các frame theo định dạng DUML v1 mà cộng đồng đã mô tả cho các dòng drone DJI trước
(bắt đầu bằng `0x55`, có CRC8 cho header và CRC16 cho cả frame). Để tách frame một cách đáng tin
cậy, script quét mọi vị trí có byte `0x55` và chỉ chấp nhận frame qua được cả hai CRC. Tiêu chí này
rất "sạch": trên 30 nghìn gói thử nghiệm, có 76 245 frame qua cả hai CRC, chỉ 107 trường hợp qua CRC8
nhưng trượt CRC16.

Điểm khác biệt lớn so với các drone DJI cũ là **phần lớn frame được bọc trong một frame tunnel**
(`cmd_set 0x51 / cmd_id 0x01`, địa chỉ `0x27→0xee` ở chiều drone→app và `0x3b→0xe9` ở chiều
ngược lại). Payload của frame tunnel chứa tiếp các frame DUML "thật" bên trong. Chính lớp bọc này làm
dissector có sẵn của Wireshark không nhận ra được gì.

Bên trong tunnel, drone liên tục đẩy telemetry với tần số khoảng 10 Hz từ nhiều module khác nhau:
flight controller (`0x03`), gimbal (`0x04`), pin (`0x0b`), camera (`0x01`), và một số module chưa
xác định (`0x92`, `0x28`). Việc gán tên cho từng lệnh sẽ làm ở bước sau.

### 3.4. Xác định trường phần trăm pin

**Cách làm.** Trong lúc ghi `cap_04`, người thực hiện theo dõi phần trăm pin trên màn hình DJI Fly
và báo lại mỗi khi con số thay đổi; giờ trên điện thoại được lấy ngay qua `adb` để khớp với thời gian
trong file pcap. Hai mốc được canh chính xác nhất là **64%→63% lúc 13:38:22** và **63%→62% lúc
13:39:53**. Sau đó script dò trong toàn bộ frame DUML xem byte nào đổi giá trị đúng như vậy
(0x40→0x3F, rồi 0x3F→0x3E) trong khoảng thời gian tương ứng.

**Kết quả.** Có đúng một nguồn dữ liệu gốc khớp cả hai mốc:

- Frame từ **module pin (`0x0b`) gửi tới app (`0x02`)**, `cmd_set 0x0d / cmd_id 0x02`, gửi khoảng
  1 lần/giây. **Byte thứ 20 của payload là phần trăm pin.**
- Flight controller cũng gửi lại giá trị này trong frame `cmd_set 0x03 / cmd_id 0x55` (byte 8), luôn
  chậm hơn một chút, tức là chuyển tiếp từ nguồn trên.

Trong 23 phút ghi, giá trị này giảm đều từ 78 xuống 62, đổi đúng 16 lần, không có lần nào nhảy
ngược. Mỗi 1% pin mất khoảng 75–97 giây.

**Kiểm chứng.** Hai mốc chính xác mà người thực hiện báo chậm hơn thời điểm trong pcap lần lượt
4,9 và 4,3 giây. Độ trễ này nhất quán, và hợp lý khi cộng thời gian app hiển thị với thời gian phản
ứng và gõ tin nhắn. Các mốc được ghi kém chính xác hơn (do gián đoạn công cụ trong lúc thí nghiệm)
cũng đều nằm đúng trong khoảng thời gian đã ghi nhận.

Trong cùng payload có vài trường trông như điện áp (khoảng 7,77 V), dòng xả (khoảng −680 mA) và dung
lượng còn lại (khoảng 1045 mAh). Tuy nhiên các trường này **mới là giả thuyết**, cần thêm bản ghi ở
điều kiện khác (đang sạc, tải nặng) để xác nhận.

### 3.5. Luồng video: H.265 không mã hóa

Các gói lớn (khoảng 1470 byte) trên kênh `0x02` nhìn qua giống dữ liệu ngẫu nhiên, nên ban đầu chưa
loại trừ được khả năng bị mã hóa. Sau khi giải được header, ghép liền phần dữ liệu sau 20 byte đầu
của các gói này sẽ ra một **luồng H.265 (HEVC) chuẩn**:

- Thông số: profile Main, **960×720**, màu 4:2:0, khoảng **30 khung hình/giây**.
- ffmpeg giải mã ra hình ảnh camera rõ nét, nên có thể khẳng định **luồng video không bị mã hóa**.
- Số khung giải mã được: 905/905 khung với `cap_02`, và **41 442 khung** (đúng 30,0 fps) với toàn
  bộ 23 phút của `cap_04`.

Một đặc điểm quan trọng: **drone không gửi keyframe định kỳ.** Bộ tham số giải mã (VPS/SPS/PPS) và
khung IDR chỉ xuất hiện khi mở phiên hoặc kết nối lại. Hai bản ghi bắt giữa phiên (`cap_02`,
`cap_04`) hoàn toàn không có chúng. Hình ảnh vẫn giải mã được nếu mượn bộ tham số từ một phiên khác,
tức cấu hình encoder giữ nguyên giữa các phiên. Khi đó hình bắt đầu từ màu xám và rõ dần sau vài
trăm khung (khoảng 20 giây) nhờ các khối intra rải rác trong P-frame.

Hệ quả cho SDK: nếu bắt đầu nhận video giữa phiên, người dùng sẽ phải chờ khá lâu mới có hình sạch.
Muốn có hình ngay, SDK cần tìm ra lệnh yêu cầu keyframe mà app gửi cho drone.

### 3.6. Quá trình kết nối lại

Bản ghi `cap_01` cho thấy trình tự khi app nối lại với drone:

1. Gói đầu tiên là một gói bắt tay từ app (loại kênh `0x00`). Từ đây ID phiên tăng lên 1.
2. Khoảng 60 ms sau, app gửi một loạt lệnh DUML trực tiếp, không qua tunnel, tới nhiều module
   (`cmd_set 0x00 / cmd_id 0x01` và `cmd_set 0x07 / cmd_id 0x93`). Nhiều khả năng đây là bước hỏi
   phiên bản hoặc đăng ký thiết bị.
3. Khoảng 160 ms sau, drone gửi lại bộ tham số video kèm keyframe và bắt đầu đẩy telemetry như bình
   thường.

Lần thử này mất khoảng 40 giây gián đoạn, nhưng nguyên nhân là điện thoại tự nối nhầm sang một mạng
Wi-Fi khác trước khi quay lại đúng mạng của drone, không phải do drone. Các lần thử sau cần tắt mạng
Wi-Fi lân cận để đo chính xác hơn.

---

## 4. Những nhận định ban đầu đã được điều chỉnh

Trong quá trình phân tích, một số giả thuyết ban đầu tỏ ra sai và đã được sửa lại. Ghi lại ở đây
để minh bạch:

- Ban đầu cho rằng các frame DUML nằm nối tiếp nhau ngay sau header 34 byte. Thực tế phần lớn frame
  nằm lồng trong frame tunnel. Vì giả định sai này, lần dò trường pin đầu tiên không cho kết quả.
- Ban đầu đoán byte 6–7 là số thứ tự và byte 8–11 là ID phiên. Thực tế byte 6 là loại kênh, byte 7
  là checksum, còn ID phiên nằm ở byte 2–3.
- Chuỗi `78 5d` lặp lại trong header từng bị nghi là timestamp. Giá trị này không đổi suốt 23 phút,
  nên không phải timestamp; ý nghĩa vẫn chưa rõ.

---

## 5. Hạn chế

- Mới chỉ quan sát lúc drone **đứng yên hoặc lơ lửng, chưa có thao tác điều khiển bay**, nên chưa
  thấy các lệnh điều khiển.
- Các module `0x92`, `0x28` và phần lớn lệnh telemetry chưa được gán ý nghĩa.
- Một số byte trong header (byte 16–31 của kênh điều khiển, byte 16–19 của kênh video) chưa giải
  được.
- Tất cả kết quả đều từ **một drone, một điện thoại và một phiên bản app**. Chưa kiểm tra khi firmware
  hoặc app cập nhật.
- Luồng video có khoảng 40 điểm bất thường nhỏ, nghi do mất gói quanh lúc kết nối lại, chưa kiểm
  chứng.

---

## 6. Hướng tiếp theo

1. **Tìm lệnh yêu cầu keyframe** (quan trọng cho phần video của SDK): xem các lệnh app gửi lúc kết
   nối lại, kết hợp dịch ngược APK.
2. **Gán tên cho các lệnh telemetry**: đối chiếu với định nghĩa trong các dissector cộng đồng, và
   dùng cùng phương pháp "thay đổi có kiểm soát" như với pin, ví dụ xoay gimbal để tìm trường góc
   gimbal, hoặc di chuyển drone để tìm trường độ cao.
3. **Bắt gói khi điều khiển bay** (cất cánh, di chuyển, hạ cánh) để tìm lệnh điều khiển từ app.
4. Viết dissector Wireshark cho header bao ngoài và lớp tunnel, để các thành viên khác xem trực tiếp
   trên Wireshark.
5. Bắt đầu một PoC nhỏ: tự mở kết nối UDP tới drone, đọc telemetry pin và nhận video mà không cần
   DJI Fly.

---

## Phụ lục: Công cụ và cách tái lập

Các script nằm trong thư mục `poc/` của repo, chỉ dùng thư viện chuẩn của Python:

| Script | Chức năng |
|---|---|
| `poc/duml_survey.py` | Thống kê cấu trúc gói: header, loại kênh, danh sách lệnh DUML, các khoảng gián đoạn |
| `poc/find_battery_field.py` | Dò byte telemetry khớp với các mốc pin đã ghi |
| `poc/extract_video.py` | Ghép luồng video từ pcap thành file `.h265` (có thể mượn bộ tham số từ file khác) |

Ví dụ giải mã video từ một bản ghi giữa phiên:

```
python poc/extract_video.py captures/cap_01_connect.pcap captures/cap_01.h265
python poc/extract_video.py captures/cap_04_battery_drain.pcap captures/cap_04.h265 --params captures/cap_01.h265
ffmpeg -flags2 +showall -err_detect ignore_err -i captures/cap_04.h265 cap_04.mp4
```

Nhật ký chi tiết từng bước (kể cả các mốc thời gian gốc và những lần thử sai) nằm trong
`notes/capture-log.md`. File pcap và ảnh trích từ video không đưa lên repo vì dung lượng lớn và có
hình người trong khung hình.
