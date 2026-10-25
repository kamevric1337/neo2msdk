"""Đọc telemetry LIVE từ drone — qua tcpdump trên điện thoại (adb).

    python examples/live_read.py

Yêu cầu: điện thoại cắm USB, đã root, DJI Fly đang kết nối Neo 2 (để có luồng
dữ liệu). SDK đọc và giải mã ĐỘC LẬP từ gói tin — không nhờ DJI Fly diễn giải.
Ctrl+C để thoát.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neo2sdk import MSDKManager
from neo2sdk.keys import (BatteryKey, FlightControllerKey, GimbalKey, SystemKey)


def main():
    sdk = MSDKManager().connect("adb")
    sdk.start(background=True)
    km = sdk.key_manager
    print("Đọc live từ drone (Ctrl+C để thoát)...\n")
    try:
        while True:
            time.sleep(1)
            bat = km.get_value(BatteryKey.Info)
            att = km.get_value(FlightControllerKey.Attitude)
            alt = km.get_value(FlightControllerKey.Altitude)
            st = km.get_value(FlightControllerKey.Status)
            gim = km.get_value(GimbalKey.Attitude)
            if bat is None:
                print("  (đang chờ dữ liệu...)")
                continue
            print(f"pin {bat.percent}% {bat.voltage_mv/1000:.2f}V {bat.current_ma:+d}mA | "
                  f"att p{att.pitch:+.0f} r{att.roll:+.0f} y{att.yaw:+.0f} | h {alt:+.1f}m | "
                  f"gim {gim.pitch:+.0f}° | {'BAY' if st and st.in_air else 'đất'} | "
                  f"video {sdk.stats['video_packets']}")
    except KeyboardInterrupt:
        sdk.stop()
        print("\nThoát.")


if __name__ == "__main__":
    main()
