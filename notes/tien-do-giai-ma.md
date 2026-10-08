# Tiến độ giải mã giao thức DJI Neo 2 — Sơ đồ cấu trúc gói tin

**Cập nhật:** 07/10/2026 · **Giai đoạn:** Phase 1 – PoC (sau Ngày 6)
**Mục đích:** nhìn một chỗ thấy ngay **đã giải mã được gì / chưa giải mã gì** trong từng lớp gói tin.

## Chú thích ký hiệu

| Ký hiệu | Ý nghĩa |
|:---:|---|
| ✅ | Đã giải mã **và kiểm chứng** bằng thực nghiệm (thay đổi có kiểm soát) |
| 🟡 | Suy theo chuẩn DJI / mới một phần — **chưa kiểm chứng** trên Neo 2 |
| ❓ | **Chưa giải mã** — chưa rõ ý nghĩa |

Tiến độ tổng thể: **khung giao thức và các trường telemetry cốt lõi đã xong**; còn lại là các trường
phụ (cần bay để kiểm chứng) và một luồng cảm biến nhị phân tốc độ cao.

---

## 1. Bức tranh tổng thể: một luồng UDP, bốn loại kênh

```
   Điện thoại (DJI Fly)  ⇄  UDP cổng 9003  ⇄  Neo 2 (192.168.2.1)
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
   │  Kênh 0x02   │     │ Kênh 0x01/04 │     │  Kênh 0x00   │
   │   VIDEO      │     │   ĐIỀU KHIỂN │     │  Bắt tay     │
   │  H.265 ✅    │     │  (DUML) ✅   │     │ (reconnect)🟡│
   └──────────────┘     └──────┬───────┘     └──────────────┘
                               │ chứa
                               ▼
                        ┌──────────────┐
                        │ Frame DUML   │  ← nhiều frame, phần lớn
                        │  (tunnel) ✅ │     bọc trong tunnel 0x51/01
                        └──────┬───────┘
                               │ lồng bên trong
                               ▼
                   Telemetry: pin ✅ · gimbal ✅ · hướng drone ✅
                   camera 🟡 · cảm biến tốc độ cao ❓
```

Mọi gói đều mở đầu bằng **header chung 16 byte**. Tùy loại kênh (byte 6) mà phần sau khác nhau.

### 1.1. Gói tin có bị mã hóa không? — KHÔNG (và vì sao vẫn khó đọc)

Câu hỏi đầu tiên: thứ làm ta khó đọc gói có phải là **mã hóa (mật mã)** không? **Không.** Dữ liệu
**không hề bị mã hóa**. Chính giao thức DUML có sẵn một trường **"Encrypt"** trong header, và trên
**26.048 frame** kiểm tra, giá trị đều là **None (0)** — DJI **chủ động chọn không mã hóa**. Không có
AES, không TLS, không XOR.

Từ "mã hóa" tiếng Việt gộp 3 nghĩa rất khác nhau — cần tách ra:

| Nghĩa của "mã hóa" | Có trong gói Neo 2? | Vai trò |
|---|:---:|---|
| **Encryption (mật mã)** — giấu nội dung bằng khóa | ❌ KHÔNG | nếu có thì không khóa = chịu, không đọc nổi |
| **Encoding (biểu diễn nhị phân)** — đóng gói dữ liệu thành byte theo định dạng riêng | ✅ CÓ | làm khó đọc nhưng **giải được** nếu hiểu định dạng |
| **Compression (nén)** cho video | ✅ CÓ (H.265) | làm dữ liệu trông ngẫu nhiên dù không mã hóa |

**Vậy cái gì làm khó đọc? (các lớp "encoding", không phải mật mã):**
1. **Định dạng đóng gói riêng của DJI** — header ngoài không theo chuẩn công khai nào → phải tự dò
   nghĩa từng byte. Khó vì **không có tài liệu**, không phải vì bị khóa.
