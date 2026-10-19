"""KeyManager — API Key-based (như MSDK V5).

    km.get_value(FlightControllerKey.Attitude)        # giá trị mới nhất (cache)
    km.listen(BatteryKey.PercentRemaining, callback)  # gọi callback mỗi lần cập nhật
    km.set_value(ControlKey.VirtualStick, ...)        # (chưa hỗ trợ — đường điều khiển)

Cache lưu giá trị mới nhất của mỗi Key; listener được gọi khi giá trị tới.
"""
from __future__ import annotations

import threading
from collections import defaultdict

from .keys import Key


class KeyManager:
    def __init__(self):
        self._cache = {}
        self._listeners = defaultdict(list)
        self._lock = threading.Lock()

    # --- API đọc ---
    def get_value(self, key: Key):
        """Giá trị mới nhất của key, hoặc None nếu chưa có."""
        with self._lock:
            return self._cache.get(key)

    def listen(self, key: Key, callback):
        """Đăng ký nhận cập nhật cho key. callback(value) gọi mỗi lần có giá trị mới."""
        with self._lock:
            self._listeners[key].append(callback)

    def remove_listener(self, key: Key, callback):
        with self._lock:
            if callback in self._listeners[key]:
                self._listeners[key].remove(callback)

    # --- API ghi (điều khiển) — CHƯA hỗ trợ ---
    def set_value(self, key: Key, value):
        raise NotImplementedError(
            "Đường điều khiển chưa hỗ trợ: cần lấy frame lệnh qua Frida hook động "
            "(xem notes/capture-log.md, phần kiến trúc điều khiển).")

    # --- nội bộ: SDK Core gọi khi có giá trị mới ---
    def _update(self, key: Key, value):
        with self._lock:
            self._cache[key] = value
            listeners = list(self._listeners.get(key, ()))
        for cb in listeners:
            try:
                cb(value)
            except Exception as e:  # listener lỗi không được làm sập vòng đọc
                print(f"[KeyManager] listener {key} lỗi: {e}")
