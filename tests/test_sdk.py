"""Unit test cho neo2sdk — chạy: python tests/test_sdk.py (không cần pytest).

Gồm: round-trip encode/decode (frame DUML, header ngoài, lệnh xin keyframe),
và kiểm tra giải mã telemetry trên pcap thật cho ra giá trị hợp lý.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from neo2sdk.transport.duml import build_frame, crc16, iter_frames
from neo2sdk.transport.framing import (CH_DUML_APP, build_duml_app_packet,
                                        build_outer, parse_outer)
from neo2sdk.core.commands import request_iframe_frame, request_iframe_packet
from neo2sdk.core.telemetry import decode as decode_telemetry
from neo2sdk import MSDKManager
from neo2sdk.keys import BatteryKey, FlightControllerKey


def test_duml_roundtrip():
    f = build_frame(0x02, 0x09, 0x01, 0x0a, b"\x11\x22\x33", seq=0x1234)
    frames = list(iter_frames(f))
    assert len(frames) == 1, "phải parse ra đúng 1 khung"
    fr = frames[0]
    assert fr.key() == (0x02, 0x09, 0x01, 0x0a)
    assert fr.seq == 0x1234
    assert fr.payload == b"\x11\x22\x33"
    # CRC16 ở cuối phải khớp
    assert crc16(f[:-2]) == int.from_bytes(f[-2:], "little")


def test_tunnel_nesting():
    inner = build_frame(0x0b, 0x02, 0x0d, 0x02, b"x" * 44, seq=1)
    tunnel = build_frame(0x27, 0xee, 0x51, 0x01, inner, seq=2)
    frames = list(iter_frames(tunnel))
    keys = [f.key() for f in frames]
    assert (0x27, 0xee, 0x51, 0x01) in keys, "thấy frame tunnel"
    assert (0x0b, 0x02, 0x0d, 0x02) in keys, "thấy frame lồng bên trong"
    assert any(f.nested for f in frames), "frame lồng được đánh dấu nested"


def test_outer_roundtrip():
    body = b"hello-body-data"
    pkt = build_outer(CH_DUML_APP, body, session_id=0xabb1, video_ack=0x1234)
    o = parse_outer(pkt)
    assert o is not None and o.checksum_ok, "checksum XOR phải hợp lệ"
    assert o.channel == CH_DUML_APP
    assert o.session_id == 0xabb1
    assert o.body == body
    assert o.length == len(pkt)


def test_request_iframe_bytes():
    # khớp mẫu cap_05: payload 11 byte, byte[5]=0x24 khi xin
    f = request_iframe_frame(seq=0xcdb8, request=True)
    frames = list(iter_frames(f))
    assert len(frames) == 1
    pl = frames[0].payload
    assert pl == bytes([0, 0, 0, 0, 0, 0x24, 0, 0, 0, 0x24, 0]), pl.hex()
    assert frames[0].key() == (0x02, 0x09, 0x01, 0x01)
    # không xin -> 0x04
    f2 = request_iframe_frame(request=False)
    assert list(iter_frames(f2))[0].payload[5] == 0x04


def test_request_iframe_byte_exact():
    # frame dựng phải TRÙNG BYTE Y HỆT frame thật quan sát ở cap_05 (seq=0xcdb8)
    real = bytes.fromhex("551804200209b8cd00010100000000002400000024 00fa23".replace(" ", ""))
    assert request_iframe_frame(seq=0xcdb8, request=True) == real


def test_manager_build_request_iframe():
    sdk = MSDKManager()
    sdk.session_id = 0xabb1
    pkt = sdk.build_request_iframe()
    o = parse_outer(pkt)
    assert o is not None and o.checksum_ok and o.session_id == 0xabb1
    frames = list(iter_frames(o.body, 18))
    assert any(f.key() == (0x02, 0x09, 0x01, 0x01) for f in frames)


def test_request_iframe_packet_parses():
    pkt = request_iframe_packet(session_id=0xabb1, seq=5)
    o = parse_outer(pkt)
    assert o is not None and o.checksum_ok
    # khung nằm sau 18 byte sub-header trong body
    frames = list(iter_frames(o.body, 18))
    assert any(f.key() == (0x02, 0x09, 0x01, 0x01) for f in frames)


def test_telemetry_on_pcap():
    pcap = ROOT / "captures" / "cap_09_flight_indoor.pcap"
    if not pcap.exists():
        print("  (bỏ qua test_telemetry_on_pcap — không có pcap)")
        return
    sdk = MSDKManager().connect(str(pcap))
    sdk.start()
    km = sdk.key_manager
    bat = km.get_value(BatteryKey.PercentRemaining)
    att = km.get_value(FlightControllerKey.Attitude)
    assert bat is not None and 0 <= bat <= 100, f"pin bất thường: {bat}"
    assert att is not None and -180 <= att.yaw <= 360, f"yaw bất thường: {att}"
    assert sdk.stats["telemetry_updates"] > 1000, "quá ít cập nhật telemetry"


def test_frame_decode_battery():
    # dựng frame pin với giá trị biết trước rồi decode lại
    import struct
    pl = bytearray(44)
    struct.pack_into("<I", pl, 1, 7800)    # voltage
    struct.pack_into("<i", pl, 5, -650)    # current
    struct.pack_into("<I", pl, 9, 1639)    # full
    struct.pack_into("<I", pl, 13, 1000)   # remain
    pl[19] = 2                              # cells
    pl[20] = 55                             # soc
    f = list(iter_frames(build_frame(0x0b, 0x02, 0x0d, 0x02, bytes(pl))))[0]
    updates = dict(decode_telemetry(f))
    info = updates[BatteryKey.Info]
    assert info.percent == 55 and info.voltage_mv == 7800 and info.cells == 2
    assert info.current_ma == -650 and info.remain_mah == 1000


def test_osd_full_decode():
    # dựng frame OSD với GPS + cờ in_air/motor + vệ tinh, decode lại
    import math
    import struct
    from neo2sdk.keys import FlightControllerKey
    p = bytearray(42)
    struct.pack_into("<d", p, 0, math.radians(105.8))    # longitude
    struct.pack_into("<d", p, 8, math.radians(21.0))     # latitude
    struct.pack_into("<h", p, 16, 125)                   # height 12.5m
    struct.pack_into("<h", p, 24, 0)                     # pitch
    struct.pack_into("<h", p, 28, 900)                   # yaw 90°
    p[30] = 43                                           # flyc_state
    struct.pack_into("<I", p, 32, 0x04 | 0x08 | 0x8000)  # in_air+motor+gps_used
    p[36] = 14                                           # 14 vệ tinh
    f = list(iter_frames(build_frame(0x03, 0x02, 0x03, 0x43, bytes(p))))[0]
    u = dict(decode_telemetry(f))
    loc = u[FlightControllerKey.Location]
    assert abs(loc.latitude - 21.0) < 1e-4 and abs(loc.longitude - 105.8) < 1e-4, loc
    st = u[FlightControllerKey.Status]
    assert st.in_air and st.motors_on and st.gps_used and st.satellites == 14, st
    assert u[FlightControllerKey.IsFlying] is True
    assert abs(u[FlightControllerKey.Altitude] - 12.5) < 1e-6


def test_control_scaffold():
    from neo2sdk.core.control import JoystickConfig
    c = JoystickConfig(throttle=2.0, yaw=-3.0).clamped()
    assert c.throttle == 1.0 and c.yaw == -1.0, "phải kẹp về [-1,1]"
    sdk = MSDKManager()
    assert sdk.flight_control is not None
    raised = False
    try:
        sdk.flight_control.send_virtual_stick(yaw=0.5)
    except NotImplementedError:
        raised = True
    assert raised, "send_virtual_stick phải báo chưa hỗ trợ (cần Frida)"


def run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} test PASS")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