2. **Giao thức DUML dạng nhị phân** — byte thô (nguồn/đích/lệnh/payload) + CRC, không phải văn bản.
3. **Lớp tunnel (frame lồng frame)** — frame thật bị bọc trong `0x51/0x01` → đây là lý do dissector
   chuẩn của Wireshark không nhận ra gì, chứ không phải vì mã hóa.
4. **Trường nhị phân đóng gói chặt** — int16/int32/float/quaternion, little-endian, dấu phẩy tĩnh
   (vd 0.1°), **không có tên trường** → phải dùng "thay đổi có kiểm soát" để đoán nghĩa.
5. **Video nén H.265 (entropy cao)** — trông y như ngẫu nhiên → dễ tưởng bị mã hóa. Nhưng **nén ≠ mã
   hóa**: giải nén bằng ffmpeg là ra hình (điểm gây nhầm lẫn kinh điển).

**Điểm đáng chú ý về an ninh:** DUML **có hỗ trợ mã hóa** (trường Encrypt liệt kê AES128/192/256,
DES, XOR…), nhưng Neo 2 **để None** ở kết nối Wi-Fi trực tiếp này. Hệ quả: (a) *thuận lợi cho dự án* —
revert được giao thức mà không phải phá mật mã, nên hướng tự xây SDK khả thi; (b) *về bảo mật* — ai
trong tầm Wi-Fi và vào được mạng drone đều có thể đọc telemetry/video, và về lý thuyết chèn lệnh, vì
tầng này **không mã hóa cũng không xác thực gói**.

> **Tóm lại:** gói khó đọc vì **đóng gói nhị phân nhiều lớp theo định dạng riêng + video nén H.265**,
> chứ **không phải vì mã hóa**. Rào cản là *"không có tài liệu"*, không phải *"không có khóa"*.

---

## 2. Phương pháp: làm sao xác định được từng phần của gói

Nguyên tắc chung: **không có tài liệu chính thức của DJI cho Neo 2**, nên mọi ý nghĩa đều suy ra từ
**dữ liệu thật** bằng quan sát + thí nghiệm, rồi kiểm chứng chéo. Các kỹ thuật đã dùng:

**2.1. Bắt gói theo nhiều kịch bản.** tcpdump chạy trên điện thoại (quyền root) ghi lại toàn bộ
traffic. Mỗi kịch bản nhắm một mục tiêu: nhàn rỗi (xem cấu trúc nền), tắt/bật Wi-Fi (bắt tay +
keyframe), pin tụt 23 phút, nghiêng gimbal, xoay drone từng trục…

**2.2. So sánh nhiều gói → tách trường cố định / thay đổi.** Đặt cạnh nhau hàng nghìn gói, xem byte
nào **không đổi** (hằng số / ID), byte nào **tăng đều** (số thứ tự), byte nào **đổi ngẫu nhiên** (dữ
liệu / checksum). Ví dụ: byte 0–1 luôn = độ dài | 0x8000; byte 4–5 tăng 8 mỗi gói → seq video; byte 7
= XOR của 7 byte đầu → checksum.

**2.3. Kiểm CRC để tìm ranh giới khung.** DUML có CRC8 cho header và CRC16 cho cả khung. Quét mọi
byte `0x55`, chỉ nhận là khung thật khi **qua cả hai CRC**. Nhờ đó tách đúng các khung lồng trong
tunnel (trên 30k gói: 76 245 khung qua cả hai CRC, chỉ 107 khung lọt CRC8 nhưng trượt CRC16 → tiêu
chí rất sạch).

**2.4. "Thay đổi có kiểm soát" — chìa khóa để gắn tên trường.** Tạo một thay đổi vật lý **đã biết
trước**, ghi lại **mốc thời gian**, rồi dò byte nào biến đổi khớp đúng:
- *Pin:* theo dõi % trên app tụt 78→62 suốt 23 phút → tìm byte giảm đúng từng mốc thời gian.
- *Gimbal:* nghiêng camera ngang → xuống → lên → ngang, giữ mỗi vị trí ~10s → tìm trường đổi dấu
  đúng chiều, bằng 0 khi để ngang.
