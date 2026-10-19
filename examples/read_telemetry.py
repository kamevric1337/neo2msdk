"""Demo: đọc telemetry bằng neo2sdk (API Key-based, như MSDK V5).

Chạy offline trên pcap đã bắt — khi có drone chỉ cần đổi nguồn sang "udp".

    python examples/read_telemetry.py captures/cap_09_flight_indoor.pcap
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neo2sdk import MSDKManager
from neo2sdk.keys import BatteryKey, FlightControllerKey, GimbalKey


def main(pcap):
    sdk = MSDKManager()
    sdk.connect(pcap)

    # Đăng ký listener như MSDK V5: KeyManager.listen(key, callback)
    seen = {"bat": 0, "att": 0, "alt": 0, "gim": 0}

    def on_battery(info):
        seen["bat"] += 1
        if seen["bat"] == 1 or seen["bat"] % 200 == 0:
            print(f"  [Battery]  {info.percent}%  {info.voltage_mv/1000:.2f}V  "
                  f"{info.current_ma:+d}mA  {info.remain_mah}/{info.full_mah}mAh  {info.cells}S")

    def on_attitude(att):
        seen["att"] += 1
        if seen["att"] % 300 == 0:
            print(f"  [Attitude] pitch={att.pitch:+.1f}° roll={att.roll:+.1f}° yaw={att.yaw:+.1f}°")

    def on_altitude(h):
        seen["alt"] += 1
        if seen["alt"] % 300 == 0:
            print(f"  [Altitude] {h:+.1f} m")

    def on_gimbal(g):
        seen["gim"] += 1
        if seen["gim"] % 300 == 0:
            print(f"  [Gimbal]   pitch={g.pitch:+.1f}°")

    sdk.key_manager.listen(BatteryKey.Info, on_battery)
    sdk.key_manager.listen(FlightControllerKey.Attitude, on_attitude)
    sdk.key_manager.listen(FlightControllerKey.Altitude, on_altitude)
    sdk.key_manager.listen(GimbalKey.Attitude, on_gimbal)

    print(f"Đọc {pcap} ...")
    sdk.start()

    print("\n--- Giá trị cuối cùng (KeyManager.get_value) ---")
    for key in (BatteryKey.PercentRemaining, FlightControllerKey.Attitude,
                FlightControllerKey.Altitude, FlightControllerKey.Velocity,
                FlightControllerKey.FlightState, GimbalKey.Attitude):
        print(f"  {key.path:38s} = {sdk.key_manager.get_value(key)}")
    print(f"\nThống kê: {sdk.stats}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "captures/cap_09_flight_indoor.pcap")
