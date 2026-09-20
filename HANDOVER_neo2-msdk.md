# HANDOVER: Dự án MSDK riêng cho DJI Neo 2

**Tài liệu này dành cho Claude Code CLI chạy trên máy Windows của Quyền.**
Đọc hết trước khi chạy bất cứ lệnh nào. Cập nhật lần cuối: ngày bàn giao (xem `git log`).

---

## 0. Cách dùng tài liệu này

- Mục 1–3: bối cảnh và mục tiêu. Đọc để hiểu vì sao làm.
- Mục 4: **trạng thái môi trường thực tế đã kiểm chứng** — không giả định gì khác ngoài mục này.
- Mục 5: **việc cần làm ngay** (Bước 10, 11 của Ngày 1).
- Mục 6: kế hoạch Ngày 2–7.
- Mục 7: giới hạn và quy tắc bắt buộc.
- Phụ lục A–D: script, cấu trúc giao thức, lệnh hay dùng, thuật ngữ.

**Quy tắc làm việc với người dùng:**
1. Những thao tác GUI (Wireshark, màn hình điện thoại, cài app) thì **hướng dẫn người dùng làm**, không tự giả lập kết quả.
2. Trước khi chạy lệnh làm thay đổi điện thoại (push file, cài app, sửa quyền), **hỏi xác nhận**.
3. Không bao giờ báo "đã xong" một bước nếu chưa chạy lệnh kiểm tra tương ứng trong mục "Kiểm tra" của bước đó.
4. Nếu kết quả thực tế khác tài liệu này, tin kết quả thực tế và **cập nhật lại tài liệu này** (`notes\HANDOVER_neo2-msdk.md`) rồi commit.

---

## 1. Bối cảnh

- DJI **Neo 2** chưa được MSDK V5 chính thức hỗ trợ (kiểm tra tháng 9/2026: các issue xin hỗ trợ Neo 1/Neo 2 trên repo `dji-sdk/Mobile-SDK-Android-V5` vẫn mở, danh sách sản phẩm MSDK không có dòng Neo). Vì vậy không thể viết chương trình theo dõi/điều khiển bằng SDK chuẩn.
- App **DJI Fly** vẫn điều khiển Neo 2 bình thường.
- Hướng đã chọn: **reverse-engineer giao thức DJI Fly ↔ Neo 2**, rồi tự xây MSDK riêng **tuân theo convention của MSDK V5 gốc** (Key-based Manager, KeyManager, layer App → MSDK Manager → SDK Core → Transport).

## 2. Roadmap tổng thể

1. Nghiên cứu cấu trúc MSDK V5 gốc (làm song song).
2. Revert giao thức bằng capture traffic + decompile APK.
3. Xây MSDK riêng, 3 phase:
   - **Phase 1:** xem video + đọc telemetry + điều khiển cơ bản bằng chương trình tự revert.
   - **Phase 2:** đóng gói thành MSDK, tích hợp vào sample app MSDK gốc.
   - **Phase 3:** mở cho người khác lập trình trên MSDK này.

## 3. Đang ở đâu: Phase 1, Hướng A (PoC), kế hoạch 7 ngày

Mục tiêu PoC: bắt được traffic thật → nhìn ra cấu trúc frame → đối chiếu code APK → **verify được ít nhất 1 trường dữ liệu (battery %)**. Chưa cần điều khiển bay thật.

| Ngày | Nội dung | Trạng thái |
|---|---|---|
| 1 | Cài công cụ trên máy tính | **Đang làm — xong Bước 9/11** |
| 2 | Chuẩn bị điện thoại (đã root sẵn) + DJI Fly | Chưa |
| 3 | Capture traffic lần đầu | Chưa |
| 4 | Đọc traffic bằng Wireshark | Chưa |
| 5 | Decompile APK (jadx + Ghidra) | Chưa |
| 6 | Đối chiếu code ↔ traffic, verify battery % | Chưa |
| 7 | Verify lại + viết báo cáo PoC | Chưa |

**Thay đổi quan trọng so với kế hoạch ban đầu (đã thống nhất, không được quay lại bản cũ):**