- *Hướng drone:* xoay / nghiêng **từng trục một** → mỗi trục chỉ làm một trường đổi → tách được
  yaw / pitch / roll riêng biệt.
- *Lệnh keyframe:* đưa app ra nền rồi mở lại (buộc phải xin khung mới) → tìm lệnh **chỉ xuất hiện**
  đúng những lúc đó, không có trong lúc xem bình thường.

**2.5. Đối chiếu chuẩn cộng đồng.** So khớp với bộ dissector DUML công khai và layout "OSD General"
của các dòng DJI cũ. Ví dụ: hướng drone nằm đúng offset 24/26/28 của OSD chuẩn → Neo 2 dùng lại
layout này; dữ liệu pin khớp struct "Battery Dynamic Data".

**2.6. Đối chiếu mã nguồn app (phân tích tĩnh).** Giải nén APK, đọc chuỗi ký tự và dịch ngược thư
viện. Ví dụ: tìm thấy hành động `AppRequestIFrame` xác nhận cặp lệnh xin keyframe; danh mục hơn 6000
"key" của SDK (`GimbalAttitudeQuaternion`, `AttitudeQuaternion`, `BatteryVoltage`…) khớp đúng các
trường đã giải mã.

**2.7. Giải mã & kiểm chứng chéo.** Ghép payload các gói video thành luồng H.265 rồi giải mã bằng
ffmpeg ra hình → chứng minh video không mã hóa. Mỗi kết luận được kiểm chứng bằng **≥2 nguồn độc
lập**: gimbal có cả trường góc (i16) lẫn quaternion khớp nhau; thí nghiệm gimbal lặp lại 2 lần;
mốc người dùng báo khớp thời điểm trong pcap với độ trễ ổn định ~4–5s.

### Tóm tắt: mỗi nội dung được xác định bằng cách nào
| Nội dung gói | Kỹ thuật chính |
|---|---|
| Độ dài, seq, checksum, loại kênh, ID phiên | So sánh nhiều gói (2.2) |
| Ranh giới khung DUML, lớp tunnel | Kiểm CRC (2.3) |
| % pin, điện áp, dòng, dung lượng | Thay đổi có kiểm soát (pin tụt) + chuẩn DJI (2.4, 2.5) |
| Góc gimbal | Thay đổi có kiểm soát (nghiêng camera), 2 trường khớp nhau (2.4) |
| Hướng drone (yaw/pitch/roll) | Thay đổi có kiểm soát (xoay từng trục) + OSD chuẩn (2.4, 2.5) |
| Lệnh xin keyframe | Thay đổi có kiểm soát (ra/vào app) + mã nguồn APK (2.4, 2.6) |
| Video H.265 không mã hóa | Ghép payload + giải mã ffmpeg ra hình (2.7) |

---

## 3. Header chung 16 byte (mọi gói, cả hai chiều) — ✅ gần như trọn vẹn

```
 byte:  0    1      2    3      4    5      6     7      8   9  10 11     12 13 14 15
       ┌──────────┬──────────┬──────────┬─────┬─────┬──────────────┬──────────────┐
       │ Độ dài   │ ID phiên │ Seq video│ Loại│ XOR │ ACK seq video│   (thường 0) │
       │ |0x8000  │          │  (+8/gói)│ kênh│ chk │ (app→drone)  │              │
       ├──────────┼──────────┼──────────┼─────┼─────┼──────────────┼──────────────┤
       │    ✅    │    ✅    │    ✅    │ ✅  │ ✅  │     🟡       │     ❓       │
       └──────────┴──────────┴──────────┴─────┴─────┴──────────────┴──────────────┘
```

