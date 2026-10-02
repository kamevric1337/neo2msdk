"""Dò trường góc gimbal trong telemetry (cap_06): i16 LE bám theo 4 mốc gimbal.

Mốc (giờ điện thoại): giữ yên ~10s trước khi người dùng nhắn, nên cửa sổ ổn định nằm
TRƯỚC thời điểm nhắn. Tìm field: ~bằng nhau ở bước 1 & 4 (ngang), lệch mạnh và NGƯỢC phía
ở bước 2 (xuống) & 3 (lên).
"""
import struct, sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from duml_survey import ip_udp, scan
from find_battery_field import read_pcap

TZ = timezone(timedelta(hours=7))
def ts(hms): h,m,s = map(int,hms.split(":")); return datetime(2026,10,2,h,m,s,tzinfo=TZ).timestamp()
# cửa sổ ổn định: [mốc-7s, mốc-1s]
WIN = {1:(ts("16:08:08"),ts("16:08:14")), 2:(ts("16:09:09"),ts("16:09:15")),
       3:(ts("16:09:38"),ts("16:09:44")), 4:(ts("16:10:04"),ts("16:10:10"))}
path = sys.argv[1] if len(sys.argv)>1 else "../captures/cap_06_gimbal.pcap"

# key -> step -> list of i16 values
vals = defaultdict(lambda: defaultdict(list))
for t, fr in read_pcap(path):
    r = ip_udp(fr)
    if r is None: continue
    drone, p = r
    if not drone: continue
    step = next((k for k,(a,b) in WIN.items() if a<=t<=b), None)
    if step is None: continue
    for off,n,s,d,cs,ci in scan(p):
        if cs==0x51 and ci==0x01: continue  # bỏ frame tunnel, chỉ xét telemetry thật
        pl = p[off+11:off+n-2]
        for o in range(0, len(pl)-1):
            v = struct.unpack("<h", pl[o:o+2])[0]
            vals[(s,d,cs,ci,len(pl),o)][step].append(v)

import statistics as st
cand = []
for k, sv in vals.items():
    if any(step not in sv for step in (1,2,3,4)): continue
    m = {step: st.median(sv[step]) for step in (1,2,3,4)}
    base = (m[1]+m[4])/2
    d2, d3 = m[2]-base, m[3]-base
    # bước 2 và 3 ngược phía, biên độ lớn, bước 1~4
    if d2*d3 >= 0: continue
    spread = min(abs(d2), abs(d3))
    level_diff = abs(m[1]-m[4])
    # loại field nhiễu loạn: độ lệch chuẩn trong mỗi cửa sổ phải nhỏ so với spread
    noise = max(st.pstdev(sv[step]) if len(sv[step])>1 else 0 for step in (1,2,3,4))
    if spread < 20 or level_diff > spread*0.6 or noise > spread*0.4: continue
    cand.append((spread, level_diff, noise, k, m))
cand.sort(key=lambda c:(-c[0], c[1]))
print(f"{len(cand)} ứng viên (spread giảm dần):\n")
for spread,ld,noise,k,m in cand[:25]:
    s,d,cs,ci,plen,o = k
    print(f"  {s:#04x}->{d:#04x} set={cs:#04x} id={ci:#04x} plen={plen} off={o:3d} i16  "
          f"B1={m[1]:.0f} B2(xuống)={m[2]:.0f} B3(lên)={m[3]:.0f} B4={m[4]:.0f}  "
          f"spread={spread:.0f} |B1-B4|={ld:.0f} noise={noise:.0f}")
