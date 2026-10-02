"""Bộ giải mã telemetry DJI Neo 2 (giao thức UDP cổng 9003).

Thư viện độc lập (chỉ dùng thư viện chuẩn Python), giải mã gói thành các sự kiện
telemetry có tên. Nền tảng cho SDK Phase 1 "đọc telemetry".

Dùng được cho hai nguồn:
  - File pcap đã bắt (offline, để phát triển/kiểm thử):
        for ts, payload in iter_pcap("captures/cap_08_attitude.pcap"):
            for ev in decode_udp_payload(payload):
                print(ts, ev)
  - UDP trực tiếp (khi chạy trên điện thoại / máy nối cùng mạng drone):
        sock.recvfrom(2048) -> decode_udp_payload(data)

Các trường đã xác định thực nghiệm (xem notes/capture-log.md, Ngày 3-5):
  - Battery       : % pin                          (0x0b->0x02 set 0x0d id 0x02, payload[20])
  - GimbalAttitude: pitch gimbal + quaternion       (0x04->0x02 set 0x04 id 0x05)
  - DroneState    : pitch/roll/yaw thân drone + ... (0x03 set 0x03 id 0x43, OSD chuẩn DJI)
  - KeyframeRequest: app xin I-frame                (0x02->0x09 set 0x01 id 0x01, payload[5] bit 0x20)

Các trường trong DroneState (độ cao, vận tốc, trạng thái bay) lấy theo LAYOUT OSD CHUẨN DJI
(frame 0x03/0x43 của Neo 2 trùng cấu trúc flyc_osd_general). Đã xác nhận pitch/roll/yaw trên
cap_08; các trường còn lại suy từ chuẩn, CHƯA kiểm chứng khi bay — đánh dấu (chưa kiểm chứng).

CLI:  python poc/neo2_telemetry.py captures/cap_08_attitude.pcap [--only battery,drone_attitude]
"""
from __future__ import annotations

import math
import struct
import sys
from dataclasses import dataclass

DUML_PORT = 9003
OUTER_MIN = 16          # header chung tối thiểu
CH_DUML_DRONE = 0x01    # loại kênh (byte 6)
CH_VIDEO = 0x02
CH_DUML_APP = 0x04


# ---------------------------------------------------------------------------
# CRC của DUML v1 (để nhận diện biên frame một cách tin cậy)
# ---------------------------------------------------------------------------
def _mk_table(poly):
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (c >> 1) ^ poly if c & 1 else c >> 1
        table.append(c)
    return table


_T8 = _mk_table(0x8C)
_T16 = _mk_table(0x8408)


def crc8(data, crc=0x77):
    for b in data:
        crc = _T8[(crc ^ b) & 0xFF]
    return crc


def crc16(data, crc=0x3692):
    for b in data:
        crc = (crc >> 8) ^ _T16[(crc ^ b) & 0xFF]
    return crc


# ---------------------------------------------------------------------------
# Các sự kiện telemetry
# ---------------------------------------------------------------------------
@dataclass
class Battery:
    percent: int              # state of charge (%)
    voltage_mv: int           # điện áp cả pack (mV)
    current_ma: int           # dòng (mA); âm = đang xả
    remain_mah: int           # dung lượng còn lại (mAh)
    full_mah: int             # dung lượng sạc đầy (mAh)
    cells: int                # số cell nối tiếp (Neo 2: 2)
    temp_raw: int             # nhiệt độ thô (≈ 0.1°C, chưa chốt đơn vị)

    def __str__(self):
        return (f"Battery        {self.percent:3d}%  {self.voltage_mv/1000:.3f}V "
                f"{self.current_ma:+5d}mA  {self.remain_mah}/{self.full_mah}mAh "
                f"{self.cells}S  {self.temp_raw/10:.1f}°C")


@dataclass
class GimbalAttitude:
    pitch_deg: float          # góc nghiêng camera (độ); âm = chúc xuống
    quat: tuple               # (w, x, y, z) hướng camera

    def __str__(self):
        return f"GimbalAttitude pitch={self.pitch_deg:+6.1f}°"


