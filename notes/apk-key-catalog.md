# Danh mục khả năng SDK (trích từ APK DJI Fly) — Ngày 6

Mục đích: liệt kê các "key/action" mà SDK nội bộ của DJI Fly hỗ trợ, để biết Neo 2 **đọc/điều khiển
được những gì** và đặt tên khớp khi tự xây SDK. Đây là tài liệu offline, không gửi gì tới drone.

## Nguồn và cách trích
- APK: `apk/dji_fly_1.21.10_base.apk` (không commit), thư viện `lib/arm64-v8a/libsdk_key_value.so`.
- Lệnh: `strings -n 5 libsdk_key_value.so | grep -E '^[A-Z][A-Za-z0-9]{4,45}$' | sort -u`
- Danh sách đầy đủ **6216 key** lưu ở `notes/apk-sdk-keys.txt` (tái tạo được từ APK).

## Lưu ý về "iLink"
Tên `libilink*.so` / namespace `ilink` KHÔNG phải giao thức link với drone, mà là **dịch vụ đăng nhập
tài khoản DJI qua cloud** (`TdiManager`, `IlinkLoginRequest`, OAuth/FaceRecognize…). `libilink_network.so`
là thư viện mạng Tencent Mars (CDN/HTTP). Giao thức UDP 9003 với drone được dựng ở lớp khác (nhiều khả
năng `libsdk_jni.so`); việc tìm chính xác bộ dựng header trong lib 87 MB đã strip là tốn công, trong
khi header đã được dựng lại đầy đủ bằng thực nghiệm (xem `capture-log.md`), nên không theo tiếp hướng này.

## Phân nhóm (số key theo chủ đề)
Camera 245 · Drone 105 · Rc 90 · Gimbal 85 · Video 67 · Battery 53 · Vision 49 · Photo 44 ·
Flight 35 · Live 21 · Motor 13 · Payload 12 · Exposure 12 · Aircraft 12 · Compass 10 ·
Obstacle 9 · Record 7 · Home 7 · Esc 6 · Zoom 5 · Landing 5 · Virtual 4 · Takeoff 3 · Stick 3 ·
Imu 3 · Gps 3 · Rtk 2 · Perception 2 · Heading 2.

## Khớp với các trường telemetry đã giải mã (Ngày 3-5)
SDK có đúng các key tương ứng với trường ta tìm được bằng thực nghiệm → xác nhận chéo:
| Trường ta giải mã | Key SDK tương ứng |
|---|---|
| % pin, điện áp | `BatteryVoltage`, `BatteryPercentNeededToLand`, … |
| Gimbal pitch + quaternion | **`GimbalAttitude`, `GimbalAttitudeQuaternion`** |
| Hướng drone (pitch/roll/yaw) | `Attitude`, `AttitudeQuaternion`, `CompassHeading` |
| Lệnh xin keyframe | `AppRequestIFrame` (xem `capture-log.md` Ngày 4) |

Đáng chú ý: SDK dùng **quaternion** cho cả gimbal lẫn drone — đúng như dữ liệu trên dây (gimbal có
quaternion ở payload, drone có `AttitudeQuaternion`).

## Lộ trình điều khiển (cho giai đoạn bay thử sau này)
Các key cho thấy cách Neo 2 nhận lệnh điều khiển — chưa dùng, chỉ đánh dấu để khảo sát khi bay:
- **Điều khiển tay ảo (virtual stick):** `IsSupportVirtualJoyStick`, `JoystickControlMode`,
  `JoystickControlSpeed`, `HandheldStickPosition`, `JoystickPitchInverted`, `JoystickYawInverted`.
  → Đây nhiều khả năng là cơ chế gửi lệnh bay (gửi vector cần điều khiển), tương tự Virtual Stick
  của MSDK V5 chính thức.
- **Cất/hạ cánh:** `IsSupportTakeOff`, `AutoTakeOffHeight`, `ArmPresentReqTakeOff`, `ConfirmForceLanding`,
  `AutoLandingGearEnable`.
- **Return-to-home:** `GoHomeMode`, `GoHomeHeight`, `GoHomeSpeed`, `GoHomeStage`, `HomeLocation`,
  `BatteryPercentNeededToGoHome`.
- **Điều khiển gimbal:** `GimbalAngleRotation`, `GimbalMotionControlReq`, `GimbalRollAngleControl`,
  `GimbalFollowSpeed`, `GimbalResetCommandMsg`, `GimbalControlRightRequest`.

## Việc tiếp theo dựa trên danh mục này
- Khi bay thử: bắt gói lúc đẩy cần điều khiển trong app, đối chiếu với nhóm `Joystick*` để tìm
  **frame lệnh điều khiển** (app → FC), cấu trúc vector cần.
- Đối chiếu từng key với cmd_set/cmd_id DUML (cần disassemble sâu hơn `libsdk_jni.so`, hoặc suy ra
  từ thực nghiệm) để lập bảng key ↔ lệnh hoàn chỉnh cho SDK.
