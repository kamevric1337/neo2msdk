-- Dissector cho giao thức bọc ngoài của DJI Neo 2 trên UDP cổng 9003
-- (điện thoại nối thẳng Wi-Fi vào drone, không qua RC).
--
-- Giải mã header bọc ngoài, phân loại kênh (DUML / video H.265), đi theo
-- các frame DUML kể cả frame lồng trong tunnel 0x51/0x01, và chú thích hai
-- trường đã xác định thực nghiệm: % pin và lệnh app xin keyframe (I-frame).
-- Xem notes/capture-log.md (cap_02/cap_04/cap_05) để biết nguồn gốc từng kết luận.
--
-- Nạp qua init.lua (dofile) hoặc test rời:
--   tshark -X lua_script:dji-dumlv1-proto.lua -X lua_script:dji-neo2-udp.lua -r cap.pcap
-- Cần dji-dumlv1-proto.lua nạp trước để có dji_dumlv1_main_dissector (nếu thiếu,
-- dissector này vẫn chạy và chỉ hiện src/dst/cmd_set/cmd_id tự parse).

local NEO2_UDP_PORT = 9003

local p_neo2 = Proto("dji_neo2", "DJI Neo 2 (UDP 9003 wrapper)")

local CHANNEL_TEXT = {
    [0x00] = "Handshake (reconnect)",
    [0x01] = "DUML drone->app",
    [0x02] = "Video (H.265)",
    [0x04] = "DUML app->drone",
}

local f_len      = ProtoField.uint16("dji_neo2.len", "Payload length", base.DEC, nil, 0x7FFF)
local f_flag8000 = ProtoField.bool("dji_neo2.flag8000", "Length flag 0x8000", 16, nil, 0x8000)
local f_session  = ProtoField.uint16("dji_neo2.session", "Session id", base.HEX)
local f_vseq     = ProtoField.uint16("dji_neo2.video_seq", "Video seq", base.HEX)
local f_channel  = ProtoField.uint8("dji_neo2.channel", "Channel type", base.HEX, CHANNEL_TEXT)
local f_chksum   = ProtoField.uint8("dji_neo2.checksum", "Header checksum (XOR b0..b6)", base.HEX)
local f_chk_ok   = ProtoField.bool("dji_neo2.checksum_ok", "Checksum valid")
local f_ack      = ProtoField.uint16("dji_neo2.video_ack", "Video seq ACK (app->drone)", base.HEX)
local f_vpayload = ProtoField.bytes("dji_neo2.video_payload", "H.265 payload")
local f_frame    = ProtoField.bytes("dji_neo2.duml_frame", "DUML frame")
local f_src      = ProtoField.uint8("dji_neo2.src", "Src module", base.HEX)
local f_dst      = ProtoField.uint8("dji_neo2.dst", "Dst module", base.HEX)
local f_cmdset   = ProtoField.uint8("dji_neo2.cmd_set", "Cmd set", base.HEX)
local f_cmdid    = ProtoField.uint8("dji_neo2.cmd_id", "Cmd id", base.HEX)
local f_battery  = ProtoField.uint8("dji_neo2.battery_pct", "Battery %", base.DEC)
local f_keyframe = ProtoField.bool("dji_neo2.keyframe_request", "App I-frame request")

p_neo2.fields = {
    f_len, f_flag8000, f_session, f_vseq, f_channel, f_chksum, f_chk_ok, f_ack,
    f_vpayload, f_frame, f_src, f_dst, f_cmdset, f_cmdid, f_battery, f_keyframe,
}

-- Bảng tên module/cmd_set mượn từ dji-dumlv1-proto.lua nếu đã nạp.
local SRC_DST = DJI_DUMLv1_SRC_DEST_TEXT or {}
local CMD_SET = DJI_DUMLv1_CMD_SET_TEXT or {}

-- CRC8 header DUML (poly 0x31 reflected = 0x8C, init 0x77) để tìm biên frame.
local crc8_table = {}
for i = 0, 255 do
    local c = i
    for _ = 1, 8 do
        if c % 2 == 1 then c = math.floor(c / 2) ~ 0x8C else c = math.floor(c / 2) end
    end
    crc8_table[i] = c
end
local function crc8(tvb, off, n)
    local c = 0x77
    for i = 0, n - 1 do
        c = crc8_table[(c ~ tvb(off + i, 1):uint()) & 0xFF]
    end
    return c
end

