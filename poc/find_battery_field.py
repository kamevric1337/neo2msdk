"""Tìm byte chứa % pin trong các frame DUML trên cổng UDP 9003.

Đọc pcap (chỉ dùng stdlib, stream được file lớn), quét mọi frame DUML v1 hợp lệ
(kiểm CRC8 + CRC16, kể cả frame lồng trong tunnel 0x51/0x01), rồi theo dõi giá trị từng byte của payload
theo khóa (src, dst, cmd_set, cmd_id, offset). In ra những khóa có chuyển
giá trị khớp với các mốc pin đã ghi trong notes/capture-log.md.

Dùng: python poc/find_battery_field.py captures/cap_04_battery_drain.pcap
"""
import struct
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

OUTER_HDR = 34
DUML_PORT = 9003
TZ = timezone(timedelta(hours=7))  # giờ điện thoại (+07)

# Mốc chính xác (giờ điện thoại) và giá trị (trước, sau). Cửa sổ chấp nhận:
# tối đa LEAD giây trước tin nhắn (thời gian gõ + độ trễ adb), SLACK sau.
PRECISE_MARKS = [
    ("13:38:22", 64, 63),
    ("13:39:53", 63, 62),
]
LEAD, SLACK = 30, 5


def ts_of(hms):
    h, m, s = map(int, hms.split(":"))
    return datetime(2026, 9, 29, h, m, s, tzinfo=TZ).timestamp()


def read_pcap(path):
    with open(path, "rb") as f:
        gh = f.read(24)
        magic = struct.unpack("<I", gh[:4])[0]
        if magic == 0xA1B2C3D4:
            endian, div = "<", 1e6
        elif magic == 0xA1B23C4D:
            endian, div = "<", 1e9
        else:
            raise ValueError(f"pcap magic không hỗ trợ: {magic:#x}")
        linktype = struct.unpack(endian + "I", gh[20:24])[0]
        if linktype != 1:
            raise ValueError(f"linktype {linktype}, chỉ hỗ trợ Ethernet (1)")
        rec = struct.Struct(endian + "IIII")
        while True:
            h = f.read(16)
            if len(h) < 16:
                return
            sec, frac, incl, _ = rec.unpack(h)
            yield sec + frac / div, f.read(incl)


def udp_payload(frame):
    if len(frame) < 42 or frame[12:14] != b"\x08\x00":
        return None
    ihl = (frame[14] & 0x0F) * 4
    if frame[23] != 17:
        return None
    u = 14 + ihl
    sport, dport = struct.unpack(">HH", frame[u:u + 4])
    if DUML_PORT not in (sport, dport):
        return None
    return frame[u + 8:]


def _table(poly):
    t = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ poly if c & 1 else c >> 1
        t.append(c)
    return t


_T8, _T16 = _table(0x8C), _table(0x8408)


def crc8(b, c=0x77):
    for x in b:
        c = _T8[(c ^ x) & 0xFF]
    return c


def crc16(b, c=0x3692):
    for x in b:
        c = (c >> 8) ^ _T16[(c ^ x) & 0xFF]
    return c


def duml_frames(buf):
    """Mọi frame DUML v1 hợp lệ (qua CRC8 header và CRC16) ở bất kỳ offset nào.

    Quét toàn bộ buffer thay vì nối tiếp từ sau header 34 byte, vì frame
    cmd_set 0x51/cmd_id 0x01 là tunnel chứa các frame DUML khác bên trong
    payload, và frame không phải lúc nào cũng liền nhau.
    """
    i = buf.find(b"U")
    while i != -1 and i + 13 <= len(buf):
        if crc8(buf[i:i + 3]) == buf[i + 3]:
            length = struct.unpack("<H", buf[i + 1:i + 3])[0] & 0x03FF
            if length >= 13 and i + length <= len(buf):
                f = buf[i:i + length]
                if crc16(f[:-2]) == struct.unpack("<H", f[-2:])[0]:
                    # src, dst, cmd_set, cmd_id, payload (bỏ 11 byte đầu và CRC16)
                    yield f[4], f[5], f[9], f[10], f[11:-2]
        i = buf.find(b"U", i + 1)


def main(path):
    # khóa -> (giá trị hiện tại, danh sách chuyển (t, cũ, mới))
    last = {}
    trans = defaultdict(list)
    n_pkts = n_frames = 0
    for t, frame in read_pcap(path):
        p = udp_payload(frame)
        if p is None or len(p) <= OUTER_HDR:
            continue
        n_pkts += 1  # gói có thể chứa DUML (chưa chắc có)
        for src, dst, cset, cid, pl in duml_frames(p):
            n_frames += 1
            for off, v in enumerate(pl):
                k = (src, dst, cset, cid, len(pl), off)
                old = last.get(k)
                if old != v:
                    if old is not None:
                        trans[k].append((t, old, v))
                    last[k] = v

    print(f"{n_pkts} gói có DUML, {n_frames} frame DUML, {len(last)} khóa byte")

    hits = []
    for k, tl in trans.items():
        ok = 0
        for hms, a, b in PRECISE_MARKS:
            m = ts_of(hms)
            if any(m - LEAD <= t <= m + SLACK and o == a and n == b for t, o, n in tl):
                ok += 1
        if ok:
            hits.append((ok, k, tl))

    hits.sort(key=lambda h: (-h[0], len(h[2])))
    for ok, (src, dst, cset, cid, plen, off), tl in hits[:20]:
        vals = [tl[0][1]] + [n for _, _, n in tl]
        print(f"\nkhớp {ok}/{len(PRECISE_MARKS)} mốc  src={src:#04x} dst={dst:#04x} "
              f"cmd_set={cset:#04x} cmd_id={cid:#04x} payload[{off}]/{plen}  "
              f"{len(tl)} lần đổi, giá trị {vals[0]}→{vals[-1]}")
        if len(tl) <= 40:
            for t, o, n in tl:
                ts = datetime.fromtimestamp(t, TZ).strftime("%H:%M:%S.%f")[:-3]
                print(f"    {ts}  {o:3d} → {n:3d}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "captures/cap_04_battery_drain.pcap")
