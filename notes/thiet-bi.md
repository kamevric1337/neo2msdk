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

## Việc còn lại của Ngày 2
- [ ] frida-server: push lên máy, chạy, xác nhận `frida-ps -U` liệt kê được tiến trình
- [ ] DJI Fly (`dji.go.v5`): đăng nhập, ghép cặp Neo 2, xác nhận xem được video
- [ ] Lưu APK vào `apk\` (dùng `pm path dji.go.v5` rồi `adb pull`)
- [ ] Ẩn root nếu DJI Fly từ chối chạy vì phát hiện root (Zygisk + DenyList trong Magisk)