-- Dissect một frame DUML tại [off] trong tvb; trả độ dài frame, hoặc 0 nếu không hợp lệ.
local function dissect_frame(tvb, off, pinfo, tree, depth)
    if off + 4 > tvb:len() then return 0 end
    if tvb(off, 1):uint() ~= 0x55 then return 0 end
    if crc8(tvb, off, 3) ~= tvb(off + 3, 1):uint() then return 0 end
    local flen = tvb(off + 1, 2):le_uint() & 0x03FF
    if flen < 13 or off + flen > tvb:len() then return 0 end

    local src = tvb(off + 4, 1):uint()
    local dst = tvb(off + 5, 1):uint()
    local cset = tvb(off + 9, 1):uint()
    local cid = tvb(off + 10, 1):uint()
    local label = string.format("DUML %s->%s set=0x%02x id=0x%02x",
        SRC_DST[src] or string.format("0x%02x", src),
        SRC_DST[dst] or string.format("0x%02x", dst), cset, cid)

    local sub = tree:add(f_frame, tvb(off, flen))
    sub:append_text(": " .. label)
    sub:add(f_src, tvb(off + 4, 1))
    sub:add(f_dst, tvb(off + 5, 1))
    sub:add(f_cmdset, tvb(off + 9, 1)):append_text(
        " (" .. (CMD_SET[cset] or "?") .. ")")
    sub:add(f_cmdid, tvb(off + 10, 1))

    -- Trường đã xác định thực nghiệm (xem capture-log.md):
    -- Pin: src=0x0b set=0x0d id=0x02, payload[20] = % pin. payload bắt đầu ở off+11.
    if src == 0x0b and cset == 0x0d and cid == 0x02 and flen >= 11 + 21 + 2 then
        sub:add(f_battery, tvb(off + 11 + 20, 1)):append_text(" (pin -> app)")
        pinfo.cols.info:append(string.format(" [BAT %d%%]", tvb(off + 11 + 20, 1):uint()))
    end
    -- Xin keyframe: 0x02->0x09 set=0x01 id=0x01, payload[5] bit 0x20 bật = xin.
    if src == 0x02 and dst == 0x09 and cset == 0x01 and cid == 0x01 and flen >= 11 + 6 + 2 then
        local req = (tvb(off + 11 + 5, 1):uint() & 0x20) ~= 0
        sub:add(f_keyframe, tvb(off + 11 + 5, 1), req)
        if req then pinfo.cols.info:append(" [I-FRAME REQ]") end
    end

    -- Giao cho dissector DUML gốc nếu có (hiện chi tiết đầy đủ trong cây con).
    if dji_dumlv1_main_dissector ~= nil then
        local duml = sub:add(tvb(off, flen), "DUML v1 detail")
        pcall(dji_dumlv1_main_dissector, tvb(off, flen), pinfo, duml)
    end

    -- Tunnel 0x51/0x01: payload chứa các frame DUML lồng -> đệ quy.
    if cset == 0x51 and cid == 0x01 and depth < 4 then
        local p = off + 11
        local pend = off + flen - 2
        while p < pend do
            local inner = dissect_frame(tvb, p, pinfo, sub, depth + 1)
            if inner == 0 then p = p + 1 else p = p + inner end
        end
    end
    return flen
end

function p_neo2.dissector(tvb, pinfo, tree)
    local n = tvb:len()
    if n < 16 then return 0 end

    local b0 = tvb(0, 2):le_uint()
    local declared = b0 & 0x7FFF
    if (b0 & 0x8000) == 0 or declared ~= n then return 0 end  -- không phải gói Neo 2

    pinfo.cols.protocol = "DJI-Neo2"
    local channel = tvb(6, 1):uint()
    local root = tree:add(p_neo2, tvb(), "DJI Neo 2, " .. (CHANNEL_TEXT[channel] or "channel ?"))

    root:add_le(f_len, tvb(0, 2))
    root:add_le(f_flag8000, tvb(0, 2))
    root:add_le(f_session, tvb(2, 2))
    root:add_le(f_vseq, tvb(4, 2))
    root:add(f_channel, tvb(6, 1))

    -- checksum = XOR byte 0..6
    local x = 0
    for i = 0, 6 do x = x ~ tvb(i, 1):uint() end
    root:add(f_chksum, tvb(7, 1))
    root:add(f_chk_ok, tvb(7, 1), x == tvb(7, 1):uint())

    if channel == 0x04 then  -- app->drone: byte 8-9 là ACK seq video
        root:add_le(f_ack, tvb(8, 2))
    end

    if channel == 0x02 then
        pinfo.cols.info = string.format("Video seq=0x%04x len=%d", tvb(4, 2):le_uint(), n - 20)
        if n > 20 then root:add(f_vpayload, tvb(20, n - 20)) end
        return n
    end

    if channel == 0x01 or channel == 0x04 then
        pinfo.cols.info = (channel == 0x01) and "DUML drone->app" or "DUML app->drone"
        if n <= 34 then
            pinfo.cols.info:append(" (keep-alive)")
            return n
        end
        local off = 34
        while off < n do
            local flen = dissect_frame(tvb, off, pinfo, root, 0)
            if flen == 0 then off = off + 1 else off = off + flen end
        end
        return n
    end

    return n  -- channel 0x00 (handshake) / khác: chỉ header
end

DissectorTable.get("udp.port"):add(NEO2_UDP_PORT, p_neo2)
