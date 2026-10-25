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
    // bỏ nhiễu: tunnel telemetry 0x51/0x01 và nhịp tim 0x01/0x0a (bộ đếm thời gian tăng liên tục)
    const noise = (cs === 0x51 && ci === 0x01) || (cs === 0x01 && ci === 0x0a);
    if (!noise && lastPayload[key] !== ph) {
      lastPayload[key] = ph;
      console.log(`[TX] ${key}  ${ph}`);
    }
    i += flen;
  }
}

function hex(n) { return '0x' + n.toString(16).padStart(2, '0'); }
function hex2(n) { return n.toString(16).padStart(2, '0'); }

// frida 16 có Module.findExportByName(mod,name) tĩnh; frida 17 bỏ, thay bằng
// Process.getModuleByName(mod).findExportByName(name). Thử cả hai cho tương thích.
function resolveExport(mod, name) {
  try { if (typeof Module.findExportByName === 'function') { const p = Module.findExportByName(mod, name); if (p) return p; } } catch (e) {}
  try { const m = Process.getModuleByName(mod); if (m) return m.findExportByName(name); } catch (e) {}
  try { if (typeof Module.getGlobalExportByName === 'function') return Module.getGlobalExportByName(name); } catch (e) {}
  return null;
}

function readAndHandle(buf, len) {
  if (len < 34 || len > 4096) return;
  try {
    const bytes = new Uint8Array(buf.readByteArray(Math.min(len, 4096)));
    handlePacket(bytes);
  } catch (e) {}
}

// sendto(fd, buf, len, flags, dest, addrlen) / send(fd, buf, len, flags):
// args[1] = buffer, args[2] = độ dài.
function hookSendto(name) {
  const p = resolveExport('libc.so', name);
  if (!p) { console.log('không tìm thấy ' + name); return; }
  Interceptor.attach(p, {
    onEnter(args) { readAndHandle(args[1], args[2].toInt32()); }
  });
  console.log('đã hook ' + name);
}

// sendmsg(fd, msghdr*, flags): args[1] = struct msghdr*. Trên aarch64:
//   msg_iov @ +16 (con trỏ mảng iovec), msg_iovlen @ +24.
//   iovec = { void* iov_base @ +0 ; size_t iov_len @ +8 }.
// Một datagram UDP thường chỉ có 1 iov; duyệt hết cho chắc.
function hookSendmsg() {
  const p = resolveExport('libc.so', 'sendmsg');
  if (!p) { console.log('không tìm thấy sendmsg'); return; }
  Interceptor.attach(p, {
    onEnter(args) {
      try {
        const msghdr = args[1];
        const iov = msghdr.add(16).readPointer();
        const iovlen = msghdr.add(24).readU64().toNumber();
        for (let k = 0; k < iovlen && k < 8; k++) {
          const ent = iov.add(k * 16);
          const base = ent.readPointer();
          const len = ent.add(8).readU64().toNumber();
          readAndHandle(base, len);
        }
      } catch (e) {}
    }
  });
  console.log('đã hook sendmsg');
}

console.log('=== duml_sniff: hook điểm gửi, log frame lệnh app->drone ===');
console.log('Thao tác MỘT thứ (vd kéo gimbal) chậm; frame nào payload biến thiên theo tay = lệnh.');
hookSendto('sendto');
hookSendto('send');
hookSendmsg();