- **Bỏ HCI snoop log làm đường capture chính.** Log đó chỉ ghi Bluetooth. Khi bay qua RC, điện thoại nối RC bằng **cáp USB** nên dữ liệu không đi qua Bluetooth; khi nối thẳng điện thoại với Neo 2 thì BLE chỉ dùng để đánh thức/ghép nối, còn video + telemetry đi qua **Wi-Fi**.
- **Kịch bản PoC = điện thoại ↔ Neo 2 trực tiếp qua Wi-Fi**, capture bằng `tcpdump` trên máy đã root. Kịch bản RC + USB để sau (khó hơn, phải hook Frida vào chỗ app đọc/ghi USB).
- **Thêm Frida** vào bộ công cụ: dùng khi payload bị mã hóa, hook ở điểm trước khi mã hóa.
- **Thêm Ghidra**: jadx chỉ đọc được lớp Java/Kotlin, phần xử lý giao thức của DJI nhiều khả năng nằm trong thư viện native `.so`.

---

## 4. Trạng thái môi trường (đã kiểm chứng bằng lệnh)

### 4.1 Máy tính

| Hạng mục | Giá trị |
|---|---|
| OS | Windows 11 25H2, build 26200 |
| CPU / RAM | Intel i5-1335U / 16 GB |
| Thư mục dự án | `D:\neo2-msdk` |
| Python | 3.13.7, 64-bit, tại `D:\Miscellanous\Python\python.exe` |
| venv | `D:\neo2-msdk\.venv` (activate bằng `.venv\Scripts\activate.bat`) |
| pip | 26.2.1 |
| Thư viện | bleak 3.0.2, scapy 2.7.0, pyshark 0.6, fastcrc 0.3.6, frida 17.18.0, frida-tools 14.10.4 |
| adb | 1.0.41 / 37.0.1-15733141 — **có 2 bản trùng phiên bản** |
| Wireshark / TShark | 4.6.8, Npcap 1.88, **Lua 5.4.6**, hiện `Plugins: 0 loaded` |
| JDK | Temurin 21.0.12.1, `JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot\` |
| jadx | 1.5.6 |
| Ghidra | 12.1.3_PUBLIC, đã tạo project `neo2` |

**Đường dẫn quan trọng:**

```
D:\neo2-msdk\
├─ .venv\
├─ captures\                 (pcap — KHÔNG commit)
├─ apk\                      (APK DJI Fly — KHÔNG commit)
├─ notes\                    (ghi chép, tài liệu này, báo cáo)
├─ poc\                      (code PoC)
├─ ghidra-projects\neo2      (project Ghidra)
├─ requirements.txt
└─ tools\
   ├─ platform-tools\adb.exe
   ├─ jadx\bin\jadx.bat, jadx-gui.bat            (1.5.6)
   ├─ ghidra\ghidra_12.1.3_PUBLIC\ghidraRun.bat  (12.1.3)
   ├─ android\                                    (frida-server, Magisk apk)
   ├─ dji-firmware-tools\                         (BƯỚC 10 — chưa clone)
   ├─ dji-dissectors\                             (BƯỚC 10 — chưa tạo)
   └─ check_env.py                                (xem Phụ lục A)
```

**Hai bản adb cùng phiên bản `37.0.1-15733141`:**
- `C:\Users\admin\AppData\Local\Android\Sdk\platform-tools\adb.exe` (đứng trước trong PATH)
- `D:\neo2-msdk\tools\platform-tools\adb.exe`

Hiện không xung đột. Nếu sau này gặp lỗi `adb server version doesn't match this client`, xử lý bằng cách bỏ `D:\neo2-msdk\tools\platform-tools` khỏi PATH (giữ bản Android SDK), rồi `adb kill-server`.

**Java:** ngoài Temurin 21 còn có Microsoft JDK 17 và Oracle `javapath`, đứng sau trong PATH. Nếu Ghidra/jadx báo sai phiên bản Java, kiểm tra `java -version` và đẩy Temurin 21 lên đầu **System variables → Path**.

