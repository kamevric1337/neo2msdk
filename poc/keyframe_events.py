"""Liệt kê theo thời gian: VPS/keyframe trên kênh video và các lệnh nghi là "xin keyframe".

Lệnh theo dõi: 0x02->0xe9 set 0x18 id 0x47 và 0x02->0x09 set 0x01 id 0x01 (cùng seq DUML),
cùng ACK 0x09->0x02 set 0x01 id 0x01. Xem notes/capture-log.md, mục cap_05.

Dùng: python poc/keyframe_events.py captures/cap_05_keyframe.pcap
"""
import sys
from datetime import datetime

from duml_survey import ip_udp, scan
from find_battery_field import TZ, read_pcap

VPS = b"\x00\x00\x00\x01\x40\x01"
WATCH = {(0x02, 0xe9, 0x18, 0x47), (0x02, 0x09, 0x01, 0x01), (0x09, 0x02, 0x01, 0x01)}


def main(path):
    last_vps = None
    for t, frame in read_pcap(path):
        r = ip_udp(frame)
        if r is None:
            continue
        from_drone, p = r
        ts = datetime.fromtimestamp(t, TZ).strftime("%H:%M:%S.%f")[:-3]
        if from_drone and p[6] == 0x02 and VPS in p[20:]:
            if last_vps is None or t - last_vps > 1:
                print(f"{ts}  ===== VPS/keyframe =====")
            last_vps = t
        for off, n, src, dst, cset, cid in scan(p):
            if (src, dst, cset, cid) in WATCH:
                f = p[off:off + n]
                print(f"{ts}  {src:#04x}->{dst:#04x} set={cset:#04x} id={cid:#04x} "
                      f"attr={f[8]:#04x} seq={f[6] | f[7] << 8:#06x}  {f[11:-2].hex(' ')}")


if __name__ == "__main__":
    main(sys.argv[1])
