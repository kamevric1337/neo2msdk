"""Khảo sát cấu trúc gói UDP 9003: header ngoài 34 byte + frame DUML (kiểm CRC).

In ra:
  - số gói theo chiều / cỡ, tỉ lệ gói mà frame DUML cấp ngoài phủ kín [34:]
  - bảng lệnh DUML, tách frame cấp ngoài và frame lồng (nằm trong payload frame khác)
  - thống kê từng trường u16 LE của header 34 byte theo chiều gửi
  - các khoảng gián đoạn traffic > 2s và lệnh DUML đầu tiên sau mỗi khoảng

Dùng: python poc/duml_survey.py captures/cap_02_idle_30s.pcap [...]
"""
import struct
import sys
from collections import Counter, defaultdict

from find_battery_field import DUML_PORT, OUTER_HDR, crc8, crc16, read_pcap

DRONE_IP = bytes([192, 168, 2, 1])
GAP = 2.0


def ip_udp(frame):
    """(từ drone?, payload UDP) cho gói cổng 9003, không thì None."""
    if len(frame) < 42 or frame[12:14] != b"\x08\x00" or frame[23] != 17:
        return None
    u = 14 + (frame[14] & 0x0F) * 4
    sport, dport = struct.unpack(">HH", frame[u:u + 4])
    if DUML_PORT not in (sport, dport):
        return None
    return frame[26:30] == DRONE_IP, frame[u + 8:]


def scan(buf):
    """Mọi frame DUML hợp lệ: (offset, độ dài, src, dst, cmd_set, cmd_id)."""
    out = []
    i = buf.find(b"\x55")
    while i != -1 and i + 13 <= len(buf):
        if crc8(buf[i:i + 3]) == buf[i + 3]:
            n = struct.unpack("<H", buf[i + 1:i + 3])[0] & 0x03FF
            if n >= 13 and i + n <= len(buf) and \
                    crc16(buf[i:i + n - 2]) == struct.unpack("<H", buf[i + n - 2:i + n])[0]:
                out.append((i, n, buf[i + 4], buf[i + 5], buf[i + 9], buf[i + 10]))
        i = buf.find(b"\x55", i + 1)
    return out


def split_levels(frames):
    """Tách frame cấp ngoài (không nằm trong span frame hợp lệ nào khác) và frame lồng."""
    top, nested, end = [], [], -1
    for f in frames:
        (nested if f[0] < end else top).append(f)
        end = max(end, f[0] + f[1])
    return top, nested


def tiling(buf, top):
    """'kín' nếu frame cấp ngoài nối liền từ OUTER_HDR tới hết buffer."""
    if not top:
        return "không frame" if len(buf) > OUTER_HDR else "chỉ header"
    pos = OUTER_HDR
    for off, n, *_ in top:
        if off != pos:
            return "hở/lệch"
        pos += n
    return "kín" if pos == len(buf) else "dư đuôi"


def fmt_cmd(k):
    return f"{k[0]:#04x}→{k[1]:#04x} set={k[2]:#04x} id={k[3]:#04x}"


def survey(path):
    print(f"\n{'=' * 78}\n{path}\n{'=' * 78}")
    pk = Counter()
    tile = defaultdict(Counter)
    cmd_top, cmd_nest = Counter(), Counter()
    big_top = Counter()
    fields = defaultdict(lambda: defaultdict(list))  # chiều -> offset -> [(t, giá trị)]
    len_match = defaultdict(Counter)
    gaps, last_t, first_t = [], None, None
    after_gap = None

    for t, frame in read_pcap(path):
        r = ip_udp(frame)
        if r is None:
            continue
        from_drone, p = r
        d = "drone→app" if from_drone else "app→drone"
        size = "lớn" if len(p) >= 1000 else "nhỏ"
        pk[(d, size)] += 1
        first_t = first_t or t
        if last_t is not None and t - last_t > GAP:
            after_gap = {"start": last_t, "end": t, "cmds": []}
            gaps.append(after_gap)
        last_t = t

        if len(p) >= OUTER_HDR:
            for off in range(0, OUTER_HDR, 2):
                fields[d][off].append((t, struct.unpack("<H", p[off:off + 2])[0]))
            len_match[d][struct.unpack("<H", p[32:34])[0] == len(p) - OUTER_HDR] += 1

        top, nested = split_levels(scan(p))
        tile[(d, size)][tiling(p, top)] += 1
        for f in top:
            cmd_top[(d,) + f[2:]] += 1
            if size == "lớn":
                big_top[(f[2:], f[1])] += 1
        for f in nested:
            cmd_nest[(d,) + f[2:]] += 1
        if after_gap is not None and len(after_gap["cmds"]) < 25:
            for f in top + nested:
                after_gap["cmds"].append((t - after_gap["end"], d, f[2:]))

    print(f"thời lượng {last_t - first_t:.1f}s")
    print("\n[1] gói theo chiều/cỡ và độ phủ frame cấp ngoài trên [34:]")
    for k in sorted(pk):
        print(f"  {k[0]:10s} {k[1]:4s} {pk[k]:7d} gói   {dict(tile[k].most_common())}")

    print("\n[2] frame cấp ngoài trong gói lớn (lệnh, độ dài frame) — top 8")
    for (c, n), cnt in big_top.most_common(8):
        print(f"  {fmt_cmd(c)}  len={n:4d}  {cnt}")

    print("\n[3] lệnh DUML cấp ngoài — top 12")
    for k, c in cmd_top.most_common(12):
        print(f"  {k[0]:10s} {fmt_cmd(k[1:])}  {c}")
    print("    lệnh DUML lồng — top 20")
    for k, c in cmd_nest.most_common(20):
        print(f"  {k[0]:10s} {fmt_cmd(k[1:])}  {c}")

    print("\n[4] header 34 byte: từng u16 LE theo chiều gửi")
    print("    (số giá trị khác nhau, min..max, % bước tăng so với gói trước, % bước = +1)")
    for d in sorted(fields):
        print(f"  {d}:  byte[32:34] == len(payload)-34 ở {len_match[d][True]}/"
              f"{sum(len_match[d].values())} gói")
        for off in sorted(fields[d]):
            vals = [v for _, v in fields[d][off]]
            steps = [b - a for a, b in zip(vals, vals[1:])]
            inc = sum(s > 0 for s in steps) / max(len(steps), 1)
            one = sum(s == 1 for s in steps) / max(len(steps), 1)
            distinct = len(set(vals))
            desc = f"{vals[0]:#06x}" if distinct == 1 else f"{min(vals):#06x}..{max(vals):#06x}"
            print(f"    [{off:2d}:{off + 2:2d}] {distinct:6d} giá trị  {desc:15s} "
                  f"tăng {inc:5.1%}  +1 {one:5.1%}")

    print(f"\n[5] gián đoạn > {GAP}s")
    if not gaps:
        print("  không có")
    for g in gaps:
        print(f"  {g['start'] - first_t:.2f}s → {g['end'] - first_t:.2f}s "
              f"({g['end'] - g['start']:.1f}s). Frame DUML đầu tiên sau đó:")
        for dt, d, c in g["cmds"]:
            print(f"    +{dt:6.3f}s {d:10s} {fmt_cmd(c)}")


if __name__ == "__main__":
    for path in sys.argv[1:] or ["captures/cap_02_idle_30s.pcap", "captures/cap_01_connect.pcap"]:
        survey(path)
