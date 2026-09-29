"""Trích luồng H.265 từ kênh video (byte6 = 0x02) cổng 9003 ra file Annex-B.

Mỗi gói kênh video = header 20 byte + dữ liệu H.265; ghép liền payload[20:] theo thứ tự đến.
Drone chỉ gửi VPS/SPS/PPS + IDR khi mở phiên / nối lại, sau đó không có keyframe định kỳ.
Capture bắt giữa phiên (vd. cap_04) sẽ không có bộ tham số — dùng --params để mượn từ một file
.h265 khác (cùng cấu hình camera), và giải mã với ffmpeg -flags2 +showall (ảnh xám lúc đầu,
rõ dần sau vài trăm khung).

Dùng:
  python poc/extract_video.py captures/cap_01_connect.pcap captures/cap_01.h265
  python poc/extract_video.py captures/cap_04_battery_drain.pcap captures/cap_04.h265 \
      --params captures/cap_01.h265
  ffmpeg -flags2 +showall -err_detect ignore_err -i captures/cap_04.h265 out.mp4
"""
import argparse
import re
import struct

from duml_survey import ip_udp
from find_battery_field import read_pcap

VIDEO_HDR = 20
START = b"\x00\x00\x00\x01"


def param_sets(path):
    """VPS/SPS/PPS (NAL 32/33/34) đầu tiên trong một file Annex-B."""
    data = open(path, "rb").read()
    starts = [m.start() for m in re.finditer(b"\x00\x00\x00\x01", data)] + [len(data)]
    got = {}
    for a, b in zip(starts, starts[1:]):
        t = (data[a + 4] >> 1) & 0x3F
        if t in (32, 33, 34) and t not in got:
            got[t] = data[a:b]
        if len(got) == 3:
            break
    if len(got) < 3:
        raise SystemExit(f"{path}: không đủ VPS/SPS/PPS")
    return got[32] + got[33] + got[34]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pcap")
    ap.add_argument("out")
    ap.add_argument("--params", help="file .h265 để mượn VPS/SPS/PPS")
    a = ap.parse_args()

    out = open(a.out, "wb")
    if a.params:
        out.write(param_sets(a.params))
    started, last, gaps, pkts = False, None, 0, 0
    for _, frame in read_pcap(a.pcap):
        r = ip_udp(frame)
        if not (r and r[0] and len(r[1]) > VIDEO_HDR and r[1][6] == 0x02):
            continue
        p = r[1]
        seq = struct.unpack("<H", p[4:6])[0]
        if last is not None and (seq - last) % 65536 != 8:
            gaps += 1
        last = seq
        # bỏ phần khung dở dang ở đầu capture: bắt đầu tại gói đầu tiên mở NAL mới
        if not started:
            if not p[VIDEO_HDR:].startswith(START):
                continue
            started = True
        out.write(p[VIDEO_HDR:])
        pkts += 1
    out.close()
    print(f"{pkts} gói video → {a.out}, {gaps} chỗ nhảy seq (mất gói / nối lại)")


if __name__ == "__main__":
    main()
