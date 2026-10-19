"""Demo: lấy luồng video H.265 bằng neo2sdk, ghi ra file .h265.

    python examples/save_video.py captures/cap_02_idle_30s.pcap out.h265
    ffmpeg -flags2 +showall -err_detect ignore_err -i out.h265 out.mp4   # xem thử

Lưu ý: drone không gửi keyframe định kỳ (xem notes/tien-do-giai-ma.md 6.1),
nên bản ghi giữa phiên sẽ mờ rồi rõ dần. Cần bộ tham số VPS/SPS/PPS từ lúc
mở phiên/kết nối lại để giải mã sạch.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neo2sdk import MSDKManager


def main(pcap, out):
    sdk = MSDKManager()
    sdk.connect(pcap)
    f = open(out, "wb")
    sdk.on_video(f.write)
    print(f"Ghép video {pcap} -> {out} ...")
    sdk.start()
    f.close()
    print(f"Xong: {sdk.video.bytes_out} byte H.265, {sdk.stats['video_packets']} gói video, "
          f"{sdk.video.lost_packets} chỗ mất gói.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "captures/cap_02_idle_30s.pcap",
         sys.argv[2] if len(sys.argv) > 2 else "out.h265")
