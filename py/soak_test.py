#!/usr/bin/env python3
"""用 Python 直接进游戏跑一段，量帧率与战斗数据。

没有装 playwright / selenium 也没关系：这里只用标准库实现了一个最小的
Chrome DevTools Protocol 客户端（HTTP 拿调试目标 + 手写 WebSocket 帧），
所以它做的是和真人一样的事 —— 真的在画布上按下鼠标、拖动、松开，
然后从页面里读回 fps、分数、击杀数、敌机数量。

    python3 py/soak_test.py                  # 默认 12 秒
    python3 py/soak_test.py --seconds 20 --palette 2
    python3 py/soak_test.py --headful        # 想看着它跑

退出码：0 = 跑完且没有 JS 报错；1 = 有报错或没跑起来。
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME_URL = "file://" + os.path.join(ROOT, "index.html")
VIEW_W, VIEW_H = 1440, 900


# ---------------------------------------------------------------- 最小 CDP 客户端
class WS:
    """够用就好的 WebSocket 客户端：只处理文本帧和 ping。"""

    def __init__(self, host: str, port: int, path: str) -> None:
        self.sock = socket.create_connection((host, port), timeout=15)
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise IOError("调试端口握手被关闭")
            buf += chunk
        head, _, rest = buf.partition(b"\r\n\r\n")
        if b"101" not in head.split(b"\r\n")[0]:
            raise IOError("WebSocket 握手失败: " + head[:120].decode("latin-1"))
        self.buf = rest

    def _read(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise IOError("调试连接被关闭")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text: str) -> None:
        data = text.encode()
        header = bytearray([0x81])          # FIN + text
        n = len(data)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack("!H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack("!Q", n)
        mask = os.urandom(4)
        header += mask
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + masked)

    def recv(self) -> str:
        while True:
            b0, b1 = self._read(2)
            opcode = b0 & 0x0F
            n = b1 & 0x7F
            if n == 126:
                n = struct.unpack("!H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack("!Q", self._read(8))[0]
            payload = self._read(n) if n else b""
            if opcode == 0x1:
                return payload.decode()
            if opcode == 0x8:
                raise IOError("对端关闭了调试连接")
            if opcode == 0x9:               # ping -> pong
                self.sock.sendall(bytes([0x8A, 0x80 | len(payload)]) + os.urandom(4) + payload)
            # 其它帧（binary/pong）直接丢弃

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class CDP:
    def __init__(self, ws: WS) -> None:
        self.ws = ws
        self.next_id = 0
        self.errors: list[str] = []

    def call(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        mid = self.next_id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                return msg
            if msg.get("method") == "Runtime.exceptionThrown":
                desc = msg["params"]["exceptionDetails"].get("exception", {}).get("description", "")
                self.errors.append(desc.splitlines()[0] if desc else "exception")

    def js(self, expr: str):
        res = self.call("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        result = res.get("result", {})
        if result.get("exceptionDetails"):
            raise RuntimeError("页面求值出错: " + json.dumps(result["exceptionDetails"])[:200])
        return result.get("result", {}).get("value")

    def mouse(self, kind: str, x: float, y: float) -> None:
        self.call("Input.dispatchMouseEvent", {
            "type": kind, "x": x, "y": y, "button": "left", "clickCount": 1,
        })


# ---------------------------------------------------------------- 启动与收尾
def find_chrome() -> str:
    for path in CHROME_CANDIDATES:
        if os.path.exists(path):
            return path
    raise SystemExit("找不到 Chrome/Chromium，可用 --chrome 指定路径")


def wait_for_target(port: int, timeout: float = 25.0) -> str:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as fh:
                for target in json.load(fh):
                    if target.get("type") == "page" and target.get("webSocketDebuggerUrl"):
                        return target["webSocketDebuggerUrl"]
        except Exception as exc:            # noqa: BLE001 - 启动期什么都可能发生
            last = exc
        time.sleep(0.25)
    raise SystemExit(f"等不到调试目标（{last}）")


def run(seconds: float, palette: int, headful: bool, chrome: str, size: tuple[int, int],
        baseline: bool = False) -> int:
    view_w, view_h = size
    port = 9333
    profile = tempfile.mkdtemp(prefix="dsh-soak-")
    url = "about:blank" if baseline else f"{GAME_URL}?autostart&palette={palette}"
    args = [
        chrome,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile}",
        f"--window-size={view_w},{view_h}",
        "--no-first-run",
        "--disable-crash-reporter",
    ]
    if headful:
        args += ["--disable-gpu"]
    else:
        args += ["--headless=new", "--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
    args.append(url)

    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    try:
        ws = WS("127.0.0.1", port, wait_for_target(port).split(f"127.0.0.1:{port}", 1)[1])
        cdp = CDP(ws)
        cdp.call("Runtime.enable")
        cdp.call("Emulation.setDeviceMetricsOverride", {
            "width": view_w, "height": view_h, "deviceScaleFactor": 1, "mobile": False,
        })
        time.sleep(1.0)

        if not baseline and not cdp.js("!!(window.__stardust && window.__stardust.startGame)"):
            raise SystemExit("游戏没加载起来（window.__stardust 不存在）")

        # 帧计数：和游戏自己抢一帧，只为了量 fps
        cdp.js(
            "window.__frames = 0; window.__t0 = performance.now();"
            "(function tick(){ window.__frames++; requestAnimationFrame(tick); })();"
        )

        what = "空页面基线" if baseline else f"配色 {palette}"
        print(f"跑 {seconds:.0f}s · {what} · {view_w}x{view_h} …", flush=True)
        cx, cy = view_w / 2, view_h / 2
        start = time.time()
        while time.time() - start < seconds:
            t = time.time() - start
            # 绕圈飞：按住不放，光标绕着屏幕中心转
            x = cx + math.cos(t * 0.85) * 400
            y = cy + math.sin(t * 0.85) * 400
            cdp.mouse("mousePressed", x, y)
            cdp.mouse("mouseMoved", x, y)
            time.sleep(0.06)

        if baseline:
            fps = cdp.js("Math.round(window.__frames / ((performance.now() - window.__t0) / 1000))")
            print(f"\n空页面基线：{fps} fps")
            print("（这个数字是这台机器/这个浏览器当前的渲染上限，用来判断掉帧是游戏负载还是环境）")
            return 0

        stats = json.loads(cdp.js(
            "JSON.stringify({"
            " fps: Math.round(window.__frames / ((performance.now() - window.__t0) / 1000)),"
            " score: __stardust.G.score, kills: __stardust.G.kills,"
            " lv: __stardust.G.weaponLv, sector: __stardust.G.sector,"
            " enemies: __stardust.enemies.length, motes: __stardust.motes.length,"
            " drones: __stardust.drones.length,"
            " fortHp: __stardust.fort ? Math.round(__stardust.fort.hp) : 0,"
            " fortAlive: __stardust.fort ? __stardust.fort.alive : false,"
            " palette: __stardust.palette().id"
            "})"
        ))
        print("\n运行结果")
        print(f"  配色        {stats['palette']}")
        print(f"  帧率        {stats['fps']} fps")
        print(f"  分数        {stats['score']}（LV.{stats['lv']}，第 {stats['sector']} 星区）")
        print(f"  击杀        {stats['kills']}")
        print(f"  场上        {stats['enemies']} 敌机 · {stats['motes']} 星尘 · {stats['drones']} 护航机")
        print(f"  堡垒        {'存活 ' + str(stats['fortHp']) + ' HP' if stats['fortAlive'] else '已被摧毁'}")
        if cdp.errors:
            print("\nJS 报错：")
            for err in cdp.errors[:5]:
                print("  " + err)
            return 1
        print("\n  没有 JS 报错")
        return 0
    finally:
        if ws is not None:
            ws.close()
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        shutil.rmtree(profile, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="用 Python 驱动星尘港湾跑一段并测量帧率")
    parser.add_argument("--seconds", type=float, default=12.0, help="跑多久（默认 12 秒）")
    parser.add_argument("--palette", type=int, default=1, choices=[1, 2, 3],
                        help="1 极光青 / 2 绯红脉冲 / 3 琥珀星火")
    parser.add_argument("--size", default="1440x900", help="画布分辨率，例如 1440x900 / 1280x720")
    parser.add_argument("--headful", action="store_true", help="开一个真窗口看它跑")
    parser.add_argument("--baseline", action="store_true",
                        help="跑一个空页面量基线帧率，用来区分环境限制和游戏负载")
    parser.add_argument("--chrome", default=None, help="Chrome 可执行文件路径")
    args = parser.parse_args()
    try:
        view_w, view_h = (int(v) for v in args.size.lower().split("x"))
    except ValueError:
        raise SystemExit("--size 需要形如 1440x900")
    return run(args.seconds, args.palette, args.headful, args.chrome or find_chrome(), (view_w, view_h),
               args.baseline)


if __name__ == "__main__":
    sys.exit(main())
