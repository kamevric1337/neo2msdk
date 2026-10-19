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
        from .core.control import FlightControl
        self.flight_control = FlightControl(self)
        self._source = None
        self._thread = None
        self._running = False
        self.session_id = 0        # cập nhật từ gói đến; cần để dựng lệnh gửi đi
        self._seq = 0              # bộ đếm seq cho khung gửi đi
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
            self.session_id = outer.session_id   # theo dõi phiên hiện tại (để dựng lệnh gửi)
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

    # --- đường ghi (điều khiển) ---
    def build_request_iframe(self, request: bool = True) -> bytes:
        """Dựng gói xin keyframe cho phiên hiện tại (không gửi). Dùng được offline."""
        from .core.commands import request_iframe_packet
        self._seq = (self._seq + 1) & 0xFFFF
        return request_iframe_packet(self.session_id, seq=self._seq, request=request)

    def request_iframe(self, request: bool = True):
        """Dựng + GỬI lệnh xin keyframe (cần đã connect "udp" với drone thật).

        Đây là lệnh điều khiển DUY NHẤT hiện đã giải mã trọn vẹn và dựng byte chính
        xác (trùng y hệt app, xem tests). Các lệnh khác chờ Frida.
        """
        pkt = self.build_request_iframe(request)
        if isinstance(self._source, UdpSource):
            self._source.send(pkt)
            return True
        raise RuntimeError(
            "Chưa kết nối live: request_iframe() cần connect('udp') với drone. "
            "Dùng build_request_iframe() để lấy byte gói mà không gửi.")