| Byte | Trường | TT | Ghi chú |
|:---:|---|:---:|---|
| 0–1 | Độ dài gói `| 0x8000` | ✅ | bit 15 luôn bật |
| 2–3 | ID phiên | ✅ | +1 mỗi lần kết nối lại |
| 4–5 | Seq gói video | ✅ | tăng 8 mỗi gói video; 0 ở kênh khác |
| 6 | Loại kênh | ✅ | 01=DUML drone→app · 02=video · 04=DUML app→drone · 00=bắt tay |
| 7 | Checksum | ✅ | = XOR của byte 0..6 |
| 8–11 | ACK seq video | 🟡 | chiều app→drone = seq video đã nhận; chiều drone→app chưa rõ hết |
| 12–15 | (0) | ❓ | hầu như luôn 0, chưa rõ dùng khi nào |

---

## 4. Kênh ĐIỀU KHIỂN (byte 6 = 0x01 / 0x04): header 34 byte + frame DUML

```
 ┌─ 16 byte header chung (mục 3) ─┬────── 18 byte phần riêng kênh DUML ──────┐
 │  [0 .............. 15]         │ [16 ................ 31]   [32 ... 33]   │
 │            ✅                  │   78 5d 78 5d 00..  ❓      Độ dài sau ✅ │
 └────────────────────────────────┴──────────────────────────────────────────┘
                                                                   │
                        [34 ..................................... hết gói]
                        │  Các frame DUML nối tiếp / lồng nhau          │
                        ▼
    ┌───────────────────── FRAME DUML v1 ─────────────────────┐
    │ 55 │ len+ver │ crc8 │ src │ dst │ seq │ cfg │ set │ id │ … payload … │ crc16 │
    │[0] │ [1..2]  │ [3]  │ [4] │ [5] │[6-7]│ [8] │ [9] │[10]│  [11..n-3]  │[n-2..]│
    │ ✅ │   ✅    │  ✅  │ ✅  │ ✅  │ ✅  │ ✅  │ ✅  │ ✅ │  tùy lệnh   │  ✅   │
    └─────────────────────────────────────────────────────────────────────────────┘
```

- Byte 16–31 (`78 5d 78 5d 00 00 00 00 78 5d 78 5d 00 00 00 00`): **❓ cố định, chưa rõ nghĩa**
  (không đổi suốt 23 phút → không phải timestamp).
- Byte 32–33: **✅** độ dài phần dữ liệu sau header 34 byte.
- **Tunnel ✅:** frame `set=0x51 id=0x01` là "phong bì" — payload của nó chứa các frame DUML thật
  bên trong (lồng nhau). Đây là chỗ chứa phần lớn telemetry.

---

## 5. Các frame telemetry đã giải mã

### 5.1. Pin — `0x0b→0x02  set 0x0d / id 0x02` (payload 44 byte) — ✅ gần trọn vẹn

```
 payload: 0   1 ───── 4   5 ───── 8   9 ──── 12  13 ─── 16  17 18  19   20   21 ──── 28  29   30 ─── 43
         ┌──┬──────────┬──────────┬──────────┬──────────┬──────┬───┬────┬──────────┬────┬────────┐
         │? │ Điện áp  │ Dòng (I) │ DL đầy   │ DL còn   │Nhiệt │Cel│SOC │ Status   │Ver │  ❓    │
         │  │ u32 mV   │ i32 mA   │ u32 mAh  │ u32 mAh  │ độ   │ l │ %  │ u64      │    │        │
         ├──┼──────────┼──────────┼──────────┼──────────┼──────┼───┼────┼──────────┼────┼────────┤
         │❓│   ✅     │   ✅     │   ✅     │   ✅     │ 🟡   │✅ │ ✅ │   ❓     │ ✅ │  ❓    │
         └──┴──────────┴──────────┴──────────┴──────────┴──────┴───┴────┴──────────┴────┴────────┘
```
Kiểm chứng trên 23 phút xả: điện áp 8099→7751 mV, DL còn 1289→1032 mAh, SOC 78→63%, cell=2 (pin 2S).
Nhiệt độ 🟡 (đơn vị ước lượng 0,1°C). Status (8 byte cờ) và đuôi: ❓.

### 5.2. Gimbal — `0x04→0x02  set 0x04 / id 0x05` (payload 50 byte) — ✅ phần góc

