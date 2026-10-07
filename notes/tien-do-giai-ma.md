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

---

## 2. Header chung 16 byte (mọi gói, cả hai chiều) — ✅ gần như trọn vẹn

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

## 3. Kênh ĐIỀU KHIỂN (byte 6 = 0x01 / 0x04): header 34 byte + frame DUML

```
 ┌─ 16 byte header chung (mục 2) ─┬────── 18 byte phần riêng kênh DUML ──────┐
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

## 4. Các frame telemetry đã giải mã

### 4.1. Pin — `0x0b→0x02  set 0x0d / id 0x02` (payload 44 byte) — ✅ gần trọn vẹn

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

### 4.2. Gimbal — `0x04→0x02  set 0x04 / id 0x05` (payload 50 byte) — ✅ phần góc

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

### 4.3. Hướng thân drone — `0x03  set 0x03 / id 0x43` (OSD General, payload 85 byte)

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

### 4.4. Lệnh app xin keyframe — `0x02→0x09  set 0x01 / id 0x01` — ✅

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

## 5. Kênh VIDEO (byte 6 = 0x02): header 20 byte + H.265

```
 ┌─ 16 byte header chung ─┬─ 4 byte ─┬──────── phần còn lại ────────┐
 │   [0 ........ 15] ✅   │ [16..19] │ [20 ....................... ] │
 │                        │   ❓     │   Luồng H.265 (Annex-B) ✅    │
 └────────────────────────┴──────────┴───────────────────────────────┘
```
- Byte 16–19 (`f8 13 60 6d`…): ❓ trường riêng của video.
- Byte 20+: ✅ **H.265 thô, 960×720, 30 fps, KHÔNG mã hóa** — đã ghép và giải mã ra hình bằng ffmpeg.
- Lưu ý: drone chỉ gửi keyframe lúc mở phiên / kết nối lại (không định kỳ).

---

## 6. Các module telemetry — mức định danh

| Module (nguồn) | Là gì | TT | Ghi chú |
|:---:|---|:---:|---|
| `0x0b` Pin | Dữ liệu pin | ✅ | giải mã đầy đủ (mục 4.1) |
| `0x04` Gimbal | Góc camera | ✅ | pitch + quaternion (mục 4.2) |
| `0x03` Flight Controller | Hướng drone, OSD | ✅/🟡 | pitch/roll/yaw ✅; GPS/độ cao/vận tốc 🟡 |
| `0x28` Camera | Tham số camera, baro/nhiệt độ | 🟡 | tự mô tả bằng text (`cam_*`, `baro`…); chưa map từng trường |
| `0x92` Cảm biến tốc độ cao | Nhị phân ~50 Hz | ❓ | nghi IMU thô / thị giác; cần thí nghiệm có kiểm soát |

---

## 7. Bảng tổng kết: đã giải mã / chưa giải mã

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