@dataclass
class DroneState:
    """Trích theo layout OSD General chuẩn DJI (frame 0x03/0x43).

    pitch/roll/yaw đã kiểm chứng trên cap_08. Các trường dưới đây suy từ layout
    chuẩn, CHƯA kiểm chứng khi bay — chỉ hiển thị để sớm dùng, cần xác nhận lại.
    """
    pitch_deg: float
    roll_deg: float
    yaw_deg: float
    relative_height_m: float  # (chưa kiểm chứng) độ cao so với điểm cất cánh
    vgx_ms: float             # (chưa kiểm chứng) vận tốc theo trục X (m/s)
    vgy_ms: float             # (chưa kiểm chứng)
    vgz_ms: float             # (chưa kiểm chứng)

    def __str__(self):
        return (f"DroneState     pitch={self.pitch_deg:+6.1f}° roll={self.roll_deg:+6.1f}° "
                f"yaw={self.yaw_deg:+6.1f}°  h={self.relative_height_m:+.1f}m? "
                f"v=({self.vgx_ms:+.1f},{self.vgy_ms:+.1f},{self.vgz_ms:+.1f})m/s?")


@dataclass
class KeyframeRequest:
    requested: bool           # True = cờ "xin ngay" bật

    def __str__(self):
        return f"KeyframeReq    {'XIN I-FRAME' if self.requested else '(duy trì)'}"


# ---------------------------------------------------------------------------
# Giải mã một frame DUML đã tách -> sự kiện (hoặc None nếu chưa biết)
# ---------------------------------------------------------------------------
def _i16(buf, off):
    return struct.unpack_from("<h", buf, off)[0]


def _quat_pitch(w, x, y, z):
    """Góc pitch (độ) từ quaternion; kẹp để tránh lỗi số học."""
    sinp = max(-1.0, min(1.0, 2 * (w * y - z * x)))
    return math.degrees(math.asin(sinp))


def decode_frame(src, dst, cmd_set, cmd_id, payload):
    # Pin: module pin -> app (Battery Dynamic Data, layout chuẩn DJI + 1 byte đầu).
    # Kiểm chứng trên cap_04 (23 phút x, mọi trường nhất quán). Xem notes/capture-log.md.
    if src == 0x0B and cmd_set == 0x0D and cmd_id == 0x02 and len(payload) >= 30:
        voltage = struct.unpack_from("<I", payload, 1)[0]
        current = struct.unpack_from("<i", payload, 5)[0]
        full = struct.unpack_from("<I", payload, 9)[0]
        remain = struct.unpack_from("<I", payload, 13)[0]
        temp = struct.unpack_from("<H", payload, 17)[0]
        cells = payload[19]
        soc = payload[20]
        return Battery(soc, voltage, current, remain, full, cells, temp)

    # Gimbal: gimbal -> app
    if src == 0x04 and cmd_set == 0x04 and cmd_id == 0x05 and len(payload) >= 40:
        pitch = _i16(payload, 0) / 10.0           # pitch 0.1° (trường chính)
        quat = struct.unpack_from("<ffff", payload, 24)  # hướng camera đầy đủ
        return GimbalAttitude(pitch, quat)

    # Hướng drone: FC OSD General (layout chuẩn DJI)
    if cmd_set == 0x03 and cmd_id == 0x43 and len(payload) >= 30:
        pitch = _i16(payload, 24) / 10.0
        roll = _i16(payload, 26) / 10.0
        yaw = _i16(payload, 28) / 10.0
        height = _i16(payload, 16) / 10.0
        vgx = _i16(payload, 18) / 10.0
        vgy = _i16(payload, 20) / 10.0
        vgz = _i16(payload, 22) / 10.0
        return DroneState(pitch, roll, yaw, height, vgx, vgy, vgz)

    # App xin keyframe
    if src == 0x02 and dst == 0x09 and cmd_set == 0x01 and cmd_id == 0x01 and len(payload) > 5:
        return KeyframeRequest(bool(payload[5] & 0x20))

    return None