```
 payload: 0 ── 1   2 ─────────────────── 23   24 ───────────── 39   40 ─────── 49
         ┌───────┬───────────────────────────┬────────────────────┬──────────────┐
         │ Pitch │          ❓                │ Quaternion hướng   │     ❓       │
         │ i16   │   (các trường khác)        │ camera (w,x,y,z)   │              │
         │ 0.1°  │                            │ 4 × float32        │              │
         ├───────┼────────────────────────────┼────────────────────┼──────────────┤
         │  ✅   │           ❓               │        ✅          │     ❓       │
         └───────┴────────────────────────────┴────────────────────┴──────────────┘
```
Hai trường độc lập (pitch i16 và quaternion) khớp nhau tuyệt đối trên 2 lần ghi. Tầm: -90°…+100°.

### 5.3. Hướng thân drone — `0x03  set 0x03 / id 0x43` (OSD General, payload 85 byte)

```
 payload: 0 ──────── 15  16 17  18 ─── 23   24 25  26 27  28 29   30 ─────────────── 84
         ┌──────────────┬──────┬──────────┬──────┬──────┬──────┬──────────────────────┐
         │ Kinh/Vĩ độ   │ Độ   │ Vận tốc  │Pitch │ Roll │ Yaw  │ Trạng thái bay, GPS, │
         │ 2×double     │ cao  │ x/y/z    │ i16  │ i16  │ i16  │ … (theo OSD chuẩn)   │
         │              │ i16  │ 3×i16    │ 0.1° │ 0.1° │ 0.1° │                      │
         ├──────────────┼──────┼──────────┼──────┼──────┼──────┼──────────────────────┤
         │     🟡       │  🟡  │   🟡     │  ✅  │  ✅  │  ✅  │        🟡/❓          │
         └──────────────┴──────┴──────────┴──────┴──────┴──────┴──────────────────────┘
```
Pitch/Roll/Yaw ✅ (kiểm chứng cap_08, đổi từng trục). Vì Neo 2 dùng **layout OSD chuẩn DJI**, các
trường GPS/độ cao/vận tốc 🟡 (suy theo chuẩn, dưới đất đều ~0 — cần bay để xác nhận).

### 5.4. Lệnh app xin keyframe — `0x02→0x09  set 0x01 / id 0x01` — ✅

```
 payload: 0  1  2  3  4   5    6 ...
         ┌──────────────┬─────┬──────┐
         │     ❓       │ Cờ  │  ❓  │   bit 0x20 của byte 5 = "xin I-frame ngay"
         ├──────────────┼─────┼──────┤
         │     ❓       │ ✅  │  ❓  │
         └──────────────┴─────┴──────┘
```
5/5 lần khớp + đối chiếu mã app (`AppRequestIFrame`). Chưa gửi thử chủ động để chốt 100%.

---

## 6. Kênh VIDEO (byte 6 = 0x02): header 20 byte + H.265

```
 ┌─ 16 byte header chung ─┬─ 4 byte ─┬──────── phần còn lại ────────┐
 │   [0 ........ 15] ✅   │ [16..19] │ [20 ....................... ] │
 │                        │   ❓     │   Luồng H.265 (Annex-B) ✅    │
 └────────────────────────┴──────────┴───────────────────────────────┘
```
- Byte 16–19 (`f8 13 60 6d`…): ❓ trường riêng của video.
- Byte 20+: ✅ **H.265 thô, 960×720, 30 fps, KHÔNG mã hóa** — đã ghép và giải mã ra hình bằng ffmpeg.
- Lưu ý: drone chỉ gửi keyframe lúc mở phiên / kết nối lại (không định kỳ).

### 6.1. Vì sao video giải mã bị mờ đục, rõ dần (không nét ngay)

Khi giải mã các bản ghi (vd. `demo_cap02.mp4`, lưới khung của cap_04), ảnh **bắt đầu mờ đục như sương
rồi rõ dần sau ~20 giây**, chỗ có người thì nhận ra được còn nền thì phẳng lì. Nguyên nhân:

