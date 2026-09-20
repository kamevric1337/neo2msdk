# Môi trường PoC Neo 2 (cập nhật ngày 21/09/2026)

- Máy tính: Windows 11 25H2 build 26200, i5-1335U, RAM 16 GB
- Thư mục dự án: D:\neo2-msdk
- Python: 3.13.7 (64-bit) tại D:\Miscellanous\Python, venv tại .venv
- frida / frida-tools: 17.18.0 / 14.10.4
- bleak 3.0.2, scapy 2.7.0, pyshark 0.6, fastcrc 0.3.6
- adb: 1.0.41, platform-tools 37.0.1 (2 bản cùng phiên bản: Android SDK + tools\platform-tools)
- Wireshark / TShark: 4.6.8, Npcap 1.88, Lua 5.4.6
- JDK: Temurin 21.0.12.1 (JAVA_HOME = C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot)
- jadx: 1.5.6
- Ghidra: 12.1.3_PUBLIC, project neo2 tại D:\neo2-msdk\ghidra-projects
- dji-firmware-tools: đã clone vào tools\dji-firmware-tools (xem `git log` trong thư mục đó để lấy commit chính xác)
- Dissector DUML: 13 file .lua chép vào tools\dji-dissectors (không có init.lua ở đó); init.lua đặt tại
  %APPDATA%\Wireshark\plugins\init.lua, biến dji_script_path trỏ tới "D:/neo2-msdk/tools/dji-dissectors/"
- Điện thoại: Samsung SM-G780G (S20 FE), đã root sẵn (công cụ root chưa xác định), serial RF8W409975R,
  trạng thái adb lần cuối kiểm tra: không có thiết bị kết nối (chưa cắm/chưa authorized) — cần làm ở Ngày 2
- Kết quả check_env.py: ALL OK - Day 1 done (chạy lúc 21/09/2026)

## Việc còn cần xác nhận thủ công (GUI, do người dùng làm)
- [ ] Mở Wireshark: không có hộp thoại "Lua: Error during loading"
- [ ] Help → About Wireshark → tab Plugins: có dòng `init.lua`
- [ ] Analyze → Enabled Protocols…, gõ `dji`: thấy `DJI_DUMLV1`, `DJI_MAVIC`, `DJI_P3`