# ---------------------------------------------------------------------------
# Tách frame DUML (kể cả frame lồng trong tunnel 0x51/0x01) từ 1 buffer
# ---------------------------------------------------------------------------
def _walk_frames(buf, start, depth=0):
    """Sinh (src, dst, cmd_set, cmd_id, payload) cho mọi frame hợp lệ."""
    i = buf.find(b"\x55", start)
    while i != -1 and i + 13 <= len(buf):
        if crc8(buf[i:i + 3]) == buf[i + 3]:
            length = struct.unpack_from("<H", buf, i + 1)[0] & 0x03FF
            if length >= 13 and i + length <= len(buf) and \
                    crc16(buf[i:i + length - 2]) == struct.unpack_from("<H", buf, i + length - 2)[0]:
                src, dst = buf[i + 4], buf[i + 5]
                cmd_set, cmd_id = buf[i + 9], buf[i + 10]
                payload = buf[i + 11:i + length - 2]
                yield src, dst, cmd_set, cmd_id, payload
                # tunnel: payload chứa frame lồng
                if cmd_set == 0x51 and cmd_id == 0x01 and depth < 4:
                    yield from _walk_frames(payload, 0, depth + 1)
                i += length
                continue
        i = buf.find(b"\x55", i + 1)


def decode_udp_payload(payload):
    """Giải mã payload UDP của một gói cổng 9003 -> danh sách sự kiện telemetry.

    Dùng cho cả gói đọc từ pcap lẫn gói nhận trực tiếp qua socket UDP.
    """
    events = []
    if len(payload) < OUTER_MIN:
        return events
    b0 = struct.unpack_from("<H", payload, 0)[0]
    if (b0 & 0x8000) == 0 or (b0 & 0x7FFF) != len(payload):
        return events  # không phải gói Neo 2 hợp lệ
    channel = payload[6]
    if channel not in (CH_DUML_DRONE, CH_DUML_APP):
        return events  # kênh video / handshake: không có telemetry DUML
    for src, dst, cs, ci, pl in _walk_frames(payload, 34):
        ev = decode_frame(src, dst, cs, ci, pl)
        if ev is not None:
            events.append(ev)
    return events


# ---------------------------------------------------------------------------
# Đọc pcap (stdlib) — chỉ Ethernet + IPv4 + UDP cổng 9003
# ---------------------------------------------------------------------------
def iter_pcap(path):
    """Sinh (timestamp, udp_payload) cho từng gói cổng 9003 trong file pcap."""
    with open(path, "rb") as f:
        gh = f.read(24)
        magic = struct.unpack_from("<I", gh, 0)[0]
        if magic == 0xA1B2C3D4:
            div = 1e6
        elif magic == 0xA1B23C4D:
            div = 1e9
        else:
            raise ValueError(f"pcap magic không hỗ trợ: {magic:#x}")
        if struct.unpack_from("<I", gh, 20)[0] != 1:
            raise ValueError("chỉ hỗ trợ linktype Ethernet (1)")
        rec = struct.Struct("<IIII")
        while True:
            h = f.read(16)
            if len(h) < 16:
                return
            sec, frac, incl, _ = rec.unpack(h)
            frame = f.read(incl)
            if len(frame) < 42 or frame[12:14] != b"\x08\x00" or frame[23] != 17:
                continue
            u = 14 + (frame[14] & 0x0F) * 4
            sport, dport = struct.unpack_from(">HH", frame, u)
            if DUML_PORT not in (sport, dport):
                continue
            yield sec + frac / div, frame[u + 8:]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv):
    if not argv:
        print(__doc__)
        return
    path = argv[0]
    only = None
    if "--only" in argv:
        only = set(argv[argv.index("--only") + 1].split(","))
    kind = {"Battery": "battery", "GimbalAttitude": "gimbal",
            "DroneState": "drone_state", "KeyframeRequest": "keyframe"}
    from datetime import datetime
    counts = {}
    last_print = {}
    for ts, payload in iter_pcap(path):
        for ev in decode_udp_payload(payload):
            name = type(ev).__name__
            counts[name] = counts.get(name, 0) + 1
            if only and kind.get(name) not in only:
                continue
            # giảm nhiễu: in tối đa ~2 lần/giây cho mỗi loại
            if ts - last_print.get(name, 0) < 0.5:
                continue
            last_print[name] = ts
            tstr = datetime.fromtimestamp(ts).strftime("%H:%M:%S.%f")[:-3]
            print(f"{tstr}  {ev}")
    print("\n--- tổng số sự kiện giải mã được ---")
    for name, c in sorted(counts.items()):
        print(f"  {name:16s} {c}")


if __name__ == "__main__":
    main(sys.argv[1:])