### 4.2 Điện thoại

| Hạng mục | Giá trị |
|---|---|
| Model | Samsung Galaxy S20 FE, **SM-G780G** (Exynos 990, arm64) |
| Root | **Đã root sẵn** — chưa biết bằng công cụ gì (Magisk / KernelSU / APatch) |
| adb serial | `RF8W409975R` |
| Trạng thái adb lần cuối | `unauthorized` — chưa bấm "Allow USB debugging" trên máy |
| Android version | **Chưa biết** |
| ROM | **Chưa biết** (gốc hay custom) |

Vì máy đã root nên **Ngày 2 không còn khâu mở bootloader, không mất dữ liệu, không lo trip Knox**. Ngày 2 chỉ còn cấu hình và cài đặt.

### 4.3 Thiết bị bay

DJI Neo 2, có sẵn, dùng để test và capture.

### 4.4 Những thứ CHƯA xác nhận (phải kiểm tra, đừng giả định là đã có)

- [ ] `git --version` và repo đã `git init` chưa, `.gitignore` đã tạo chưa
- [ ] `notes\moi-truong.md` đã ghi chưa
- [ ] `tools\check_env.py` đã được copy vào máy chưa (nếu chưa, tạo lại từ Phụ lục A)
- [ ] Bước 9: `tools\android\frida-server-17.18.0-android-arm64` (đã giải nén, không còn `.xz`) và `Magisk-v*.apk`
- [ ] `jadx-gui.bat` mở được cửa sổ GUI

---

## 5. VIỆC CẦN LÀM NGAY

### 5.0 Kiểm tra trạng thái trước

Chạy trong **cmd** (không PowerShell):

```cmd
cd /d D:\neo2-msdk
git --version
git status
dir tools\android
dir tools
where adb
```

Báo lại cho người dùng cái gì thiếu. Nếu chưa `git init`, làm mục 5.1.

### 5.1 Git (nếu chưa có)

```cmd
cd /d D:\neo2-msdk
git init
```

Tạo `.gitignore` với nội dung:

```
.venv/
tools/
captures/
apk/
ghidra-projects/
```

Lý do loại trừ: `captures/` chứa file lớn và có thể chứa số serial thiết bị; `apk/` là phần mềm của DJI, không được phân phối lại; `tools/` là binary tải về, tái tạo được.

### 5.2 BƯỚC 10 — Cài dissector DUML cho Wireshark

Mục đích: để Wireshark hiển thị các trường trong frame DJI (cmd set, cmd id, payload) thay vì chỉ byte thô. Dùng repo `o-gs/dji-firmware-tools`.

> **Cảnh báo quan trọng:** KHÔNG chép tất cả file `.lua` vào thư mục plugin của Wireshark. README của repo nói rõ làm vậy sẽ gây hàng loạt lỗi "Lua: Error during loading". Cách đúng: các file `.lua` để ở thư mục **ngoài** cây plugin, chỉ `init.lua` đặt trong thư mục plugin, và sửa `init.lua` trỏ tới thư mục kia.

**10.1 Clone:**

```cmd
cd /d D:\neo2-msdk\tools
git clone https://github.com/o-gs/dji-firmware-tools
dir dji-firmware-tools\comm_dissector\wireshark\*.lua
```

Kỳ vọng: hàng chục file `.lua`, trong đó có `init.lua`. Nếu sai đường dẫn: `dir /s /b dji-firmware-tools\init.lua`.

**10.2 Chép các file Lua ra thư mục riêng (trừ `init.lua`):**

```cmd
mkdir dji-dissectors
copy dji-firmware-tools\comm_dissector\wireshark\*.lua dji-dissectors\
del dji-dissectors\init.lua
dir dji-dissectors\*.lua
```

Kiểm tra: `dji-dissectors` có nhiều file `.lua` và **không có** `init.lua`.

**10.3 Chép `init.lua` vào thư mục plugin:**

