"""SDK Core — ghép luồng video H.265 từ kênh video (byte6 = 0x02).

Mỗi gói video = 20 byte header + dữ liệu H.265. Ghép liền body[4:] (bỏ 4 byte
riêng của video sau 16 byte header chung) được bitstream Annex-B.
Xem notes/tien-do-giai-ma.md mục 6.
"""
from __future__ import annotations

VIDEO_HDR_EXTRA = 4   # 4 byte riêng kênh video, ngay sau 16 byte header chung
START_CODE = b"\x00\x00\x00\x01"


class VideoDecoder:
    """Nhận body của gói kênh video, nhả dần bitstream H.265.

    Dùng: đăng ký callback nhận từng chunk, hoặc ghi ra file .h265 để ffmpeg phát.
    Lưu ý: drone không gửi keyframe định kỳ (xem mục 6.1) — hình sẽ rõ dần, hoặc
    cần gửi lệnh xin I-frame (đường điều khiển, chưa hỗ trợ).
    """

    def __init__(self, on_chunk=None):
        self.on_chunk = on_chunk
        self._started = False
        self._seq = None
        self.lost_packets = 0
        self.bytes_out = 0

    def feed(self, outer):
        """Nạp một OuterPacket kênh video."""
        body = outer.body
        if len(body) <= VIDEO_HDR_EXTRA:
            return
        data = body[VIDEO_HDR_EXTRA:]
        # theo dõi mất gói qua seq video (+8 mỗi gói)
        if self._seq is not None and (outer.video_seq - self._seq) % 65536 != 8:
            self.lost_packets += 1
        self._seq = outer.video_seq
        # bắt đầu khi thấy NAL đầu tiên để tránh nửa khung dở
        if not self._started:
            if not data.startswith(START_CODE):
                return
            self._started = True
        self.bytes_out += len(data)
        if self.on_chunk:
            self.on_chunk(data)
