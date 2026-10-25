"""Nguồn gói LIVE qua adb: chạy tcpdump trên điện thoại, stream pcap về PC.

Vì PC không nằm trên đường đi điện thoại↔drone, ta bắt ngay trên điện thoại (root)
và đẩy pcap qua `adb exec-out` về, parse luồng pcap tại chỗ.

    from neo2sdk import MSDKManager
    from neo2sdk.transport.adb_source import AdbTcpdumpSource
    sdk = MSDKManager().connect(AdbTcpdumpSource())
    sdk.start(background=True)

Yêu cầu: adb thấy máy, điện thoại đã root, tcpdump có sẵn (đã kiểm ở Ngày 2).
"""
from __future__ import annotations

import struct
import subprocess

from .framing import DUML_PORT


class AdbTcpdumpSource:
    """Lặp ra (timestamp, udp_payload) từ tcpdump chạy trên điện thoại qua adb."""

    def __init__(self, iface: str = "wlan0", adb: str = "adb"):
        self.iface = iface
        self.adb = adb
        self._proc = None

    def __iter__(self):
        # -U: flush mỗi gói (độ trễ thấp); -w -: ghi pcap ra stdout; lọc cổng 9003
        cmd = [self.adb, "exec-out",
               f"su -c 'tcpdump -i {self.iface} -s 0 -U -w - port {DUML_PORT} 2>/dev/null'"]
        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=0)
        f = self._proc.stdout

        gh = _read_exact(f, 24)
        if gh is None:
            return
        magic = struct.unpack_from("<I", gh, 0)[0]
        if magic == 0xA1B2C3D4:
            le, div = "<", 1e6
        elif magic == 0xA1B23C4D:
            le, div = "<", 1e9
        elif magic == 0xD4C3B2A1:
            le, div = ">", 1e6
        else:
            raise ValueError(f"pcap magic lạ: {magic:#x}")
        rec = struct.Struct(le + "IIII")
        try:
            while True:
                h = _read_exact(f, 16)
                if h is None:
                    return
                sec, frac, incl, _orig = rec.unpack(h)
                frame = _read_exact(f, incl)
                if frame is None:
                    return
                if len(frame) < 42 or frame[12:14] != b"\x08\x00" or frame[23] != 17:
                    continue
                u = 14 + (frame[14] & 0x0F) * 4
                sport, dport = struct.unpack_from(">HH", frame, u)
                if DUML_PORT not in (sport, dport):
                    continue
                yield sec + frac / div, frame[u + 8:]
        finally:
            self.close()

    def close(self):
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass
            self._proc = None


def _read_exact(f, n):
    """Đọc đúng n byte từ stream (pipe có thể trả từng phần). None nếu EOF."""
    buf = bytearray()
    while len(buf) < n:
        chunk = f.read(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return bytes(buf)