#### Bản chất: video nén đánh đổi "dung lượng" lấy "sự phụ thuộc"

Một video 960×720 @30fps nếu lưu **đầy đủ từng khung** tốn ~40 MB/giây — không truyền nổi qua Wi-Fi.
Mẹo nén: hai khung liên tiếp gần như giống hệt nhau, nên **hầu hết các khung chỉ lưu PHẦN THAY ĐỔI**
so với khung trước (gọi là P-frame). Cái giá: mỗi khung **phụ thuộc** khung trước → video là một
**chuỗi mắt xích**, không phải tập ảnh rời.

- **P-frame không phải ảnh** — nó là một *"công thức sửa"*: "lấy khung trước, dời khối này sang phải
  3 pixel, cộng thêm sai lệch kia". Nó **vô nghĩa nếu không có khung trước để sửa lên** (như công thức
  "thêm 2 thìa đường" — vô dụng nếu chưa có ly nước).
- **Keyframe (I-frame)** là **ảnh đầy đủ, tự vẽ được**, không cần gì trước nó. Nhiệm vụ: làm **điểm gốc**
  để chuỗi P-frame bám vào — chỗ duy nhất "cắt đứt phụ thuộc, làm lại từ số 0".

Khi bắt **vào giữa phiên**, cái đầu tiên nhận được là một P-frame (công thức sửa) nhưng **không biết
sửa lên cái gì** → bộ giải mã phải bịa một nền xám rồi sửa lên đó → sai hệ thống → mờ đục. (Ví von:
mở truyện ở giữa, đọc được câu "anh ta đáp: đồng ý" mà không biết câu hỏi — chữ đọc được nhưng nghĩa sai.)

**Hai thứ khác nhau cùng thiếu khi bắt giữa phiên** (đừng nhầm):

| Thứ thiếu | Nhiệm vụ | Thiếu thì sao |
|---|---|---|
| **VPS/SPS/PPS** (bộ tham số) | Dạy decoder *cách đọc* luồng: ảnh rộng bao nhiêu, màu tổ chức ra sao | **Đen màn hình** — không giải mã nổi 1 pixel |
| **Keyframe** (I-frame) | Cho chuỗi một *ảnh gốc* để bám vào | Giải mã được nhưng **sai/mờ** |

Ta **mượn được** VPS/SPS/PPS từ phiên khác (camera cùng cấu hình) nên vượt qua cái thiếu thứ nhất →
ra được hình. Nhưng **không thể mượn keyframe** (nó là ảnh của đúng cảnh ngay lúc đó) → nên vẫn mờ.

**Mất gói = đứt mắt xích giữa chuỗi:** vì mỗi khung sửa lên khung trước, một khối bị mất sẽ khiến **mọi
khung sau "sửa lên cái sai" → lỗi lan truyền** (error propagation), kéo dài tới khi được vá lại. Đây là
bản chất của "khối vỡ không tự hết": cái hỏng được **thừa kế** sang các khung kế tiếp.

> **Một câu:** cơ chế giúp video nhỏ gọn (bỏ ảnh đầy đủ, chỉ lưu thay đổi) cũng chính là cơ chế khiến
> nó dễ vỡ khi **thiếu điểm gốc** (keyframe) hoặc **đứt chuỗi** (mất gói).

Dưới đây là các biểu hiện cụ thể của bản chất trên:

**Trực tiếp (cơ chế ngay tại chỗ):**
1. **Thiếu keyframe (I-frame).** Video nén gồm *keyframe* (ảnh đầy đủ, tự giải mã được) và *P-frame*
   (chỉ lưu phần thay đổi so với khung trước). Các bản ghi này bắt **vào giữa phiên**, không có
   keyframe nào → bộ giải mã phải khởi đầu từ **nền xám sai** rồi cộng dồn P-frame lên → lớp mờ đục.
