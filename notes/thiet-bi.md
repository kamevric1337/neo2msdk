# Thiết bị: điện thoại (cập nhật ngày 21/09/2026)

- Model: Samsung Galaxy S20 FE, SM-G780G (Exynos 990, arm64-v8a)
- Android: 13
- Security patch: 2025-10-01
- adb serial: RF8W409975R
- Trạng thái adb: `device` (đã Allow USB debugging, không còn `unauthorized`)
- Root: Magisk (`com.topjohnwu.magisk` có cài; `su -c id` trả về
  `uid=0(root) gid=0(root) groups=0(root) context=u:r:magisk:s0`)
- KernelSU: không có
- tcpdump: có sẵn tại `/system/bin/tcpdump` (không cần cài)
- Package DJI ban đầu tìm thấy: `com.smartremote.djiflydrone` — tra cứu web xác nhận đây là
  **"Fly Go 4: Drone Camera Remote"**, app bên thứ ba của "Smart Remote Application"
  (smartremotedev.com), KHÔNG PHẢI DJI, yêu cầu nhập thẻ tín dụng trước khi dùng lần đầu.
  → Đã gỡ bỏ (`adb uninstall com.smartremote.djiflydrone`, thành công) ngày 21/09/2026.
- DJI Fly chính hãng: đã cài, package `dji.go.v5`, versionName 1.21.10, versionCode 3115981,
  minSdk 24 / targetSdk 34, installerPackageName=com.google.android.packageinstaller.
- frida-server: push lên `/data/local/tmp/frida-server` (58856048 bytes), chmod 755, chạy bằng
  `su` (PID 27606). `frida-ps -U` từ máy tính chạy OK, thấy tiến trình "DJI Fly" (PID 25992)
  đang chạy trên điện thoại — người dùng đã mở app.
  Lưu ý: trên Git Bash/MSYS, lệnh `adb push`/`adb shell` với đường dẫn Unix tuyệt đối
  (`/data/local/tmp/...`) bị MSYS tự dịch sai thành đường dẫn Windows → phải chạy với
  `MSYS_NO_PATHCONV=1` phía trước. Không gặp vấn đề này khi chạy trong cmd.exe thường.

- Ghép cặp trực tiếp qua Wi-Fi: đã kết nối thành công (không dùng RC), chưa cất cánh/điều khiển gì.
  `wlan0` trên điện thoại: IP `192.168.2.12/24`. ARP/neighbor cho thấy Neo 2 ở
  `192.168.2.1` (MAC `4c:43:f6:d8:b6:3a`). Không thấy default route (chỉ có route nội bộ
  `192.168.2.0/24 dev wlan0`) — cần lưu ý khi capture Ngày 3, traffic tới drone chắc chắn
  là UDP/TCP tới `192.168.2.1` trên cùng subnet.
- APK: đã pull `apk\dji_fly_1.21.10_base.apk` (719464897 bytes, chỉ có base.apk, không có
  split APK) — không commit (nằm trong .gitignore).
- DJI Fly không báo lỗi phát hiện root khi chạy được tới bước xem video (chưa cần ẩn root bằng
  Magisk DenyList).

## Ngày 2: hoàn tất
Đủ điều kiện định nghĩa hoàn thành Ngày 2: `adb devices` → `device`, `su -c id` → root,
`frida-ps -U` chạy được, `tcpdump` có sẵn, DJI Fly kết nối và xem được Neo 2 qua Wi-Fi trực tiếp,
APK đã lưu.
