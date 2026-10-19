"""Ghi telemetry ra CSV để phân tích (vẽ đồ thị, đối chiếu thí nghiệm).

    python examples/log_csv.py captures/cap_09_flight_indoor.pcap flight.csv

Mỗi lần OSD General tới (≈10 Hz) ghi một dòng: thời gian + tư thế + độ cao +
vận tốc + trạng thái bay. Mở bằng Excel / pandas để vẽ.
"""
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neo2sdk.core.telemetry import decode as decode_telemetry
from neo2sdk.keys import BatteryKey, FlightControllerKey
from neo2sdk.transport.duml import iter_frames
from neo2sdk.transport.framing import CH_DUML_APP, CH_DUML_DRONE, parse_outer
from neo2sdk.transport.source import PcapSource

COLS = ["t", "pitch", "roll", "yaw", "alt_m", "vz_ms", "in_air", "motors_on",
        "sats", "flyc_state", "battery_pct"]


def main(pcap, out):
    last = {"battery_pct": ""}
    n = 0
    with open(out, "w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(COLS)
        t0 = None
        for ts, payload in PcapSource(pcap):
            o = parse_outer(payload)
            if o is None or o.channel not in (CH_DUML_DRONE, CH_DUML_APP):
                continue
            t0 = ts if t0 is None else t0
            for fr in iter_frames(o.body, 18):
                u = dict(decode_telemetry(fr))
                if BatteryKey.PercentRemaining in u:
                    last["battery_pct"] = u[BatteryKey.PercentRemaining]
                att = u.get(FlightControllerKey.Attitude)
                if att is None:
                    continue
                vel = u[FlightControllerKey.Velocity]
                stt = u.get(FlightControllerKey.Status)
                w.writerow([f"{ts - t0:.2f}", att.pitch, att.roll, att.yaw,
                            u[FlightControllerKey.Altitude], vel.z,
                            int(stt.in_air) if stt else "", int(stt.motors_on) if stt else "",
                            stt.satellites if stt else "", u[FlightControllerKey.FlightState],
                            last["battery_pct"]])
                n += 1
    print(f"Ghi {n} dòng OSD -> {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "captures/cap_09_flight_indoor.pcap",
         sys.argv[2] if len(sys.argv) > 2 else "flight.csv")