2. **Làm mới dần (intra-refresh).** Thay vì gửi keyframe, drone rải các *khối intra* (vùng nhỏ vẽ
   đầy đủ) qua nhiều khung; phải **hết một chu kỳ ~20 giây** toàn ảnh mới đúng. Ảnh đang ở giữa chu kỳ.
3. **Vùng động hiện rõ, vùng tĩnh "kẹt".** P-frame mang chuyển động + sai lệch, nên chỗ **có cử động**
   (người) được vẽ bằng dữ liệu thật → rõ; chỗ **đứng yên** (tường, trần) kế thừa nền xám sai → mờ.
4. **Mất gói (packet loss).** Rớt gói UDP → mất vài khối mã hóa → các ô vuông "mosaic" bị vỡ.
5. **Bộ tham số đi mượn.** VPS/SPS/PPS mượn từ phiên khác (vì bản ghi không có) → thêm chút sai lệch.

**Gián tiếp (vì sao rơi vào tình huống đó):**
- Drone **không gửi keyframe định kỳ** (thiết kế của DJI) → không có điểm khởi lại sạch khi bắt giữa phiên.
- Các bản ghi bắt **vào giữa luồng** cho mục đích khác (đo pin, nghiêng gimbal), bỏ lỡ keyframe đầu phiên.
- tcpdump chạy trên **điện thoại đang bận** → rớt một phần gói UDP video.

**So sánh các bản ghi:** `cap_02` (nhàn rỗi, chỉ 2 chỗ mất gói) đoạn cuối sạch gần hoàn toàn nhưng clip
30s nên ~2/3 đầu vẫn đang hội tụ; `cap_04` (người cử động, 55 chỗ mất gói) nhiều khối vỡ hơn; `cap_07`
(nghiêng gimbal, mất gói + chuyển động nhiều) nhiễu nặng nhất.

**Hệ quả:** đây chính là lý do **lệnh xin keyframe** (mục 5.4) quan trọng — gửi được nó là có ngay
một khung đầy đủ, ảnh **nét tức thì** thay vì chờ ~20 giây hội tụ. Muốn đẹp hẳn còn cần **giảm mất gói**.

---

## 7. Các module telemetry — mức định danh

| Module (nguồn) | Là gì | TT | Ghi chú |
|:---:|---|:---:|---|
| `0x0b` Pin | Dữ liệu pin | ✅ | giải mã đầy đủ (mục 5.1) |
| `0x04` Gimbal | Góc camera | ✅ | pitch + quaternion (mục 5.2) |
| `0x03` Flight Controller | Hướng drone, OSD | ✅/🟡 | pitch/roll/yaw ✅; GPS/độ cao/vận tốc 🟡 |
| `0x28` Camera | Tham số camera, baro/nhiệt độ | 🟡 | tự mô tả bằng text (`cam_*`, `baro`…); chưa map từng trường |
| `0x92` Cảm biến tốc độ cao | Nhị phân ~50 Hz | ❓ | nghi IMU thô / thị giác; cần thí nghiệm có kiểm soát |

---

## 8. Bảng tổng kết: đã giải mã / chưa giải mã

| Hạng mục | Trạng thái |
|---|:---:|
| Khung giao thức (header ngoài, loại kênh, checksum, tunnel) | ✅ |
| Phân khung DUML (src/dst/cmd_set/cmd_id/CRC) | ✅ |
| Video: định dạng, độ phân giải, mã hóa hay không | ✅ |
| Lệnh xin keyframe | ✅ (chưa gửi thử) |
| Pin: điện áp, dòng, dung lượng, cell, % | ✅ |
| Gimbal: góc pitch + quaternion | ✅ |
| Hướng drone: pitch/roll/yaw | ✅ |
| Drone: GPS / độ cao / vận tốc (OSD chuẩn) | 🟡 cần bay |
| Nhiệt độ pin (đơn vị) | 🟡 |
| ACK/seq chiều drone→app, byte 12–15 header | ❓ |
| Byte 16–31 header DUML (`78 5d…`) | ❓ |
| Byte 16–19 header video | ❓ |
| Module camera `0x28`: từng trường | 🟡 |
| Module cảm biến `0x92`: nội dung | ❓ |
| Lệnh điều khiển bay (app → drone) | ❓ cần bay |