Thư mục Personal Lua Plugins của máy này gần như chắc chắn là `C:\Users\admin\AppData\Roaming\Wireshark\plugins` (`%APPDATA%\Wireshark\plugins`). Người dùng có thể xác nhận trong Wireshark: **Help → About Wireshark → tab Folders → Personal Lua Plugins**.

**Yêu cầu người dùng đóng hẳn Wireshark trước**, rồi:

```cmd
mkdir "%APPDATA%\Wireshark\plugins"
copy dji-firmware-tools\comm_dissector\wireshark\init.lua "%APPDATA%\Wireshark\plugins\"
```

**10.4 Sửa đường dẫn trong `init.lua`:**

Mở `%APPDATA%\Wireshark\plugins\init.lua`, tìm biến chuỗi chứa đường dẫn thư mục chứa các file Lua (được ghép với tên file trong các lệnh `dofile(...)`). Sửa thành:

```
D:/neo2-msdk/tools/dji-dissectors/
```

Ba lưu ý khi sửa:
1. Dùng `/`, không dùng `\`. Trong chuỗi Lua `\` là ký tự thoát; nếu buộc dùng `\` phải viết `\\`.
2. Giữ đúng kiểu có/không có dấu gạch ở cuối như chuỗi gốc, vì tên file được nối ngay sau.
3. Không xóa dấu nháy kép bao quanh chuỗi.

Nếu cấu trúc file khác dự đoán, in nội dung ra và phân tích trước khi sửa, đừng sửa mù.

**10.5 Kiểm tra (người dùng làm trên GUI):**
1. Mở Wireshark, **không** có hộp thoại "Lua: Error during loading".
2. **Help → About Wireshark → tab Plugins**: có dòng `init.lua`.
3. **Analyze → Enabled Protocols…**, gõ `dji`: thấy `DJI_DUMLV1`, `DJI_MAVIC`, `DJI_P3`…

**Rủi ro đã biết:** máy chạy Wireshark 4.6.8 / Lua 5.4.6, còn README repo ghi cập nhật cho 4.4.6. Hai loại lỗi có thể gặp:
- Lỗi không tìm thấy file → sai đường dẫn trong `init.lua`, sửa lại 10.4.
- Lỗi liên quan `bit32` → thư viện `bit32` bị bỏ từ Lua 5.4; cần shim hoặc sửa code Lua. **Không tự sửa hàng loạt file** — báo người dùng, chép nguyên văn lỗi, rồi tìm giải pháp (issue của repo, hoặc viết shim `bit32` nhỏ nạp trước trong `init.lua`).

Việc gán dissector cho pcap (DLT_USER / Decode As) **để Ngày 4**, khi đã có pcap thật.

### 5.3 BƯỚC 11 — Chạy check_env.py

Nếu `tools\check_env.py` chưa có, tạo lại từ **Phụ lục A**. Sửa dòng `ROOT` nếu thư mục dự án khác.

```cmd
cd /d D:\neo2-msdk
.venv\Scripts\activate.bat
python tools\check_env.py
```

Kỳ vọng: mọi dòng `[OK  ]` và cuối cùng `ALL OK - Day 1 done.`

Sau đó ghi `notes\moi-truong.md` (mẫu ở Phụ lục C) và commit:

```cmd
git add .gitignore requirements.txt notes
git commit -m "Day 1: environment setup"
```

**Ngày 1 kết thúc khi `check_env.py` báo ALL OK và đã commit.**

---

## 6. Kế hoạch Ngày 2–7

### Ngày 2 — Chuẩn bị điện thoại (máy đã root)

**2.1 Cho phép adb.** Người dùng mở khóa màn hình khi cắm cáp, bấm **Allow** ở hộp thoại *Allow USB debugging?* và tick *Always allow from this computer*. Nếu không hiện: **Developer options → Revoke USB debugging authorizations**, rút cắm lại, `adb kill-server`, `adb devices`.

**2.2 Thu thập thông tin máy:**

```cmd
adb devices
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release
adb shell getprop ro.product.cpu.abi
adb shell getprop ro.build.version.security_patch
adb shell "su -c id"
adb shell "pm list packages | findstr -i magisk"
adb shell "pm list packages | findstr -i kernelsu"
```

`su -c id` phải trả về `uid=0(root)`. Lệnh đầu tiên gọi `su` thường bật hộp thoại xin quyền trên màn hình điện thoại — báo người dùng bấm cho phép (và chọn "nhớ mãi"), rồi chạy lại.

Ghi tất cả vào `notes\thiet-bi.md`.

**2.3 frida-server:**

```cmd
adb push D:\neo2-msdk\tools\android\frida-server-17.18.0-android-arm64 /data/local/tmp/frida-server
adb shell "su -c 'chmod 755 /data/local/tmp/frida-server'"
adb shell "su -c '/data/local/tmp/frida-server &'"
```

Kiểm tra từ máy tính (venv đã activate): `frida-ps -U` → liệt kê tiến trình trên điện thoại. Phiên bản frida-server phải là **17.18.0**, khớp `frida --version`.

**2.4 tcpdump:** kiểm tra máy có sẵn chưa: `adb shell "su -c 'which tcpdump'"`. Nếu không có, cài bằng binary tĩnh arm64 hoặc module Magisk — **hỏi người dùng trước khi tải từ nguồn ngoài**, và chỉ dùng nguồn có uy tín rõ ràng.

**2.5 DJI Fly:** cài lên điện thoại (bản chính thức từ DJI hoặc Play Store), đăng nhập, bắt cặp với Neo 2, xác nhận xem được video. Lưu file APK vào `D:\neo2-msdk\apk\` cho Ngày 5:

```cmd
adb shell pm path <package_dji_fly>
adb pull <đường_dẫn_base.apk> D:\neo2-msdk\apk\
```

Tìm package name: `adb shell "pm list packages | findstr -i dji"`.

**2.6 Ẩn root nếu cần:** nếu DJI Fly từ chối chạy vì phát hiện root, dùng Zygisk + DenyList (Magisk) hoặc cơ chế tương đương của công cụ root đang dùng, thêm package DJI Fly vào danh sách.

**Định nghĩa hoàn thành Ngày 2:** `adb devices` báo `device`; `su -c id` ra root; `frida-ps -U` chạy được; `tcpdump` chạy được bằng root; DJI Fly xem được video từ Neo 2; APK đã lưu vào `apk\`.

### Ngày 3 — Capture traffic lần đầu

Kịch bản: **điện thoại nối trực tiếp Neo 2 qua Wi-Fi** (không dùng RC).

1. Xác định interface và dải IP khi đã kết nối Neo 2:
   ```cmd
   adb shell "su -c 'ip addr'"
   adb shell "su -c 'ip route'"
   ```
   Ghi lại tên interface (thường `wlan0`) và IP của drone — **không đoán, phải đọc từ lệnh**.
2. Capture:
   ```cmd
   adb shell "su -c 'tcpdump -i wlan0 -s 0 -w /sdcard/cap_<hanhdong>.pcap'"
   ```
   Dừng bằng Ctrl+C, rồi `adb pull /sdcard/cap_<hanhdong>.pcap D:\neo2-msdk\captures\`.
3. **Ghi log riêng cho từng hành động**, mỗi lần một file, đặt tên rõ ràng, và ghi mốc thời gian + mô tả vào `notes\capture-log.md`:
   - `01_connect` — chỉ kết nối, không làm gì khác
   - `02_idle_30s` — để yên 30 giây (để thấy gói telemetry định kỳ)
   - `03_video_start` — bật xem video
   - `04_battery_drain` — để pin tụt vài phần trăm, ghi lại % thật hiện trên app theo thời gian
   - `05_takeoff_hover_land` — chỉ làm khi an toàn (xem mục 7)

Mẹo cho Ngày 6: ở `04_battery_drain`, ghi lại **thời điểm chính xác** khi app hiển thị mỗi mức % (ví dụ 15:02:31 → 87%). Đây là mấu chốt để tìm byte chứa battery %.

### Ngày 4 — Đọc traffic

1. Mở pcap bằng Wireshark, xem traffic giữa điện thoại và IP của drone (chủ yếu UDP).
2. Tìm dấu hiệu DUML: byte `0x55` ở đầu payload, độ dài hợp lý, CRC đúng.
3. Nếu có frame DUML: dùng **Decode As** hoặc DLT_USER để gán `dji_dumlv1`.
4. Nếu payload trông ngẫu nhiên, **không** có `0x55` lặp lại → nhiều khả năng bị mã hóa. **Dừng hướng pcap**, chuyển sang Frida: hook chỗ app ghi/đọc socket hoặc hàm đóng gói trong `.so`, dump plaintext.
5. Viết script Python trong `poc\` dùng `scapy`/`pyshark` để lọc frame và `fastcrc` để kiểm CRC (cấu trúc frame ở Phụ lục B).

### Ngày 5 — Decompile APK

1. `jadx-gui` mở APK trong `apk\` → tìm lớp liên quan tới giao thức, cmd set/cmd id, battery.
2. Từ khóa gợi ý: `duml`, `cmdSet`, `cmdId`, `battery`, `capacityPercent`, `pack`, `unpack`, `crc`.
3. APK lớn nên jadx-gui dễ thiếu RAM: tăng heap bằng biến môi trường `JADX_OPTS` hoặc chỉnh trong Preferences; máy có 16 GB.
4. Nhiều khả năng phần lõi nằm trong `.so` (`lib/arm64-v8a/`). Giải nén APK (là file zip) lấy `.so` rồi mở bằng Ghidra project `neo2`.
5. Ghi phát hiện vào `notes\apk-findings.md`, kèm tên lớp/hàm và offset.

### Ngày 6 — Đối chiếu, verify battery %

1. Từ pcap `04_battery_drain`, tìm byte thay đổi đúng vào thời điểm app đổi %.
2. Đối chiếu với cmd set/cmd id tìm được trong APK và trong dissector DUML.
3. Viết script trong `poc\` đọc pcap và in ra battery % theo thời gian.
4. **Tiêu chí đạt:** giá trị script in ra khớp với % mà app hiển thị tại cùng thời điểm, trên ít nhất 2 lần capture độc lập.

### Ngày 7 — Verify lại + báo cáo

Viết `notes\bao-cao-poc.md` gồm: kịch bản capture, cấu trúc frame quan sát được, cách định vị trường battery, bằng chứng verify, những gì chưa làm được (mã hóa? kịch bản RC?), và đề xuất cho Phase 1 tiếp theo (video + telemetry + điều khiển).

---

## 7. Giới hạn và quy tắc bắt buộc

**An toàn khi bay:**
- Mọi thử nghiệm liên quan tới lệnh điều khiển làm khi **đã tháo cánh quạt**, trừ khi người dùng nói rõ đang ở nơi an toàn và chủ động chấp nhận.
- Không gửi gói lệnh tự chế tới drone trong giai đoạn PoC. PoC chỉ **đọc** traffic.

**Phạm vi kỹ thuật:**
- Chỉ làm telemetry, video, điều khiển thông thường.
- **Không** đụng tới geofencing/no-fly zone, Remote ID, chữ ký firmware, hay bất cứ cơ chế an toàn/tuân thủ nào. Repo `dji-firmware-tools` có công cụ sửa firmware — **không dùng phần đó**.
- Không flash, không sửa firmware của Neo 2.

**Pháp lý và phân phối:**
- Không commit và không phân phối lại APK DJI Fly, code decompile, hay khóa trích từ app.
- Phase 3 chỉ công bố code tự viết và mô tả giao thức.
- Bay drone ở Việt Nam cần tuân thủ quy định hiện hành; việc reverse-engineer có thể trái điều khoản sử dụng của DJI — đây là quyết định của người dùng, nhưng không tự ý mở rộng phạm vi ngoài những gì đã nêu.

**Dữ liệu:**
- File pcap có thể chứa số serial thiết bị và thông tin tài khoản. Không đưa lên git, không chia sẻ nguyên file ra ngoài.

**Kỹ thuật:**
- Dùng **cmd**, không PowerShell (vấn đề `where` và execution policy).
- Mọi lệnh Python chạy trong venv đã activate.
- Sau khi sửa PATH phải mở cmd mới.
- Không tự cài thêm phần mềm từ nguồn không chính thức; hỏi người dùng trước.

---

## Phụ lục A — `tools\check_env.py`

Nếu file đã có trên máy thì dùng bản đó. Nếu mất, tạo lại nguyên văn:

```python
# check_env.py - kiem tra moi truong Ngay 1 (du an MSDK rieng cho DJI Neo 2)
import glob, importlib, os, re, shutil, struct, subprocess, sys

