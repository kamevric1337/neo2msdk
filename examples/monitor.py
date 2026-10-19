"""Dashboard telemetry trực quan (terminal) dùng neo2sdk.

Vẽ lại bảng trạng thái drone, cập nhật ~5 lần/giây. Dùng được cho:
  - pcap phát lại đúng nhịp thời gian thật:
        python examples/monitor.py captures/cap_09_flight_indoor.pcap
  - drone thật (khi đã kết nối cùng mạng):
        python examples/monitor.py udp

Nhấn Ctrl+C để thoát.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neo2sdk import MSDKManager
from neo2sdk.keys import BatteryKey, FlightControllerKey, GimbalKey
from neo2sdk.transport.source import PcapSource

FLYC_STATE = {
    0: "Manual", 6: "Trên đất / chờ", 43: "Đang bay (GPS/định vị)",
}


def fmt(v, f):
    return f(v) if v is not None else "—"


def render(km, stats):
    bat = km.get_value(BatteryKey.Info)
    att = km.get_value(FlightControllerKey.Attitude)
    alt = km.get_value(FlightControllerKey.Altitude)
    vel = km.get_value(FlightControllerKey.Velocity)
    st = km.get_value(FlightControllerKey.FlightState)
    gim = km.get_value(GimbalKey.Attitude)

    lines = [
        "┌─ DJI Neo 2 — Telemetry (neo2sdk) ───────────────────────────┐",
        f"│ Pin     : {fmt(bat, lambda b: f'{b.percent:3d}%  {b.voltage_mv/1000:.2f}V  {b.current_ma:+5d}mA  {b.cells}S'):50s}│",
        f"│ Tư thế  : {fmt(att, lambda a: f'pitch {a.pitch:+6.1f}°  roll {a.roll:+6.1f}°  yaw {a.yaw:+6.1f}°'):50s}│",
        f"│ Độ cao  : {fmt(alt, lambda h: f'{h:+.1f} m'):50s}│",
        f"│ Vận tốc : {fmt(vel, lambda v: f'x {v.x:+.1f}  y {v.y:+.1f}  z {v.z:+.1f} m/s (NED)'):50s}│",
        f"│ Gimbal  : {fmt(gim, lambda g: f'pitch {g.pitch:+6.1f}°'):50s}│",
        f"│ Trạng thái: {fmt(st, lambda s: f'{s} ({FLYC_STATE.get(s, 'chế độ ' + str(s))})'):48s}│",
        "├─────────────────────────────────────────────────────────────┤",
        f"│ gói {stats['packets']:>7d}  telemetry {stats['telemetry_updates']:>7d}  video {stats['video_packets']:>7d}      │",
        "└─────────────────────────────────────────────────────────────┘",
    ]
    sys.stdout.write("\033[H\033[J" + "\n".join(lines) + "\n")
    sys.stdout.flush()


def main(source):
    sdk = MSDKManager()
    if source == "udp":
        sdk.connect("udp")
    else:
        sdk.connect(PcapSource(source, realtime=True))   # phát đúng nhịp thời gian
    sdk.start(background=True)
    try:
        while sdk._running or sdk.stats["packets"] == 0:
            render(sdk.key_manager, sdk.stats)
            time.sleep(0.2)
        render(sdk.key_manager, sdk.stats)
        print("\n(Hết pcap.)")
    except KeyboardInterrupt:
        sdk.stop()
        print("\nĐã thoát.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "captures/cap_09_flight_indoor.pcap")