Chi tiết từng phần: `notes/capture-log.md`. Báo cáo đầy đủ: `notes/bao-cao-ngay-3-6.md`.
Danh mục khả năng SDK: `notes/apk-key-catalog.md`.

---

## 9. Ví dụ: mổ xẻ một gói tin thật

Một gói **drone→app, 520 byte**, lấy từ `captures/cap_04_battery_drain.pcap`. Đây là ví dụ thật minh
họa toàn bộ cấu trúc đã giải mã: header ngoài → lớp tunnel → các frame telemetry → pin ra số thật.

**Hex payload UDP (48 byte đầu, đủ thấy header + frame pin):**
```
 [  0] 08 82 b1 ab 00 00 01 91 60 23 f8 23 00 00 00 00   ← header chung 16B
 [ 16] 78 5d 78 5d 00 00 00 00 78 5d 78 5d 00 00 00 00   ← hằng số ❓
 [ 32] e6 01 55 5c 04 80 27 ee 10 97 00 51 01 55 39 04   ← [32:34] độ dài; từ [34] frame
 [ 48] 25 0b 02 01 08 00 0d 02 00 a0 1f 00 00 7b fd ff   ← bên trong: frame PIN
 ...
```

**Bóc lớp 1 — header chung 16 byte** (mục 3):
| Byte | Giá trị | Giải mã |
|---|---|---|
| [0:2] | `08 82` | 0x8208 → cờ 0x8000 bật, **độ dài = 520** (khớp kích thước gói) |
| [2:4] | `b1 ab` | **ID phiên = 0xabb1** |
| [4:6] | `00 00` | seq video = 0 (gói điều khiển, không phải video) |
| [6] | `01` | **loại kênh = DUML drone→app** |
| [7] | `91` | **checksum XOR** → tính lại = 0x91 → **KHỚP** |
| [8:12] | `60 23 f8 23` | ACK/seq |
| [12:16] | `00 00 00 00` | (thường 0) ❓ |

**Bóc lớp 2 — header kênh DUML** (mục 4): byte [16:32] = `78 5d 78 5d …` (hằng số ❓);
byte [32:34] = `e6 01` → **độ dài phần dữ liệu sau = 486 byte**.

**Bóc lớp 3 — các frame DUML** (từ byte 34). Gói này chứa **4 frame tunnel**, mỗi cái bọc một frame
thật bên trong:
```
55 | len=92  | tunnel 0x51/01  →  chứa:  55 | Pin→App   | set 0x0d id 0x02 | 44B
                                           >>> PIN: 78%  8.096V  -645mA  1283/1639mAh  2S  46.4°C   ✅
55 | len=60  | tunnel 0x51/01  →  chứa:  55 | Sensor→App| set 0x0a id 0xbc | 12B   ❓ (module 0x92)
55 | len=152 | tunnel 0x51/01  →  chứa:  55 | Camera→App| set 0x00 id 0x99 | 104B  🟡 (cam_lens_state)
55 | len=91  | tunnel 0x51/01  →  chứa:  55 | Sensor→App| set 0x23 id 0xb2 | 43B   ❓ (luồng 50Hz)
```

**Đọc ví dụ này:** một gói UDP duy nhất gói nhiều loại dữ liệu — pin (giải mã đầy đủ ✅), tham số
camera (định danh 🟡), và hai luồng cảm biến chưa giải mã (❓) — tất cả đều bọc trong lớp tunnel và
nằm sau đúng cái header 16 byte mà ta đã dựng lại. Mỗi frame đều qua kiểm CRC8 + CRC16 nên chắc chắn
tách đúng ranh giới.

(Tái tạo: dùng `poc/neo2_telemetry.py` để đọc telemetry, hoặc mở gói trong Wireshark với dissector
`tools/dji-dissectors/dji-neo2-udp.lua`.)