ROOT = r"D:\neo2-msdk"
TOOLS = os.path.join(ROOT, "tools")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

results = []

def report(name, ok, detail=""):
    results.append(ok)
    print(f"[{'OK  ' if ok else 'FAIL'}] {name:<24} {detail}")

def run(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception as e:
        return False, str(e)
    lines = (r.stdout + r.stderr).strip().splitlines()
    return r.returncode == 0, (lines[0].strip() if lines else "")

def first_match(*patterns):
    for p in patterns:
        hits = sorted(glob.glob(p))
        if hits:
            return hits[-1]
    return None

print("== 1. Python ==")
bits = struct.calcsize("P") * 8
report("python", bits == 64 and sys.version_info >= (3, 11),
       f"{sys.version.split()[0]}, {bits}-bit")
report("venv active", sys.prefix != sys.base_prefix, sys.prefix)

print("\n== 2. Commands in PATH ==")
cli_frida = None
for name, cmd in [("git",    ["git", "--version"]),
                  ("adb",    ["adb", "version"]),
                  ("tshark", ["tshark", "--version"]),
                  ("java",   ["java", "-version"]),
                  ("frida",  ["frida", "--version"])]:
    path = shutil.which(cmd[0])
    if not path:
        report(name, False, "not found in PATH")
        continue
    ok, first = run([path] + cmd[1:])
    if name == "java":
        m = re.search(r'version "(\d+)', first)
        ok = ok and bool(m) and int(m.group(1)) >= 21
    if name == "frida":
        cli_frida = first
    report(name, ok, f"{first}  <- {path}")

print("\n== 3. Python packages ==")
for mod_name in ["bleak", "scapy", "pyshark", "fastcrc", "frida"]:
    try:
        mod = importlib.import_module(mod_name)
        ver = str(getattr(mod, "__version__", ""))
        if mod_name == "frida":
            ok = cli_frida is None or ver == cli_frida
            report("module frida", ok, f"{ver} (CLI: {cli_frida})")
        else:
            report(f"module {mod_name}", True, ver)
    except Exception as e:
        report(f"module {mod_name}", False, repr(e))

print("\n== 4. Tools & files ==")
jadx = first_match(os.path.join(TOOLS, "jadx", "bin", "jadx-gui.bat"))
report("jadx-gui.bat", jadx is not None, jadx or r"missing tools\jadx\bin\jadx-gui.bat")

ghidra = first_match(os.path.join(TOOLS, "ghidra", "*", "ghidraRun.bat"),
                     os.path.join(TOOLS, "ghidra", "ghidraRun.bat"))
report("ghidraRun.bat", ghidra is not None, ghidra or r"missing tools\ghidra\...\ghidraRun.bat")

magisk = first_match(os.path.join(TOOLS, "android", "Magisk-*.apk"))
report("Magisk apk", magisk is not None,
       os.path.basename(magisk) if magisk else r"missing tools\android\Magisk-*.apk")

fs = [p for p in glob.glob(os.path.join(TOOLS, "android", "frida-server-*-android-arm64*"))
      if not p.lower().endswith(".xz")]
if fs:
    fs_name = os.path.basename(sorted(fs)[-1])
    parts = fs_name.split("-")
    fs_ver = parts[2] if len(parts) > 2 else "?"
    report("frida-server", cli_frida is None or fs_ver == cli_frida,
           f"{fs_name} (CLI: {cli_frida})")
else:
    report("frida-server", False, "not found or still .xz (extract it with 7-Zip)")

dis_dir = os.path.join(TOOLS, "dji-dissectors")
luas = glob.glob(os.path.join(dis_dir, "*.lua"))
has_init = os.path.exists(os.path.join(dis_dir, "init.lua"))
report("dissector .lua files", len(luas) > 5 and not has_init,
       f"{len(luas)} files in {dis_dir}" + ("  (init.lua must NOT be here)" if has_init else ""))

init_path = os.path.join(os.environ.get("APPDATA", ""), "Wireshark", "plugins", "init.lua")
if os.path.exists(init_path):
    with open(init_path, encoding="utf-8", errors="ignore") as f:
        txt = f.read()
    pointed = "dji-dissectors" in txt
    report("init.lua in plugins", pointed,
           init_path + ("" if pointed else "  (path inside not edited yet?)"))
else:
    report("init.lua in plugins", False, "missing " + init_path)

print()
n_fail = results.count(False)
print("ALL OK - Day 1 done." if n_fail == 0
      else f"{n_fail} item(s) FAIL - fix the lines marked FAIL above.")
```

---

## Phụ lục B — Cấu trúc frame DUML (giả thuyết, phải verify)

Các dòng DJI trước đây dùng giao thức **DUML**. Cấu trúc tổng quát:

| Vị trí | Nội dung |
|---|---|
| byte 0 | delimiter `0x55` |
| byte 1–2 | độ dài gói + version (10 bit thấp là length, bit cao là protocol version) |
| byte 3 | CRC8 của header |
| byte 4 | sender (loại thiết bị + index) |
| byte 5 | receiver |
| byte 6–7 | sequence number |
| byte 8 | cmd type / flags |
| byte 9 | cmd set |
| byte 10 | cmd id |
| byte 11… | payload |
| 2 byte cuối | CRC16 toàn gói |

Chi tiết chính xác phải đọc từ `dji-dumlv1-proto.lua` trong repo (file này chính là tài liệu giao thức dưới dạng code Lua). Cmd set `0x03` là Flight Control; thông tin pin thường nằm ở cmd set riêng — tra trong `dji-dumlv1-*.lua`.

**Không coi bảng này là chân lý.** Neo 2 là dòng mới, có thể khác. Việc của Ngày 4 là kiểm chứng trên dữ liệu thật.

---

## Phụ lục C — Mẫu `notes\moi-truong.md`

```markdown
# Môi trường PoC Neo 2 (cập nhật ngày ....../....../......)

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
- dji-firmware-tools: commit ......
- Điện thoại: Samsung SM-G780G (S20 FE), đã root bằng ......, Android ......, serial RF8W409975R
- Kết quả check_env.py: ......
```

---

## Phụ lục D — Lệnh hay dùng

```cmd
:: Vào môi trường dự án
cd /d D:\neo2-msdk && .venv\Scripts\activate.bat

:: Điện thoại
adb devices
adb shell "su -c id"
adb shell "su -c 'ip addr'"
adb shell "pm list packages | findstr -i dji"

:: Frida
frida-ps -U
frida-ps -Uai

:: Kiểm tra môi trường
python tools\check_env.py

:: Wireshark dòng lệnh
tshark -r captures\cap_01_connect.pcap -c 20
tshark -r captures\cap_01_connect.pcap -Y "udp" -T fields -e ip.src -e ip.dst -e data.data
```

---

## Tóm tắt cho lần chạy đầu tiên của Claude Code

1. Chạy mục **5.0** để biết trạng thái thật.
2. Làm **5.1** nếu git chưa sẵn sàng.
3. Làm **5.2 (Bước 10)** — chú ý cảnh báo về `init.lua`, và các bước GUI thì hướng dẫn người dùng.
4. Làm **5.3 (Bước 11)**, đạt `ALL OK`, ghi `notes\moi-truong.md`, commit.
5. Sang **Ngày 2**, bắt đầu bằng việc cho phép USB debugging và thu thập `getprop`.
6. Sau mỗi ngày, cập nhật trạng thái trong tài liệu này và commit.
