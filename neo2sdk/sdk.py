"""MSDKManager — điểm vào tầng cao nhất, ghép các tầng lại (như MSDK V5).

    App  →  MSDKManager  →  SDK Core  →  Transport
Luồng đọc:
    nguồn gói → parse_outer → demux theo kênh
        kênh DUML  → iter_frames → decode_telemetry → KeyManager cập nhật
        kênh video → VideoDecoder

    sdk = MSDKManager()
    sdk.connect("captures/cap_08_attitude.pcap")        # hoặc "udp"
    sdk.key_manager.listen(BatteryKey.PercentRemaining, print)
    sdk.on_video(lambda chunk: f.write(chunk))
    sdk.start()                                          # chạy đến hết nguồn (pcap) / mãi (udp)
"""
from __future__ import annotations

import threading

from .core.telemetry import decode as decode_telemetry
from .core.video import VideoDecoder
from .keys.manager import KeyManager
from .transport.framing import CH_DUML_APP, CH_DUML_DRONE, CH_VIDEO, parse_outer
from .transport.duml import iter_frames
from .transport.source import PcapSource, UdpSource


class MSDKManager:
    def __init__(self):
        self.key_manager = KeyManager()
        self.video = VideoDecoder()
        self._source = None
        self._thread = None
        self._running = False
        # thống kê
        self.stats = {"packets": 0, "duml_frames": 0, "telemetry_updates": 0, "video_packets": 0}

    # --- kết nối nguồn ---
    def connect(self, source):
        """source: đường dẫn .pcap (offline) hoặc "udp" (live, cùng mạng drone)."""
        if source == "udp":
            self._source = UdpSource()
        elif hasattr(source, "__iter__") and not isinstance(source, str):
            self._source = source          # nguồn tự cấp
        else:
            self._source = PcapSource(source)
        return self

    def on_video(self, callback):
        """Đăng ký nhận từng chunk bitstream H.265."""
        self.video.on_chunk = callback
        return self

    # --- vòng đọc ---
    def _loop(self):
        for _ts, payload in self._source:
            if not self._running:
                break
            outer = parse_outer(payload)
            if outer is None:
                continue
            self.stats["packets"] += 1
            if outer.channel == CH_VIDEO:
                self.stats["video_packets"] += 1
                self.video.feed(outer)
            elif outer.channel in (CH_DUML_DRONE, CH_DUML_APP):
                # frame DUML nằm sau 18 byte header riêng của kênh (offset 34 tính từ gói;
                # body bắt đầu ở offset 16, nên trong body là offset 18)
                for frame in iter_frames(outer.body, 18):
                    self.stats["duml_frames"] += 1
                    for key, value in decode_telemetry(frame):
                        self.stats["telemetry_updates"] += 1
                        self.key_manager._update(key, value)
        self._running = False

    def start(self, background: bool = False):
        """Chạy vòng đọc. background=True để chạy luồng nền (cho nguồn udp)."""
        if self._source is None:
            raise RuntimeError("Chưa connect() nguồn.")
        self._running = True
        if background:
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        else:
            self._loop()
        return self

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
