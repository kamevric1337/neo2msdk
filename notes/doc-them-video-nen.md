# Đọc thêm: nén video liên khung & lỗi do mất keyframe

Tài liệu tham khảo cho vấn đề đã gặp ở `tien-do-giai-ma.md` (mục 6.1): vì sao video nén dựa trên
"thay đổi", và vì sao **mất keyframe / mất gói** làm hỏng hình (mờ, khối vỡ, "mờ rồi rõ dần").

Từ khóa chủ yếu bằng **tiếng Anh** vì tài liệu đầy đủ và chuẩn hơn. Cụm tiếng Việt để ở cuối.

## 1. Nền tảng: nén video dựa trên "thay đổi" (inter-frame)
- `inter-frame compression` / `interframe coding`
- `temporal redundancy video compression` — dư thừa theo thời gian, lý do nén được
- `motion compensation` + `motion estimation` — bù/ước lượng chuyển động, cốt lõi của P-frame
- `motion vector` + `residual (prediction error)` — chính là "công thức sửa" của P-frame
- `block-based video coding` · `macroblock` (H.264) · `CTU coding tree unit` (H.265)

## 2. Các loại khung & nhóm khung
- `I-frame P-frame B-frame explained`
- `IDR frame` — Instantaneous Decoder Refresh, keyframe "sạch" trong H.264/H.265
- `keyframe (intra frame) vs interframe`
- `GOP group of pictures` + `GOP structure` — giải thích chu kỳ keyframe (rất nên đọc)
- `closed GOP vs open GOP`

## 3. Keyframe / làm mới dần (đúng hiện tượng "mờ rồi rõ dần")
- `intra refresh` / `gradual decoder refresh (GDR)` — **từ khóa chính** cho hiện tượng này
- `periodic intra refresh`
- `keyframe interval` / `I-frame interval`

## 4. Mất keyframe / mất gói gây lỗi (đúng "khối vỡ lan truyền")
- `error propagation video decoding` — **từ khóa chính**
- `error resilience video coding`
- `packet loss video artifacts` / `video corruption packet loss`
- `decoding without keyframe` / `missing I-frame green screen`
- `error concealment video` — cách decoder cố "vá" lỗi
- `reference frame missing "could not find ref"` — đúng lỗi ffmpeg đã thấy

## 5. H.265/HEVC & bộ tham số (phân biệt VPS/SPS/PPS vs keyframe)
- `HEVC NAL unit types`
- `VPS SPS PPS explained` — tại sao thiếu nó thì **đen màn hình**
- `H.265 parameter sets vs IDR`
- `Annex B byte stream H.265` — định dạng đã dùng để ghép luồng
- `emulation prevention byte 0x03` — chi tiết đã dùng để chứng minh video không mã hóa

## 6. Cơ chế "xin keyframe" trong streaming (liên quan mục 5.4 của ta)
- `FIR Full Intra Request` / `PLI Picture Loss Indication` — chuẩn RTCP, cách client xin keyframe
- `request keyframe low latency streaming`
- `force IDR / force keyframe`
- `WebRTC keyframe request` — ví dụ thực tế phổ biến

## 7. Công cụ để tự thử nghiệm
- `ffmpeg -flags2 +showall` — ép hiện cả khung lỗi (như đã dùng)
- `ffprobe -show_frames ... pict_type` — xem từng khung là I/P/B
- `H264bitstream` / `HEVCESBrowser` — xem cấu trúc NAL

## Gợi ý thứ tự đọc (theo đúng mạch vấn đề của ta)
1. `GOP structure` + `I-frame P-frame B-frame` → hiểu nén dựa trên thay đổi.
2. `intra refresh / gradual decoder refresh` → hiểu vì sao **mờ rồi rõ dần** khi không có keyframe.
3. `error propagation video` + `packet loss artifacts` → hiểu vì sao **khối vỡ lan truyền**.
4. `FIR / PLI / request keyframe` → hiểu cách khắc phục — chính là lệnh xin keyframe ta tìm được.

## Cụm tiếng Việt (nếu muốn)
"khung hình I P B" · "nén liên khung" · "chu kỳ keyframe GOP" · "mất gói gây vỡ hình" ·
"intra refresh là gì". Tài liệu tiếng Anh vẫn đầy đủ và chính xác hơn nhiều.

---
Liên quan: `tien-do-giai-ma.md` mục 6.1 (bản chất lỗi video) và mục 5.4 (lệnh xin keyframe).
