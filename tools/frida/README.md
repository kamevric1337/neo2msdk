# Frida — bắt lệnh điều khiển (chuẩn bị sẵn cho buổi lab)

Mục tiêu: tìm **frame lệnh điều khiển** app→drone (mảnh ghép còn thiếu) bằng hook động,
vì phân tích thụ động + tĩnh chưa tách được (xem `notes/capture-log.md`).

## Chuẩn bị (đã làm trong các buổi trước)
- frida-server có sẵn ở `/data/local/tmp/frida-server` trên điện thoại (root qua Magisk).
- frida/frida-tools đã cài trong `.venv` (17.18.0 / 14.10.4).

## Quy trình ở lab
1. Cắm điện thoại, bật DJI Fly, kết nối Neo 2 qua Wi-Fi như thường.
2. Khởi động frida-server:
   ```
   adb shell "su -c 'nohup /data/local/tmp/frida-server >/dev/null 2>&1 &'"
   .venv/Scripts/frida-ps -U | grep -i fly        # xác nhận thấy "DJI Fly"
   ```
3. Chạy sniffer (attach vào app đang mở):
   ```
   .venv/Scripts/frida -U -n "DJI Fly" -l tools/frida/duml_sniff.js
   ```
4. **Cất cánh, hover.** Rồi đẩy **MỘT cần CHẬM** từ giữa sang hết cỡ, giữ, về giữa.
   Làm từng trục: yaw trái/phải, ga lên/xuống. (Trong nhà: yaw + ga như cap_10.)
5. Quan sát log `[TX] ...`: frame nào có **payload biến thiên mượt theo tay** = lệnh điều khiển.
   Ghi lại `set=.. id=..` và vị trí byte đổi.

## Sau khi tìm ra
- Thêm bộ dựng frame vào `neo2sdk/core/commands.py` (giống `request_iframe_frame`).
- Nối vào `MSDKManager` (cần `RequestJoystickControlAuth` trước — xem kiến trúc trong capture-log).
- Viết test byte-exact đối chiếu frame thật (như `test_request_iframe_byte_exact`).

## Ghi chú
- `duml_sniff.js` hook `sendto`/`sendmsg` của libc, lọc gói cổng 9003 kênh app→drone,
  in frame DUML (bỏ frame tunnel), gộp trùng để đỡ nhiễu.
- Nếu app dùng QUIC/đường khác cho một phần, có thể cần hook thêm; nhưng điều khiển bay
  gần như chắc chắn qua UDP 9003 như telemetry.
