// duml_sniff.js — hook điểm GỬI gói UDP của DJI Fly, log frame DUML app->drone realtime.
//
// Mục đích: khi đẩy cần điều khiển, xem frame/byte nào biến đổi → tìm lệnh điều khiển
// (xem notes/capture-log.md, phần kiến trúc điều khiển — mảnh ghép còn thiếu).
//
// Chạy (khi có drone + frida-server đang chạy trên điện thoại):
//   frida -U -f dji.go.v5 -l tools/frida/duml_sniff.js        (spawn)
//   frida -U -n "DJI Fly" -l tools/frida/duml_sniff.js        (attach)
//
// Mẹo dùng: đẩy MỘT cần (vd yaw) CHẬM từ giữa sang hết cỡ. Frame nào có payload
// biến thiên mượt theo tay = frame lệnh. Lọc sẵn: chỉ in frame app->drone, kèm
// cmd_set/id và payload; gộp frame trùng để đỡ nhiễu.

'use strict';

const PORT_9003 = 9003;
const DELIM = 0x55;

// CRC8 (init 0x77, poly 0x8C reflected) để xác nhận biên frame
const T8 = (() => { const t = []; for (let i = 0; i < 256; i++) { let c = i; for (let k = 0; k < 8; k++) c = (c & 1) ? ((c >>> 1) ^ 0x8C) : (c >>> 1); t[i] = c; } return t; })();
function crc8(bytes, off, n) { let c = 0x77; for (let i = 0; i < n; i++) c = T8[(c ^ bytes[off + i]) & 0xFF]; return c; }

// in gọn: gộp theo (set,id), chỉ in lại khi payload đổi
const lastPayload = {};

function handlePacket(bytes) {
  // header ngoài: [0:2] = len|0x8000, [6] = kênh. Chỉ xét app->drone DUML (kênh 0x04).
  if (bytes.length < 34) return;
  const lenFlag = bytes[0] | (bytes[1] << 8);
  if ((lenFlag & 0x8000) === 0) return;
  if ((lenFlag & 0x7FFF) !== bytes.length) return;
  const channel = bytes[6];
  if (channel !== 0x04) return;           // 0x04 = DUML app->drone

  // duyệt frame DUML từ offset 34
  let i = 34;
  while (i + 13 <= bytes.length) {
    if (bytes[i] !== DELIM || crc8(bytes, i, 3) !== bytes[i + 3]) { i++; continue; }
    const flen = (bytes[i + 1] | (bytes[i + 2] << 8)) & 0x3FF;
    if (flen < 13 || i + flen > bytes.length) { i++; continue; }
    const src = bytes[i + 4], dst = bytes[i + 5], cs = bytes[i + 9], ci = bytes[i + 10];
    const payload = bytes.slice(i + 11, i + flen - 2);
    const key = `${hex(src)}->${hex(dst)} set=${hex(cs)} id=${hex(ci)} len=${payload.length}`;
    const ph = Array.from(payload).map(hex2).join(' ');
    // frame tunnel 0x51/0x01 không in (chứa telemetry chiều kia); chỉ quan tâm lệnh thật
    if (!(cs === 0x51 && ci === 0x01) && lastPayload[key] !== ph) {
      lastPayload[key] = ph;
      console.log(`[TX] ${key}  ${ph}`);
    }
    i += flen;
  }
}

function hex(n) { return '0x' + n.toString(16).padStart(2, '0'); }
function hex2(n) { return n.toString(16).padStart(2, '0'); }

function hookSend(name) {
  const p = Module.findExportByName('libc.so', name);
  if (!p) { console.log('không tìm thấy ' + name); return; }
  Interceptor.attach(p, {
    onEnter(args) {
      // sendto(fd, buf, len, flags, dest, addrlen) / send(fd, buf, len, flags)
      const buf = args[1];
      const len = args[2].toInt32();
      if (len < 34 || len > 1600) return;
      try {
        const bytes = new Uint8Array(buf.readByteArray(Math.min(len, 1600)));
        handlePacket(bytes);
      } catch (e) {}
    }
  });
  console.log('đã hook ' + name);
}

console.log('=== duml_sniff: hook điểm gửi, log frame lệnh app->drone ===');
console.log('Đẩy MỘT cần chậm từ giữa sang hết cỡ; frame nào payload biến thiên = lệnh điều khiển.');
hookSend('sendto');
hookSend('sendmsg');   // phòng khi app dùng sendmsg
