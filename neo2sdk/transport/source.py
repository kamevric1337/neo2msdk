"""Tầng Transport — nguồn gói: PcapSource (offline, để dev/test) và UdpSource (live).

Cả hai sinh (timestamp, udp_payload). Nhờ tách nguồn, toàn bộ SDK phía trên
chạy y hệt dù đọc từ file đã bắt hay từ drone thật — chỉ đổi dòng connect().
"""
from __future__ import annotations

import socket
import struct
import time

from .framing import DUML_PORT


class PcapSource:
    """Đọc gói UDP 9003 từ file pcap (Ethernet/IPv4/UDP). Dùng để phát triển offline."""

    def __init__(self, path: str, realtime: bool = False):
        self.path = path
        self.realtime = realtime  # True = mô phỏng đúng nhịp thời gian thật

    def __iter__(self):
        with open(self.path, "rb") as f:
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
            t0 = None
            wall0 = time.time()
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
                ts = sec + frac / div
                if self.realtime:
                    t0 = ts if t0 is None else t0
                    delay = (ts - t0) - (time.time() - wall0)
                    if delay > 0:
                        time.sleep(delay)
                yield ts, frame[u + 8:]


class UdpSource:
    """Nhận gói UDP 9003 trực tiếp khi máy ở cùng mạng drone (192.168.2.x).

    Lắng nghe cổng cục bộ mà app dùng để nói chuyện với drone. Lưu ý: muốn nhận
    được, máy phải nằm trên đường đi của gói (bắt trên chính điện thoại, hoặc
    làm proxy). Trên PC thường chỉ bắt được nếu định tuyến/giả lập phù hợp —
    giai đoạn PoC chủ yếu dùng PcapSource; UdpSource để dành khi tích hợp thật.
    """

    DRONE_ADDR = ("192.168.2.1", DUML_PORT)

    def __init__(self, bind_host: str = "0.0.0.0", bind_port: int = DUML_PORT):
        self.bind_host = bind_host
        self.bind_port = bind_port
        self._sock = None

    def __iter__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.bind_host, self.bind_port))
        try:
            while True:
                data, _addr = self._sock.recvfrom(4096)
                yield time.time(), data
        finally:
            self._sock.close()

    def send(self, packet: bytes):
        """Gửi một gói tới drone (dùng cho đường điều khiển khi đã kết nối live)."""
        if self._sock is None:
            raise RuntimeError("UdpSource chưa mở socket (phải start() trước).")
        self._sock.sendto(packet, self.DRONE_ADDR)

    def close(self):
        if self._sock:
            self._sock.close()
