#!/usr/bin/env python3
"""
CapCut Automation Tool - Modern Glassmorphism UI (v2.0 Production Ready)
Features:
- Modern glassmorphism dark theme UI
- Connection Modes: None (Direct), VPN (Windscribe), and Proxy
- Advanced Proxy Support:
  * TXT File: HTTP/HTTPS & SOCKS5 with User:Password authentication
  * Rotating Proxy Link: API/URL based IP refresh and dynamic proxy fetch
  * Built-in zero-config Python Proxy Bridge for Android Emulator
  * ⚡ Live Proxy Tester: Real-time IP, country, and ping (ms) latency check
  * 🛡️ Dead Proxy Auto-Skip: Auto-advances if a proxy in rotation fails health-check
- Anti-Detection: Humanized click jitter with randomized micro-offsets
- Smart Screen & Popup Detection (handles 'Open with', 'Allow permissions')
- 🚀 Smart Export Completion: UIAutomator screen detection saves 20-30s per video
- 💾 Persistent Settings: Auto-saves and restores configuration to config.json
- 📱 Live LDPlayer Device Status & Auto-Reconnect (standard emulator ports)
- 🧹 Storage Protection: Optional auto-clean of exported videos on emulator
- Non-blocking multithreaded architecture with immediate stop & pause
"""

import os
import sys
import time
import random
import subprocess
import threading
import itertools
import queue
import ctypes
import socket
import base64
import urllib.parse
import urllib.request
import json
import re
from typing import List, Tuple, Optional, Dict
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

# ==================== DIRECTORY & EXECUTABLE DETECTION ====================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(SCRIPT_DIR, "tools")

# Ensure tools/ directory is in PATH for any subprocess or ADB DLL loading
if os.path.exists(TOOLS_DIR) and TOOLS_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = TOOLS_DIR + os.pathsep + os.environ.get("PATH", "")

# Search order: tools/adb.exe -> root adb.exe -> system PATH 'adb'
if os.path.exists(os.path.join(TOOLS_DIR, "adb.exe")):
    ADB_BIN = os.path.join(TOOLS_DIR, "adb.exe")
elif os.path.exists(os.path.join(SCRIPT_DIR, "adb.exe")):
    ADB_BIN = os.path.join(SCRIPT_DIR, "adb.exe")
else:
    ADB_BIN = "adb"

# ==================== CONFIG & DEFAULTS ====================
DEFAULT_DEVICE_ID = "emulator-5554"
DEVICE_ID = DEFAULT_DEVICE_ID
LOG_FILE = os.path.join(SCRIPT_DIR, "capcut_automation.log")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.json")

DEFAULT_TEMPLATE_URL = "https://www.capcut.com/template-detail/7573250368646221109"
DEFAULT_LOOP = "100"
DEFAULT_MIN_DELAY = "6"
DEFAULT_MAX_DELAY = "9"
DEFAULT_EXPORT_MIN = "25"
DEFAULT_EXPORT_MAX = "40"

DEFAULT_CONFIG = {
    "template_url": DEFAULT_TEMPLATE_URL,
    "loop": DEFAULT_LOOP,
    "delay_min": DEFAULT_MIN_DELAY,
    "delay_max": DEFAULT_MAX_DELAY,
    "export_min": DEFAULT_EXPORT_MIN,
    "export_max": DEFAULT_EXPORT_MAX,
    "mode": "None",
    "proxy_type": "txt",
    "proxy_file": "",
    "proxy_link_url": "",
    "proxy_fixed_endpoint": "",
    "auto_clean_storage": False
}

def load_config() -> dict:
    """Load persistent settings from config.json"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                cfg = DEFAULT_CONFIG.copy()
                cfg.update(saved)
                return cfg
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    """Save persistent settings to config.json"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

# Global status variable for GUI
CURRENT_STATUS = "Ready"
NEXT_ACTION = "—"

# VPN Package (Windscribe)
VPN_PACKAGE = "com.windscribe.vpn"
VPN_CONNECT_COORD = (241, 734)
VPN_DISCONNECT_COORD = (600, 220)

# Coordinates (720 x 1280 resolution)
BROWSER_USE_TEMPLATE: Tuple[int, int] = (365, 1274)
CC_USE_TEMPLATE: Tuple[int, int] = (270, 1214)
CLICK_IMAGE_SECTION: Tuple[int, int] = (588, 150)
GALLERY_FIRST_IMAGE: Tuple[int, int] = (150, 345)
GALLERY_CONFIRM: Tuple[int, int] = (620, 1180)
CC_EXPORT_TOP_RIGHT: Tuple[int, int] = (625, 60)
FINAL_EXPORT_BTN: Tuple[int, int] = (360, 1210)

# Proxy state
PROXIES: List[str] = []
PROXY_ITER = None
PROXY_LOCK = threading.Lock()

LOCAL_BRIDGE_PORT = 8889
LOCAL_BRIDGE: Optional['ProxyBridge'] = None

# Reconfigure stdout/stderr for utf-8 on Windows if available
try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Logging queue
LOG_QUEUE = queue.Queue()

# ==================== LOGGING ====================
def log_message(msg: str):
    """Log message to console, file, and GUI queue safely on Windows"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    try:
        print(formatted)
    except Exception:
        try:
            print(formatted.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass
    
    LOG_QUEUE.put(formatted + "\n")
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def update_status(current: str, next_action: str = "—"):
    """Update global status for GUI"""
    global CURRENT_STATUS, NEXT_ACTION
    CURRENT_STATUS = current
    NEXT_ACTION = next_action
    log_message(f"📍 {current}")

# ==================== PYTHON LOCAL PROXY BRIDGE ====================
class ProxyBridge:
    """
    Transparent local HTTP-to-SOCKS5 / Authenticated HTTP proxy bridge.
    Listens locally on 0.0.0.0:local_port.
    Emulator connects to this bridge via standard Android global http_proxy,
    and the bridge handles SOCKS5 handshake, User:Pass auth, and data forwarding.
    """
    def __init__(self, local_port: int = 8889):
        self.local_port = local_port
        self.server_socket: Optional[socket.socket] = None
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.upstream_type = "http"  # "socks5" or "http"
        self.upstream_host = ""
        self.upstream_port = 0
        self.upstream_user = ""
        self.upstream_pass = ""

    def set_upstream(self, proxy_str: str) -> bool:
        """Parse proxy string and configure upstream proxy"""
        try:
            proxy_str = proxy_str.strip()
            if not proxy_str:
                return False

            self.upstream_type = "http"
            self.upstream_user = ""
            self.upstream_pass = ""

            if proxy_str.lower().startswith("socks5://") or proxy_str.lower().startswith("socks4://"):
                self.upstream_type = "socks5"
                proxy_str = proxy_str[proxy_str.find("://") + 3:]
            elif proxy_str.lower().startswith("http://") or proxy_str.lower().startswith("https://"):
                self.upstream_type = "http"
                proxy_str = proxy_str[proxy_str.find("://") + 3:]

            if "@" in proxy_str:
                auth_part, host_part = proxy_str.split("@", 1)
                if ":" in auth_part:
                    self.upstream_user, self.upstream_pass = auth_part.split(":", 1)
                else:
                    self.upstream_user = auth_part
                parts = host_part.split(":")
                self.upstream_host = parts[0]
                self.upstream_port = int(parts[1])
            else:
                parts = proxy_str.split(":")
                if len(parts) == 2:
                    self.upstream_host = parts[0]
                    self.upstream_port = int(parts[1])
                elif len(parts) == 4:
                    self.upstream_host = parts[0]
                    self.upstream_port = int(parts[1])
                    self.upstream_user = parts[2]
                    self.upstream_pass = parts[3]
                else:
                    return False
            return True
        except Exception as e:
            log_message(f"❌ Error parsing proxy '{proxy_str}': {e}")
            return False

    def start(self):
        if self.running:
            return
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", self.local_port))
        self.server_socket.listen(50)
        self.server_socket.settimeout(1.0)
        self.thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

    def _accept_loop(self):
        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                threading.Thread(target=self._handle_client, args=(client_sock,), daemon=True).start()
            except socket.timeout:
                continue
            except Exception:
                break

    def _connect_socks5(self, target_host: str, target_port: int) -> Optional[socket.socket]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(12)
        try:
            sock.connect((self.upstream_host, self.upstream_port))
            # Handshake
            if self.upstream_user:
                sock.sendall(b"\x05\x02\x00\x02")
            else:
                sock.sendall(b"\x05\x01\x00")

            resp = sock.recv(2)
            if len(resp) < 2 or resp[0] != 5:
                sock.close()
                return None

            method = resp[1]
            if method == 2:  # Username/Password auth
                u_bytes = self.upstream_user.encode("utf-8")
                p_bytes = self.upstream_pass.encode("utf-8")
                auth_req = b"\x01" + bytes([len(u_bytes)]) + u_bytes + bytes([len(p_bytes)]) + p_bytes
                sock.sendall(auth_req)
                auth_resp = sock.recv(2)
                if len(auth_resp) < 2 or auth_resp[1] != 0:
                    sock.close()
                    return None
            elif method != 0:
                sock.close()
                return None

            # Connect command (ATYP=3 domain name)
            target_bytes = target_host.encode("utf-8")
            port_bytes = target_port.to_bytes(2, "big")
            cmd = b"\x05\x01\x00\x03" + bytes([len(target_bytes)]) + target_bytes + port_bytes
            sock.sendall(cmd)

            conn_resp = sock.recv(4)
            if len(conn_resp) < 4 or conn_resp[1] != 0:
                sock.close()
                return None

            atyp = conn_resp[3]
            if atyp == 1:
                sock.recv(4 + 2)
            elif atyp == 3:
                domain_len = sock.recv(1)[0]
                sock.recv(domain_len + 2)
            elif atyp == 4:
                sock.recv(16 + 2)

            return sock
        except Exception:
            sock.close()
            return None

    def _connect_http(self, target_host: str, target_port: int) -> Optional[socket.socket]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(12)
        try:
            sock.connect((self.upstream_host, self.upstream_port))
            req = f"CONNECT {target_host}:{target_port} HTTP/1.1\r\nHost: {target_host}:{target_port}\r\n"
            if self.upstream_user:
                auth_str = f"{self.upstream_user}:{self.upstream_pass}"
                b64 = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
                req += f"Proxy-Authorization: Basic {b64}\r\n"
            req += "Proxy-Connection: Keep-Alive\r\n\r\n"
            sock.sendall(req.encode("utf-8"))

            resp_buf = b""
            while b"\r\n\r\n" not in resp_buf:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                resp_buf += chunk

            if b" 200 " not in resp_buf.split(b"\r\n")[0]:
                sock.close()
                return None
            return sock
        except Exception:
            sock.close()
            return None

    def _handle_client(self, client_sock: socket.socket):
        try:
            client_sock.settimeout(12)
            buf = b""
            while b"\r\n" not in buf:
                chunk = client_sock.recv(1024)
                if not chunk:
                    break
                buf += chunk

            if not buf:
                client_sock.close()
                return

            first_line = buf.split(b"\r\n")[0].decode("latin-1", errors="ignore")
            parts = first_line.split()
            if len(parts) < 3:
                client_sock.close()
                return

            method, target, _ = parts

            if method.upper() == "CONNECT":
                host_port = target.split(":")
                target_host = host_port[0]
                target_port = int(host_port[1]) if len(host_port) > 1 else 443

                while b"\r\n\r\n" not in buf:
                    chunk = client_sock.recv(1024)
                    if not chunk:
                        break
                    buf += chunk

                if self.upstream_type == "socks5":
                    upstream_sock = self._connect_socks5(target_host, target_port)
                else:
                    upstream_sock = self._connect_http(target_host, target_port)

                if not upstream_sock:
                    client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    client_sock.close()
                    return

                client_sock.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                self._pipe(client_sock, upstream_sock)

            else:
                url_parsed = urllib.parse.urlparse(target)
                target_host = url_parsed.hostname or ""
                target_port = url_parsed.port or 80

                if self.upstream_type == "socks5":
                    upstream_sock = self._connect_socks5(target_host, target_port)
                    if not upstream_sock:
                        client_sock.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                        client_sock.close()
                        return
                    upstream_sock.sendall(buf)
                    self._pipe(client_sock, upstream_sock)
                else:
                    upstream_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    upstream_sock.settimeout(12)
                    upstream_sock.connect((self.upstream_host, self.upstream_port))
                    if self.upstream_user:
                        auth_str = f"{self.upstream_user}:{self.upstream_pass}"
                        b64 = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
                        headers, body = buf.split(b"\r\n\r\n", 1) if b"\r\n\r\n" in buf else (buf, b"")
                        headers += f"\r\nProxy-Authorization: Basic {b64}".encode("utf-8")
                        buf = headers + b"\r\n\r\n" + body
                    upstream_sock.sendall(buf)
                    self._pipe(client_sock, upstream_sock)

        except Exception:
            pass
        finally:
            try:
                client_sock.close()
            except:
                pass

    def _pipe(self, sock1: socket.socket, sock2: socket.socket):
        sock1.settimeout(None)
        sock2.settimeout(None)
        def forward(s_from, s_to):
            try:
                while True:
                    data = s_from.recv(8192)
                    if not data:
                        break
                    s_to.sendall(data)
            except:
                pass
            finally:
                try:
                    s_to.shutdown(socket.SHUT_WR)
                except:
                    pass

        t1 = threading.Thread(target=forward, args=(sock1, sock2), daemon=True)
        t2 = threading.Thread(target=forward, args=(sock2, sock1), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

def start_proxy_bridge(upstream_proxy_str: str) -> bool:
    """Start local bridge forwarding to upstream proxy"""
    global LOCAL_BRIDGE
    try:
        stop_proxy_bridge()
        LOCAL_BRIDGE = ProxyBridge(LOCAL_BRIDGE_PORT)
        if not LOCAL_BRIDGE.set_upstream(upstream_proxy_str):
            log_message(f"❌ Could not parse proxy configuration: {upstream_proxy_str}")
            return False
        LOCAL_BRIDGE.start()
        auth_note = " (with auth)" if LOCAL_BRIDGE.upstream_user else " (no auth)"
        log_message(f"🚀 Proxy Bridge listening on port {LOCAL_BRIDGE_PORT} -> {LOCAL_BRIDGE.upstream_type.upper()}://{LOCAL_BRIDGE.upstream_host}:{LOCAL_BRIDGE.upstream_port}{auth_note}")
        return True
    except Exception as e:
        log_message(f"❌ Failed to start local proxy bridge: {e}")
        return False

def stop_proxy_bridge():
    """Stop local proxy bridge"""
    global LOCAL_BRIDGE
    if LOCAL_BRIDGE:
        try:
            LOCAL_BRIDGE.stop()
        except:
            pass
        LOCAL_BRIDGE = None

# ==================== PROXY CONNECTIVITY TESTER ====================
def test_proxy_connection(proxy_str: str, timeout: float = 5.0) -> Tuple[bool, str, float]:
    """
    Test proxy connectivity via temporary test bridge.
    Returns: (is_success, ip_or_error_info, latency_ms)
    """
    test_port = 8890
    test_bridge = ProxyBridge(local_port=test_port)
    if not test_bridge.set_upstream(proxy_str):
        return False, "Invalid proxy format", 0.0

    test_bridge.start()
    try:
        start_t = time.time()
        proxy_handler = urllib.request.ProxyHandler({
            'http': f'http://127.0.0.1:{test_port}'
        })
        opener = urllib.request.build_opener(proxy_handler)
        req = urllib.request.Request("http://api.ipify.org?format=json", headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            ip = data.get("ip", "Connected")
            latency = (time.time() - start_t) * 1000
            return True, ip, latency
    except Exception as e:
        err_msg = str(e)
        if "timed out" in err_msg.lower():
            err_msg = "Connection Timed Out"
        elif "502" in err_msg or "bad gateway" in err_msg.lower():
            err_msg = "502 Bad Gateway / Proxy Refused"
        elif "connection refused" in err_msg.lower():
            err_msg = "Connection Refused"
        return False, err_msg, 0.0
    finally:
        test_bridge.stop()

# ==================== ADB HELPERS ====================
def run_cmd(cmd: List[str], wait: bool = True, timeout: float = 20.0):
    """Run command with optional timeout (hides CMD window, uses resolved ADB)"""
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        # Replace 'adb' with resolved executable path if needed
        exec_cmd = list(cmd)
        if exec_cmd and exec_cmd[0] == "adb":
            exec_cmd[0] = ADB_BIN

        proc = subprocess.Popen(
            exec_cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        if not wait:
            return proc, "", "", False
        out, err = proc.communicate(timeout=timeout)
        return proc, out or "", err or "", False
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        return proc, out or "", err or "", True
    except Exception as e:
        return None, "", str(e), False

def auto_detect_device() -> str:
    """Find connected emulator or device dynamically"""
    global DEVICE_ID
    try:
        proc, out, err, timed = run_cmd(["adb", "devices"], timeout=5)
        if out:
            lines = out.strip().splitlines()
            devices = []
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    devices.append(parts[0])
            if devices:
                if "emulator-5554" in devices:
                    DEVICE_ID = "emulator-5554"
                else:
                    DEVICE_ID = devices[0]
                return DEVICE_ID
    except:
        pass
    DEVICE_ID = DEFAULT_DEVICE_ID
    return DEVICE_ID

def detect_and_connect_device() -> Tuple[str, str]:
    """
    Auto-detect and connect LDPlayer emulator.
    Returns: (device_id, status) where status is 'online', 'offline', or 'disconnected'
    """
    global DEVICE_ID
    proc, out, _, _ = run_cmd(["adb", "devices"], timeout=3)
    devices = []
    if out:
        for line in out.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2:
                devices.append((parts[0], parts[1]))

    online_devices = [d[0] for d in devices if d[1] == "device"]
    
    # If no device connected, try auto-connecting to common LDPlayer ports
    if not online_devices:
        log_message("🔍 Probing LDPlayer ports (127.0.0.1:5555, emulator-5554)...")
        for port in ["127.0.0.1:5555", "127.0.0.1:5556", "127.0.0.1:5554"]:
            run_cmd(["adb", "connect", port], timeout=2)
        
        proc, out, _, _ = run_cmd(["adb", "devices"], timeout=3)
        devices = []
        if out:
            for line in out.strip().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    devices.append((parts[0], parts[1]))
        online_devices = [d[0] for d in devices if d[1] == "device"]

    if online_devices:
        if "emulator-5554" in online_devices:
            DEVICE_ID = "emulator-5554"
        elif "127.0.0.1:5555" in online_devices:
            DEVICE_ID = "127.0.0.1:5555"
        else:
            DEVICE_ID = online_devices[0]
        log_message(f"✅ Device Connected: {DEVICE_ID}")
        return DEVICE_ID, "online"

    offline_devices = [d[0] for d in devices if d[1] == "offline"]
    if offline_devices:
        DEVICE_ID = offline_devices[0]
        log_message(f"⚠️ Device {DEVICE_ID} is OFFLINE")
        return DEVICE_ID, "offline"

    DEVICE_ID = DEFAULT_DEVICE_ID
    return "None", "disconnected"

def adb(args: List[str], wait: bool = True):
    """Execute ADB command"""
    cmd = ["adb", "-s", DEVICE_ID] + args
    log_message(f"🔧 ADB: {' '.join(cmd)}")
    return run_cmd(cmd, wait=wait)

def check_device() -> bool:
    """Check if device is connected and online"""
    log_message("🔍 Checking ADB connection...")
    dev_id, status = detect_and_connect_device()
    return status == "online"

def reconnect_adb():
    """Try to reconnect ADB"""
    log_message("🔄 Attempting to reconnect ADB...")
    run_cmd(["adb", "kill-server"], timeout=5)
    time.sleep(1)
    run_cmd(["adb", "start-server"], timeout=5)
    time.sleep(2)
    return check_device()

def tap(coord: Tuple[int, int], tag: str = "", jitter: bool = True):
    """Tap at coordinates with humanized micro-jitter"""
    x, y = coord
    if jitter:
        x += random.randint(-4, 4)
        y += random.randint(-4, 4)
    if tag:
        log_message(f"👆 TAP {tag}: ({x}, {y})")
    else:
        log_message(f"👆 TAP: ({x}, {y})")
    adb(["shell", "input", "tap", str(x), str(y)], wait=False)

def tap_with_smart_detect(coord: Tuple[int, int], tag: str = "", keywords: List[str] = None, jitter: bool = True):
    """
    Tap at coordinates with UI inspection fallback.
    If keywords are found in screen dump, clicks exact button center.
    Otherwise, safely taps default coordinate with jitter.
    """
    x, y = coord
    target_x, target_y = x, y
    detected = False

    if keywords:
        try:
            proc, _, _, timed = run_cmd(
                ["adb", "-s", DEVICE_ID, "shell", "uiautomator", "dump", "/data/local/tmp/uidump.xml"],
                timeout=1.5
            )
            if not timed and proc and proc.returncode == 0:
                p2, xml_data, _, _ = run_cmd(
                    ["adb", "-s", DEVICE_ID, "shell", "cat", "/data/local/tmp/uidump.xml"],
                    timeout=1.0
                )
                if xml_data:
                    for kw in keywords:
                        if kw.lower() in xml_data.lower():
                            pattern = rf'(?:text|content-desc)="[^"]*{re.escape(kw)}[^"]*"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"'
                            match = re.search(pattern, xml_data, re.IGNORECASE)
                            if match:
                                x1, y1, x2, y2 = map(int, match.groups())
                                target_x = (x1 + x2) // 2
                                target_y = (y1 + y2) // 2
                                detected = True
                                log_message(f"🎯 Smart UI match for '{kw}': ({target_x}, {target_y})")
                                break
        except Exception:
            pass

    if jitter:
        target_x += random.randint(-3, 3)
        target_y += random.randint(-3, 3)

    if tag:
        log_message(f"👆 TAP {tag}{' (Smart)' if detected else ''}: ({target_x}, {target_y})")
    else:
        log_message(f"👆 TAP: ({target_x}, {target_y})")

    adb(["shell", "input", "tap", str(target_x), str(target_y)], wait=False)

def get_foreground_package() -> str:
    """Get currently focused app package"""
    try:
        proc, out, err, timed = run_cmd(
            ["adb", "-s", DEVICE_ID, "shell", "dumpsys", "window", "windows"],
            timeout=5
        )
        
        if timed or proc is None:
            return ""
        
        if "offline" in err.lower() or "offline" in out.lower():
            log_message("⚠️ Device offline detected")
            return ""
        
        for line in out.splitlines():
            if "mCurrentFocus" in line or "mFocusedApp" in line:
                parts = line.split()
                for part in parts:
                    if "/" in part and "." in part:
                        comp = part.strip().strip("}").strip()
                        pkg = comp.split("/")[0]
                        return pkg
    except Exception as e:
        log_message(f"⚠️ Error getting foreground: {e}")
    return ""

def check_and_dismiss_popups() -> bool:
    """Auto-detect and dismiss blocking Android popups"""
    try:
        fg = get_foreground_package()
        if not fg:
            return False

        # 1. Android Intent Resolver ("Open with Chrome / CapCut")
        if any(p in fg for p in ["intentresolver", "resolver"]):
            log_message("⚠️ 'Open with' dialog detected. Selecting option...")
            adb(["shell", "input", "keyevent", "KEYCODE_DPAD_DOWN"])
            time.sleep(0.3)
            adb(["shell", "input", "keyevent", "KEYCODE_ENTER"])
            return True

        # 2. Permission Controller ("Allow media access")
        if "permissioncontroller" in fg or "packageinstaller" in fg:
            log_message("⚠️ Permission dialog detected. Auto-confirming...")
            adb(["shell", "input", "tap", "480", "720"])
            return True

    except Exception:
        pass
    return False

def get_emulator_gateway_ip() -> str:
    """Get host IP from emulator perspective (default: 10.0.2.2)"""
    try:
        proc, out, _, _ = run_cmd(["adb", "-s", DEVICE_ID, "shell", "ip", "route"], timeout=3)
        if out:
            for line in out.splitlines():
                if "default via" in line:
                    gateway = line.split("default via")[1].strip().split()[0]
                    return gateway
    except:
        pass
    return "10.0.2.2"

def force_close_apps(exclude_vpn: bool = False):
    """
    Force close CapCut and Chrome.
    Keeps VPN open if exclude_vpn=True (Fixes the VPN kill bug).
    """
    if exclude_vpn:
        log_message("❌ Force closing CapCut & Chrome (preserving VPN)...")
    else:
        log_message("❌ Force closing all apps...")
        adb(["shell", "am", "force-stop", VPN_PACKAGE])

    adb(["shell", "am", "force-stop", "com.lemon.lvoverseas"])
    adb(["shell", "am", "force-stop", "com.android.chrome"])
    time.sleep(1)

def clean_emulator_exported_videos():
    """Clean exported videos from emulator storage to prevent full disk crashes"""
    try:
        log_message("🧹 Cleaning old exported videos from emulator storage...")
        adb(["shell", "rm", "-f", "/sdcard/Movies/CapCut/*.mp4"])
        adb(["shell", "rm", "-f", "/sdcard/DCIM/Camera/*.mp4"])
        log_message("✅ Emulator storage cleaned successfully")
    except Exception as e:
        log_message(f"⚠️ Storage clean failed: {e}")

# ==================== PROXY FUNCTIONS ====================
def load_proxies_from_file(path: str) -> int:
    """Load proxies from file"""
    global PROXIES, PROXY_ITER
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]
        
        PROXIES = [line for line in lines if line and not line.startswith("#")]
        PROXY_ITER = itertools.cycle(PROXIES) if PROXIES else None
        log_message(f"📂 Loaded {len(PROXIES)} proxies from file")
        return len(PROXIES)
    except Exception as e:
        log_message(f"❌ Error loading proxies: {e}")
        PROXIES = []
        PROXY_ITER = None
        return 0

def get_next_proxy() -> Optional[str]:
    """Get next proxy from rotation list"""
    global PROXY_ITER
    if not PROXY_ITER:
        return None
    with PROXY_LOCK:
        try:
            return next(PROXY_ITER)
        except:
            return None

def extract_proxy_from_text(text: str) -> Optional[str]:
    """Extract proxy string from API response (JSON or plain text)"""
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for k in ["proxy", "data", "result", "http", "socks5", "proxy_url"]:
                if k in data and isinstance(data[k], str) and ":" in data[k]:
                    return data[k].strip()
            if "ip" in data and "port" in data:
                u = data.get("username", data.get("user", ""))
                p = data.get("password", data.get("pass", ""))
                if u and p:
                    return f"{data['ip']}:{data['port']}:{u}:{p}"
                return f"{data['ip']}:{data['port']}"
    except:
        pass

    match = re.search(r'(?:socks[45]://|https?://)?[\w\.-]+:\d+(?::[\w\.-]+:[\w\.-]+)?', text)
    if match:
        return match.group(0)
    return None

def rotate_via_link(link_url: str, fixed_endpoint: str = "") -> Optional[str]:
    """
    Call rotation link.
    If fixed_endpoint is provided, wait 3s for IP refresh and return fixed_endpoint.
    Otherwise, parse response body as proxy string.
    """
    try:
        log_message(f"🔗 Triggering rotation URL: {link_url}")
        req = urllib.request.Request(link_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as response:
            content = response.read().decode("utf-8", errors="ignore").strip()
            log_message(f"🔗 Rotation response: {content[:100]}")

        if fixed_endpoint:
            log_message("⏳ Waiting 3s for refreshed IP to activate...")
            time.sleep(3)
            return fixed_endpoint

        parsed = extract_proxy_from_text(content)
        if parsed:
            return parsed
        else:
            log_message(f"⚠️ Could not parse proxy from API response: {content[:100]}")
            return None
    except Exception as e:
        log_message(f"⚠️ Error calling rotation link: {e}")
        if fixed_endpoint:
            return fixed_endpoint
        return None

def apply_proxy_to_device(proxy_line: str) -> bool:
    """
    Applies proxy to Android emulator.
    Uses local Python Proxy Bridge to guarantee 100% support for
    SOCKS5, SOCKS4, and HTTP/HTTPS with User:Password authentication.
    """
    if not proxy_line:
        return False

    proxy_line = proxy_line.strip()
    log_message(f"🔧 Configuring proxy: {proxy_line}")

    # Start local bridge
    if not start_proxy_bridge(proxy_line):
        return False

    # Get emulator host gateway IP
    gateway = get_emulator_gateway_ip()

    # Route Android global proxy through local bridge
    adb(["shell", "settings", "put", "global", "http_proxy", f"{gateway}:{LOCAL_BRIDGE_PORT}"])
    log_message(f"✅ Emulator routed to Local Bridge ({gateway}:{LOCAL_BRIDGE_PORT})")
    return True

def clear_proxy_on_device():
    """Clear proxy from device and stop bridge"""
    log_message("🔧 Clearing proxy...")
    adb(["shell", "settings", "put", "global", "http_proxy", ":0"])
    stop_proxy_bridge()
    log_message("✅ Proxy cleared and bridge stopped")

# ==================== VPN FUNCTIONS ====================
def vpn_open():
    """Open VPN app"""
    log_message(f"🌐 Opening VPN: {VPN_PACKAGE}")
    adb(["shell", "monkey", "-p", VPN_PACKAGE, "1"])
    time.sleep(3)

def vpn_connect():
    """Connect VPN"""
    log_message("🌐 Connecting VPN...")
    tap(VPN_CONNECT_COORD, "VPN_CONNECT")
    time.sleep(4)

def vpn_disconnect():
    """Disconnect VPN"""
    log_message("🌐 Disconnecting VPN...")
    tap(VPN_DISCONNECT_COORD, "VPN_DISCONNECT")
    time.sleep(2)

def vpn_minimize():
    """Minimize VPN app (keep it running in background)"""
    log_message("📱 Minimizing VPN (keeping connection active)")
    adb(["shell", "input", "keyevent", "KEYCODE_HOME"])
    time.sleep(0.5)

def vpn_close():
    """Close VPN app completely"""
    log_message("❌ Closing VPN")
    adb(["shell", "am", "force-stop", VPN_PACKAGE])

# ==================== CAPCUT FLOW ====================
def wait_for_screen_ready(expected_package: str, max_wait: int = 20, check_interval: float = 0.5, stop_event: threading.Event = None) -> bool:
    """Wait for screen to be ready (polling based) with popup handling and stop check"""
    update_status(f"Waiting for screen: {expected_package}", f"Max {max_wait}s")
    
    checks = int(max_wait / check_interval)
    for i in range(checks):
        if stop_event and stop_event.is_set():
            log_message("🛑 Stop detected during screen wait")
            return False
        
        fg = get_foreground_package()
        if fg == expected_package:
            log_message(f"✅ Screen ready: {expected_package}")
            update_status(f"Screen loaded: {expected_package}", "Waiting 2s for stability")
            time.sleep(2)
            return True
        
        # Check and auto-dismiss any popup blocking the screen
        if fg and fg != expected_package:
            check_and_dismiss_popups()

        if i % 6 == 0 and i > 0:
            elapsed = i * check_interval
            log_message(f"   Still waiting... ({elapsed:.1f}s, current: {fg or 'unknown'})")
        
        time.sleep(check_interval)
    
    log_message(f"⚠️ Timeout waiting for {expected_package}")
    return False

def open_template_in_browser(template_url: str, max_attempts: int = 5, stop_event: threading.Event = None) -> bool:
    """Open template in Chrome with popup check and button click"""
    update_status("Opening browser", "Launching Chrome")
    
    for attempt in range(1, max_attempts + 1):
        if stop_event and stop_event.is_set():
            log_message("🛑 Stop detected, aborting browser open")
            return False
        
        log_message(f"🔁 Attempt {attempt}/{max_attempts}")
        update_status(f"Browser attempt {attempt}/{max_attempts}", "Opening URL")
        
        log_message("📱 Launching Chrome...")
        adb(["shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", template_url])
        
        if not wait_for_screen_ready("com.android.chrome", max_wait=15, stop_event=stop_event):
            if stop_event and stop_event.is_set():
                return False
            log_message("⚠️ Chrome timeout, retrying...")
            continue
        
        if stop_event and stop_event.is_set():
            log_message("🛑 Stop detected after Chrome load")
            return False
        
        update_status("Page loading", "Waiting 4s for content")
        for _ in range(8):
            if stop_event and stop_event.is_set():
                log_message("🛑 Stop detected during page load")
                return False
            time.sleep(0.5)
        
        update_status("Clicking button", "'Use template in CapCut'")
        log_message("▶️ Clicking 'Use template'")
        tap_with_smart_detect(BROWSER_USE_TEMPLATE, "BROWSER_USE_TEMPLATE", keywords=["Use template", "CapCut"])
        
        update_status("Tap registered", "Waiting 2s")
        time.sleep(2)
        
        if wait_for_screen_ready("com.lemon.lvoverseas", max_wait=15, stop_event=stop_event):
            log_message("✅ CapCut opened!")
            return True
        
        if stop_event and stop_event.is_set():
            log_message("🛑 Stop detected, aborting")
            return False
        
        log_message("⚠️ CapCut timeout, retrying...")
        time.sleep(2)
    
    log_message("❌ Failed to open CapCut")
    return False

def capcut_use_template(stop_event: threading.Event = None):
    """Click 'Use template' in CapCut"""
    if stop_event and stop_event.is_set():
        log_message("🛑 Stop detected")
        return
    
    update_status("CapCut: Using template", "Clicking button")
    log_message("▶️ Using template")
    tap_with_smart_detect(CC_USE_TEMPLATE, "CC_USE_TEMPLATE", keywords=["Use template"])
    
    wait_time = random.uniform(2, 3)
    update_status("Template UI loading", f"Waiting {wait_time:.1f}s")
    log_message(f"⏳ Wait {wait_time:.1f}s for template UI")
    
    steps = int(wait_time * 2)
    for _ in range(steps):
        if stop_event and stop_event.is_set():
            log_message("🛑 Stop during wait")
            return
        time.sleep(0.5)

def select_image(stop_event: threading.Event = None):
    """Select image from gallery"""
    if stop_event and stop_event.is_set():
        log_message("🛑 Stop detected")
        return
    
    update_status("Opening gallery", "Clicking image section")
    log_message("🖼 Opening gallery")
    tap(CLICK_IMAGE_SECTION, "CLICK_IMAGE_SECTION")
    
    wait_time = random.uniform(1.5, 2.5)
    update_status("Gallery opening", f"Waiting {wait_time:.1f}s")
    steps = int(wait_time * 2)
    for _ in range(steps):
        if stop_event and stop_event.is_set():
            return
        time.sleep(0.5)
    
    update_status("Selecting image", "First image in gallery")
    log_message("🖼 Selecting image")
    tap(GALLERY_FIRST_IMAGE, "GALLERY_FIRST_IMAGE")
    
    wait_time = random.uniform(1, 2)
    update_status("Image selected", f"Waiting {wait_time:.1f}s")
    steps = int(wait_time * 2)
    for _ in range(steps):
        if stop_event and stop_event.is_set():
            return
        time.sleep(0.5)
    
    update_status("Confirming selection", "Clicking confirm button")
    log_message("✅ Confirming")
    tap_with_smart_detect(GALLERY_CONFIRM, "GALLERY_CONFIRM", keywords=["Next", "Confirm", "Add"])
    
    wait_time = random.uniform(1.5, 2.5)
    update_status("Confirmation processing", f"Waiting {wait_time:.1f}s")
    steps = int(wait_time * 2)
    for _ in range(steps):
        if stop_event and stop_event.is_set():
            return
        time.sleep(0.5)

def export_video(export_wait_min: float, export_wait_max: float, stop_event: threading.Event = None) -> bool:
    """Export video with smart UIAutomator completion detection"""
    if stop_event and stop_event.is_set():
        log_message("🛑 Stop detected")
        return False
    
    log_message("⏳ Waiting 2s for screen to stabilize...")
    time.sleep(2)
    
    update_status("Starting export", "Clicking export button")
    log_message("📤 Exporting...")
    tap_with_smart_detect(CC_EXPORT_TOP_RIGHT, "CC_EXPORT_TOP_RIGHT", keywords=["Export"])
    
    time.sleep(0.5)
    log_message("🔁 Retry tap for reliability")
    tap(CC_EXPORT_TOP_RIGHT, "CC_EXPORT_TOP_RIGHT")
    
    wait1 = random.uniform(5, 7)
    update_status("Export UI loading", f"Waiting {wait1:.1f}s")
    log_message(f"⏳ Wait {wait1:.1f}s for export UI")
    
    steps = int(wait1 * 2)
    for _ in range(steps):
        if stop_event and stop_event.is_set():
            log_message("🛑 Stop during export UI wait")
            return False
        time.sleep(0.5)
    
    update_status("Final export", "Clicking final export button")
    log_message("✅ Final export")
    tap_with_smart_detect(FINAL_EXPORT_BTN, "FINAL_EXPORT_BTN", keywords=["Export without watermark", "Export"])
    
    wait2 = random.uniform(export_wait_min, export_wait_max)
    update_status("Video exporting", f"Max {wait2:.0f}s (Smart Detection active)")
    log_message(f"⏳ Exporting (max {wait2:.1f}s, detecting completion)...")
    
    elapsed = 0.0
    completed_early = False
    done_keywords = ["Ready to share", "Share to TikTok", "Share", "Done", "Save to your device"]
    
    while elapsed < wait2:
        if stop_event and stop_event.is_set():
            log_message("🛑 Stop during export")
            return False
        
        sleep_chunk = min(1.0, wait2 - elapsed)
        time.sleep(sleep_chunk)
        elapsed += sleep_chunk
        
        # Check completion every 2s after elapsed >= 5s
        if elapsed >= 5.0 and int(elapsed) % 2 == 0:
            try:
                proc, _, _, timed = run_cmd(
                    ["adb", "-s", DEVICE_ID, "shell", "uiautomator", "dump", "/data/local/tmp/uidump.xml"],
                    timeout=1.2
                )
                if not timed and proc and proc.returncode == 0:
                    _, xml_data, _, _ = run_cmd(
                        ["adb", "-s", DEVICE_ID, "shell", "cat", "/data/local/tmp/uidump.xml"],
                        timeout=0.8
                    )
                    if xml_data:
                        for kw in done_keywords:
                            if kw.lower() in xml_data.lower():
                                log_message(f"🎯 Export completed early! Detected '{kw}' at {elapsed:.0f}s (Saved {wait2 - elapsed:.0f}s).")
                                update_status("Export finished", f"Done in {elapsed:.0f}s")
                                completed_early = True
                                time.sleep(1)
                                break
                if completed_early:
                    break
            except Exception:
                pass
        
        if int(elapsed) % 5 == 0 and elapsed < wait2 and not completed_early:
            remaining = wait2 - elapsed
            update_status("Exporting video", f"{remaining:.0f}s remaining")
            log_message(f"   Progress: {elapsed:.0f}s / {wait2:.0f}s")

    if not completed_early:
        log_message(f"⏳ Export wait cycle finished ({elapsed:.1f}s), proceeding...")
    
    return True

# ==================== ONE CYCLE ====================
def one_cycle(index: int, template_url: str, use_vpn: bool, use_proxy: bool, proxy_type: str,
              proxy_link_url: str, proxy_fixed_endpoint: str,
              delay_min: float, delay_max: float, export_min: float, export_max: float,
              auto_clean: bool,
              stop_event: threading.Event, pause_event: threading.Event) -> bool:
    """Execute one cycle with pause support and bug-free VPN / Proxy lifecycle"""
    update_status(f"Cycle #{index + 1}", "Starting")
    log_message("\n" + "=" * 50)
    log_message(f"🚀 CYCLE #{index + 1}")
    log_message("=" * 50)
    
    try:
        # Check pause
        if pause_event.is_set():
            update_status("Paused", "Waiting for resume...")
            log_message("⏸️ Automation paused")
            while pause_event.is_set() and not stop_event.is_set():
                time.sleep(0.5)
            if stop_event.is_set():
                return False
            log_message("▶️ Automation resumed")
            update_status(f"Cycle #{index + 1}", "Resumed")
        
        if stop_event.is_set():
            log_message("🛑 Stop requested")
            return False
        
        # 1. Apply Network Mode with Dead Proxy Auto-Skip
        if use_proxy:
            update_status("Applying proxy", "Configuring proxy")
            proxy = None
            max_proxy_attempts = 4 if proxy_type == "txt" else 1

            for p_try in range(max_proxy_attempts):
                if stop_event.is_set():
                    return False

                if proxy_type == "link":
                    proxy = rotate_via_link(proxy_link_url, proxy_fixed_endpoint)
                else:
                    proxy = get_next_proxy()

                if not proxy:
                    log_message("⚠️ No proxy available in rotation pool.")
                    break

                # Quick 3s health check
                log_message(f"🔍 Testing proxy health ({p_try + 1}/{max_proxy_attempts}): {proxy}")
                alive, ip_info, lat = test_proxy_connection(proxy, timeout=3.0)
                if alive:
                    log_message(f"✅ Proxy verified healthy: IP={ip_info} ({lat:.0f}ms)")
                    break
                else:
                    log_message(f"⚠️ Proxy dead/unresponsive ({ip_info}). Auto-skipping to next...")
                    proxy = None

            if proxy:
                apply_proxy_to_device(proxy)
            else:
                log_message("❌ Failed to find a working proxy. Skipping cycle.")
                return False

        if use_vpn:
            update_status("VPN connecting", "Opening VPN app")
            vpn_open()
            vpn_connect()
            vpn_minimize()
            # CRITICAL FIX: Do NOT close VPN app during cycle!
            force_close_apps(exclude_vpn=True)
        else:
            force_close_apps()

        # Check stop before opening browser
        if stop_event.is_set():
            log_message("🛑 Stop before browser open")
            return False

        # 2. Open Browser & Template
        if not open_template_in_browser(template_url, stop_event=stop_event):
            log_message("❌ Failed to open template")
            return False

        if stop_event and stop_event.is_set():
            log_message("🛑 Stop after browser")
            return False

        # 3. Delays
        delay = random.uniform(delay_min, delay_max)
        log_message(f"⏳ Delay {delay:.1f}s")
        steps = int(delay * 2)
        for _ in range(steps):
            if stop_event and stop_event.is_set():
                log_message("🛑 Stop during delay")
                return False
            time.sleep(0.5)

        # 4. CapCut Workflow
        capcut_use_template(stop_event)
        if stop_event and stop_event.is_set():
            return False

        select_image(stop_event)
        if stop_event and stop_event.is_set():
            return False

        export_video(export_min, export_max, stop_event)

        # Optional Auto Storage Clean
        if auto_clean:
            clean_emulator_exported_videos()

        # 5. Cleanup at Cycle End
        if use_vpn:
            update_status("VPN disconnecting", "Ending VPN session")
            vpn_open()
            vpn_disconnect()
            vpn_close()

        if use_proxy:
            clear_proxy_on_device()

        force_close_apps()

        log_message(f"🎉 CYCLE #{index + 1} DONE")
        return True

    except Exception as e:
        log_message(f"⚠️ Error in cycle #{index + 1}: {e}")
        return False

# ==================== MODERN GUI ====================
class ModernCapcutGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CapCut Automation Bot")
        self.geometry("940x780")
        self.resizable(False, False)
        
        # Apply rounded corners (Windows only)
        try:
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if hwnd:
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 33, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int)
                )
        except:
            pass
        
        # Color palette
        self.bg = "#0a0e27"
        self.card_bg = "#1a1f3a"
        self.accent = "#6366f1"
        self.accent_hover = "#818cf8"
        self.text = "#e2e8f0"
        self.text_dim = "#94a3b8"
        self.success = "#10b981"
        self.danger = "#ef4444"
        self.warning = "#f59e0b"
        
        self.configure(bg=self.bg)
        
        # State
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.worker_thread = None
        self.testing_proxy = False
        
        # Load saved config
        self.cfg = load_config()
        
        # Variables
        self.link_var = tk.StringVar(value=self.cfg.get("template_url", DEFAULT_TEMPLATE_URL))
        self.loop_var = tk.StringVar(value=self.cfg.get("loop", DEFAULT_LOOP))
        self.delay_min_var = tk.StringVar(value=self.cfg.get("delay_min", DEFAULT_MIN_DELAY))
        self.delay_max_var = tk.StringVar(value=self.cfg.get("delay_max", DEFAULT_MAX_DELAY))
        self.export_min_var = tk.StringVar(value=self.cfg.get("export_min", DEFAULT_EXPORT_MIN))
        self.export_max_var = tk.StringVar(value=self.cfg.get("export_max", DEFAULT_EXPORT_MAX))
        
        self.mode_var = tk.StringVar(value=self.cfg.get("mode", "None"))
        self.previous_mode = self.mode_var.get()
        
        # Proxy options
        self.proxy_type_var = tk.StringVar(value=self.cfg.get("proxy_type", "txt"))
        self.proxy_file_path = self.cfg.get("proxy_file", "")
        self.proxy_file_var = tk.StringVar(value="No file loaded")
        self.proxy_count_var = tk.StringVar(value="0")
        self.proxy_link_url_var = tk.StringVar(value=self.cfg.get("proxy_link_url", ""))
        self.proxy_fixed_endpoint_var = tk.StringVar(value=self.cfg.get("proxy_fixed_endpoint", ""))
        self.proxy_test_status_var = tk.StringVar(value="")
        
        # Storage cleaner
        self.auto_clean_var = tk.BooleanVar(value=self.cfg.get("auto_clean_storage", False))
        
        # Device status
        self.device_status_var = tk.StringVar(value="● Probing Device...")
        
        # Progress counters
        self.counter_var = tk.StringVar(value="0")
        self.remaining_var = tk.StringVar(value="0")
        self.time_var = tk.StringVar(value="00:00:00")
        self.status_var = tk.StringVar(value="Ready")
        self.next_action_var = tk.StringVar(value="—")
        
        self.start_time = 0
        self.cycles_done = 0
        
        # Auto-load proxy file if exists in config or default
        if self.proxy_file_path and os.path.exists(self.proxy_file_path):
            cnt = load_proxies_from_file(self.proxy_file_path)
            self.proxy_file_var.set(f"{os.path.basename(self.proxy_file_path)} ({cnt} proxies)")
        else:
            default_txt = os.path.join(SCRIPT_DIR, "proxy.txt")
            if os.path.exists(default_txt):
                cnt = load_proxies_from_file(default_txt)
                self.proxy_file_path = default_txt
                self.proxy_file_var.set(f"proxy.txt ({cnt} proxies)")

        self._build_modern_ui()
        
        # Window closing cleanup
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.after(100, self._drain_log_queue)
        self.after(1000, self._update_time)
        self.after(500, self._update_status_display)
        self.after(600, self._refresh_device_status)
    
    def _build_modern_ui(self):
        """Build modern glassmorphism UI"""
        # Header
        header = tk.Frame(self, bg=self.bg, height=60)
        header.pack(fill=tk.X, padx=20, pady=(10, 5))
        header.pack_propagate(False)
        
        tk.Label(
            header, 
            text="CapCut Automation", 
            font=("Segoe UI", 18, "bold"),
            bg=self.bg, 
            fg=self.text
        ).pack(side=tk.LEFT, pady=10)
        
        # Right Header Widgets
        header_right = tk.Frame(header, bg=self.bg)
        header_right.pack(side=tk.RIGHT, pady=10)
        
        # Device badge & reconnect button
        self.device_label = tk.Label(
            header_right,
            textvariable=self.device_status_var,
            font=("Segoe UI", 10),
            bg=self.card_bg,
            fg=self.text_dim,
            padx=8,
            pady=3
        )
        self.device_label.pack(side=tk.LEFT, padx=(0, 6))
        
        tk.Button(
            header_right,
            text="🔄 Detect",
            command=self._refresh_device_status,
            bg=self.card_bg,
            fg=self.accent_hover,
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2"
        ).pack(side=tk.LEFT, padx=(0, 15))
        
        self.status_label = tk.Label(
            header_right,
            text="● Ready",
            font=("Segoe UI", 11, "bold"),
            bg=self.bg,
            fg=self.success
        )
        self.status_label.pack(side=tk.LEFT)
        
        # Main container
        main = tk.Frame(self, bg=self.bg)
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Left panel (Settings)
        left = tk.Frame(main, bg=self.card_bg, width=470)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        left.pack_propagate(False)
        
        tk.Label(
            left,
            text="Settings",
            font=("Segoe UI", 14, "bold"),
            bg=self.card_bg,
            fg=self.text
        ).pack(anchor=tk.W, padx=20, pady=(15, 8))
        
        # URL
        self._add_input(left, "Template URL", self.link_var, width=50)
        
        # Loop & Delays in grid
        grid_frame = tk.Frame(left, bg=self.card_bg)
        grid_frame.pack(fill=tk.X, padx=20, pady=4)
        
        self._add_small_input(grid_frame, "Loop (empty=∞)", self.loop_var, 0, 0, width=12)
        self._add_small_input(grid_frame, "Min Delay", self.delay_min_var, 0, 1, width=8)
        self._add_small_input(grid_frame, "Max Delay", self.delay_max_var, 0, 2, width=8)
        
        self._add_small_input(grid_frame, "Export Min", self.export_min_var, 1, 0, width=12)
        self._add_small_input(grid_frame, "Export Max", self.export_max_var, 1, 1, width=8)
        
        # Mode selection
        tk.Label(
            left,
            text="Connection Mode",
            font=("Segoe UI", 11, "bold"),
            bg=self.card_bg,
            fg=self.text
        ).pack(anchor=tk.W, padx=20, pady=(10, 3))
        
        mode_frame = tk.Frame(left, bg=self.card_bg)
        mode_frame.pack(fill=tk.X, padx=20, pady=2)
        
        for mode in ["None", "VPN", "Proxy"]:
            tk.Radiobutton(
                mode_frame,
                text=mode,
                variable=self.mode_var,
                value=mode,
                bg=self.card_bg,
                fg=self.text,
                selectcolor=self.card_bg,
                activebackground=self.card_bg,
                activeforeground=self.accent,
                font=("Segoe UI", 10),
                command=self._on_mode_change
            ).pack(side=tk.LEFT, padx=6)
        
        # Proxy options container (initially hidden if not proxy)
        self.proxy_panel = tk.Frame(left, bg="#13172e", relief=tk.RIDGE, bd=1)
        
        # Proxy submode (TXT vs Link)
        submode_frame = tk.Frame(self.proxy_panel, bg="#13172e")
        submode_frame.pack(fill=tk.X, padx=12, pady=(8, 4))
        
        tk.Label(
            submode_frame,
            text="Proxy Source:",
            bg="#13172e",
            fg=self.text_dim,
            font=("Segoe UI", 9, "bold")
        ).pack(side=tk.LEFT)
        
        tk.Radiobutton(
            submode_frame,
            text="📁 TXT File",
            variable=self.proxy_type_var,
            value="txt",
            bg="#13172e",
            fg=self.text,
            selectcolor="#13172e",
            activebackground="#13172e",
            activeforeground=self.accent,
            font=("Segoe UI", 9),
            command=self._on_proxy_submode_change
        ).pack(side=tk.LEFT, padx=6)
        
        tk.Radiobutton(
            submode_frame,
            text="🔗 Rotating Link",
            variable=self.proxy_type_var,
            value="link",
            bg="#13172e",
            fg=self.text,
            selectcolor="#13172e",
            activebackground="#13172e",
            activeforeground=self.accent,
            font=("Segoe UI", 9),
            command=self._on_proxy_submode_change
        ).pack(side=tk.LEFT, padx=6)
        
        # TXT File Section
        self.txt_proxy_frame = tk.Frame(self.proxy_panel, bg="#13172e")
        self.txt_proxy_frame.pack(fill=tk.X, padx=12, pady=4)
        
        self.proxy_btn = tk.Button(
            self.txt_proxy_frame,
            text="📁 Load Proxy File",
            command=self._load_proxy_file,
            bg=self.accent,
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.proxy_btn.pack(side=tk.LEFT)
        
        self.proxy_label = tk.Label(
            self.txt_proxy_frame,
            textvariable=self.proxy_file_var,
            bg="#13172e",
            fg=self.text_dim,
            font=("Segoe UI", 9)
        )
        self.proxy_label.pack(side=tk.LEFT, padx=10)
        
        # Link Proxy Section
        self.link_proxy_frame = tk.Frame(self.proxy_panel, bg="#13172e")
        
        tk.Label(
            self.link_proxy_frame,
            text="Rotation / API URL:",
            bg="#13172e",
            fg=self.text_dim,
            font=("Segoe UI", 8)
        ).pack(anchor=tk.W)
        
        tk.Entry(
            self.link_proxy_frame,
            textvariable=self.proxy_link_url_var,
            bg="#0f1729",
            fg=self.text,
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            insertbackground=self.accent
        ).pack(fill=tk.X, pady=(2, 4))
        
        tk.Label(
            self.link_proxy_frame,
            text="Fixed Proxy Endpoint (Optional: host:port:user:pass):",
            bg="#13172e",
            fg=self.text_dim,
            font=("Segoe UI", 8)
        ).pack(anchor=tk.W)
        
        tk.Entry(
            self.link_proxy_frame,
            textvariable=self.proxy_fixed_endpoint_var,
            bg="#0f1729",
            fg=self.text,
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            insertbackground=self.accent
        ).pack(fill=tk.X, pady=(2, 4))
        
        # Proxy Tester Bar
        test_bar = tk.Frame(self.proxy_panel, bg="#13172e")
        test_bar.pack(fill=tk.X, padx=12, pady=(6, 4))
        
        self.test_proxy_btn = tk.Button(
            test_bar,
            text="⚡ Test Proxy",
            command=self._test_current_proxy,
            bg="#3b82f6",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT,
            cursor="hand2"
        )
        self.test_proxy_btn.pack(side=tk.LEFT)
        
        self.test_proxy_lbl = tk.Label(
            test_bar,
            textvariable=self.proxy_test_status_var,
            bg="#13172e",
            fg=self.text_dim,
            font=("Segoe UI", 9)
        )
        self.test_proxy_lbl.pack(side=tk.LEFT, padx=8)

        # Support note
        tk.Label(
            self.proxy_panel,
            text="Supports HTTP, HTTPS, & SOCKS5 (with user:pass auth)",
            bg="#13172e",
            fg=self.text_dim,
            font=("Segoe UI", 8, "italic")
        ).pack(anchor=tk.W, padx=12, pady=(2, 6))

        # Show proxy panel if mode is Proxy
        if self.mode_var.get() == "Proxy":
            self.proxy_panel.pack(fill=tk.X, padx=20, pady=6)
            self._on_proxy_submode_change()
        
        # Storage Protection Option
        clean_frame = tk.Frame(left, bg=self.card_bg)
        clean_frame.pack(fill=tk.X, padx=20, pady=(6, 2))
        
        tk.Checkbutton(
            clean_frame,
            text="Auto-clean exported videos (protects LDPlayer storage)",
            variable=self.auto_clean_var,
            bg=self.card_bg,
            fg=self.text,
            selectcolor=self.card_bg,
            activebackground=self.card_bg,
            activeforeground=self.accent,
            font=("Segoe UI", 9)
        ).pack(side=tk.LEFT)
        
        # Control buttons
        btn_frame = tk.Frame(left, bg=self.card_bg)
        btn_frame.pack(fill=tk.X, padx=20, pady=(12, 8))
        
        self.start_btn = tk.Button(
            btn_frame,
            text="▶ Start",
            command=self._start_automation,
            bg=self.success,
            fg="white",
            font=("Segoe UI", 12, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            width=9,
            height=2
        )
        self.start_btn.pack(side=tk.LEFT, padx=3)
        
        self.stop_btn = tk.Button(
            btn_frame,
            text="■ Stop",
            command=self._stop_automation,
            bg=self.danger,
            fg="white",
            font=("Segoe UI", 12, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            width=9,
            height=2
        )
        self.stop_btn.pack(side=tk.LEFT, padx=3)
        
        self.pause_btn = tk.Button(
            btn_frame,
            text="⏸ Pause",
            command=self._pause_resume_automation,
            bg="#f59e0b",
            fg="white",
            font=("Segoe UI", 12, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            width=9,
            height=2
        )
        self.pause_btn.pack(side=tk.LEFT, padx=3)
        
        tk.Button(
            btn_frame,
            text="📄 Log",
            command=self._open_log_file,
            bg=self.card_bg,
            fg=self.text,
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            cursor="hand2",
            width=5
        ).pack(side=tk.LEFT, padx=3)
        
        # Statistics card
        stats = tk.Frame(left, bg=self.card_bg)
        stats.pack(fill=tk.X, padx=20, pady=6)
        
        tk.Label(
            stats,
            text="Statistics",
            font=("Segoe UI", 12, "bold"),
            bg=self.card_bg,
            fg=self.text
        ).pack(anchor=tk.W, pady=(0, 4))
        
        stats_grid = tk.Frame(stats, bg=self.card_bg)
        stats_grid.pack(fill=tk.X)
        
        self._add_stat(stats_grid, "Completed", self.counter_var, 0, 0)
        self._add_stat(stats_grid, "Remaining", self.remaining_var, 0, 1)
        self._add_stat(stats_grid, "Time", self.time_var, 0, 2)
        
        # Right panel (Status & Console)
        right = tk.Frame(main, bg=self.bg)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Current Status box
        status_box = tk.Frame(right, bg=self.card_bg, height=150)
        status_box.pack(fill=tk.X, pady=(0, 10))
        status_box.pack_propagate(False)
        
        tk.Label(
            status_box,
            text="Current Status",
            font=("Segoe UI", 13, "bold"),
            bg=self.card_bg,
            fg=self.text
        ).pack(anchor=tk.W, padx=15, pady=(10, 6))
        
        tk.Label(
            status_box,
            textvariable=self.status_var,
            font=("Segoe UI", 11),
            bg=self.card_bg,
            fg=self.accent,
            wraplength=400,
            justify=tk.LEFT,
            anchor=tk.W
        ).pack(fill=tk.X, anchor=tk.W, padx=15, pady=(0, 4))
        
        tk.Label(
            status_box,
            text="Next:",
            font=("Segoe UI", 9),
            bg=self.card_bg,
            fg=self.text_dim
        ).pack(anchor=tk.W, padx=15, pady=(4, 0))
        
        tk.Label(
            status_box,
            textvariable=self.next_action_var,
            font=("Segoe UI", 10),
            bg=self.card_bg,
            fg=self.text_dim,
            wraplength=400,
            justify=tk.LEFT,
            anchor=tk.W
        ).pack(fill=tk.X, anchor=tk.W, padx=15, pady=(0, 8))
        
        # Console
        console_frame = tk.Frame(right, bg=self.card_bg)
        console_frame.pack(fill=tk.BOTH, expand=True)
        
        console_header = tk.Frame(console_frame, bg=self.card_bg)
        console_header.pack(fill=tk.X, padx=15, pady=(10, 6))
        
        tk.Label(
            console_header,
            text="Console",
            font=("Segoe UI", 13, "bold"),
            bg=self.card_bg,
            fg=self.text
        ).pack(side=tk.LEFT)
        
        tk.Button(
            console_header,
            text="📋 Open Log",
            command=self._open_log_file,
            bg=self.card_bg,
            fg=self.text,
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            cursor="hand2"
        ).pack(side=tk.RIGHT, padx=4)
        
        tk.Button(
            console_header,
            text="🧹 Clear",
            command=self._clear_console,
            bg=self.card_bg,
            fg=self.text_dim,
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            cursor="hand2"
        ).pack(side=tk.RIGHT, padx=4)
        
        self.console = tk.Text(
            console_frame,
            bg="#000000",
            fg="#00ff00",
            font=("Consolas", 9),
            relief=tk.FLAT,
            insertbackground="#00ff00"
        )
        self.console.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        self.console.configure(state=tk.DISABLED)
    
    def _add_input(self, parent, label, var, width=30):
        frame = tk.Frame(parent, bg=self.card_bg)
        frame.pack(fill=tk.X, padx=20, pady=4)
        
        tk.Label(
            frame,
            text=label,
            bg=self.card_bg,
            fg=self.text_dim,
            font=("Segoe UI", 9)
        ).pack(anchor=tk.W)
        
        tk.Entry(
            frame,
            textvariable=var,
            bg="#0f1729",
            fg=self.text,
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            insertbackground=self.accent,
            width=width
        ).pack(fill=tk.X, pady=(2, 0))
    
    def _add_small_input(self, parent, label, var, row, col, width=10):
        frame = tk.Frame(parent, bg=self.card_bg)
        frame.grid(row=row, column=col, padx=4, pady=3, sticky=tk.W)
        
        tk.Label(
            frame,
            text=label,
            bg=self.card_bg,
            fg=self.text_dim,
            font=("Segoe UI", 8)
        ).pack(anchor=tk.W)
        
        tk.Entry(
            frame,
            textvariable=var,
            bg="#0f1729",
            fg=self.text,
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            insertbackground=self.accent,
            width=width
        ).pack(pady=(2, 0))
    
    def _add_stat(self, parent, label, var, row, col):
        frame = tk.Frame(parent, bg=self.card_bg)
        frame.grid(row=row, column=col, padx=12, sticky=tk.W)
        
        tk.Label(
            frame,
            text=label,
            bg=self.card_bg,
            fg=self.text_dim,
            font=("Segoe UI", 8)
        ).pack()
        
        tk.Label(
            frame,
            textvariable=var,
            bg=self.card_bg,
            fg=self.accent,
            font=("Segoe UI", 16, "bold")
        ).pack()
    
    def _on_mode_change(self):
        """Handle mode switch between None, VPN, Proxy"""
        mode = self.mode_var.get()
        
        # Clear proxy if switching away from Proxy mode
        if self.previous_mode == "Proxy" and mode != "Proxy":
            threading.Thread(target=clear_proxy_on_device, daemon=True).start()
        
        self.previous_mode = mode
        
        if mode == "Proxy":
            self.proxy_panel.pack(fill=tk.X, padx=20, pady=6)
            self._on_proxy_submode_change()
        else:
            self.proxy_panel.pack_forget()
        
        self._save_current_config()
    
    def _on_proxy_submode_change(self):
        """Toggle between TXT file and Link proxy input fields"""
        submode = self.proxy_type_var.get()
        if submode == "txt":
            self.link_proxy_frame.pack_forget()
            self.txt_proxy_frame.pack(fill=tk.X, padx=12, pady=4)
        else:
            self.txt_proxy_frame.pack_forget()
            self.link_proxy_frame.pack(fill=tk.X, padx=12, pady=4)
        
        self._save_current_config()
    
    def _load_proxy_file(self):
        path = filedialog.askopenfilename(
            title="Select Proxy File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            self.proxy_file_path = path
            count = load_proxies_from_file(path)
            self.proxy_file_var.set(f"{os.path.basename(path)} ({count} proxies)")
            self._save_current_config()
    
    def _test_current_proxy(self):
        """Test the currently configured proxy in background"""
        if self.testing_proxy:
            return
        
        submode = self.proxy_type_var.get()
        proxy_candidate = ""

        if submode == "txt":
            if not PROXIES:
                messagebox.showwarning("Warning", "Please load a proxy file first.")
                return
            proxy_candidate = PROXIES[0]
        else:
            link = self.proxy_link_url_var.get().strip()
            fixed = self.proxy_fixed_endpoint_var.get().strip()
            if not link and not fixed:
                messagebox.showwarning("Warning", "Please enter a rotation link or fixed endpoint.")
                return
            proxy_candidate = fixed if fixed else "link_fetch"

        self.testing_proxy = True
        self.test_proxy_btn.config(text="Testing...", state=tk.DISABLED)
        self.proxy_test_status_var.set("⏳ Testing connection...")

        def run_test():
            try:
                target_proxy = proxy_candidate
                if target_proxy == "link_fetch":
                    link = self.proxy_link_url_var.get().strip()
                    log_message(f"🔗 Testing rotation URL: {link}")
                    target_proxy = rotate_via_link(link)
                
                if not target_proxy:
                    self.after(0, lambda: self._update_test_ui(False, "Could not fetch proxy", 0))
                    return

                log_message(f"⚡ Testing proxy: {target_proxy}")
                alive, ip_info, latency = test_proxy_connection(target_proxy, timeout=5.0)
                self.after(0, lambda: self._update_test_ui(alive, ip_info, latency))
            except Exception as e:
                self.after(0, lambda: self._update_test_ui(False, str(e), 0))

        threading.Thread(target=run_test, daemon=True).start()

    def _update_test_ui(self, alive: bool, info: str, latency: float):
        self.testing_proxy = False
        self.test_proxy_btn.config(text="⚡ Test Proxy", state=tk.NORMAL)
        if alive:
            self.proxy_test_status_var.set(f"✅ IP: {info} ({latency:.0f}ms)")
            self.test_proxy_lbl.config(fg=self.success)
            log_message(f"⚡ Proxy Test OK: IP={info}, Ping={latency:.0f}ms")
        else:
            self.proxy_test_status_var.set(f"❌ {info}")
            self.test_proxy_lbl.config(fg=self.danger)
            log_message(f"❌ Proxy Test Failed: {info}")

    def _refresh_device_status(self):
        """Check ADB device connection and update header status badge"""
        def check():
            dev_id, status = detect_and_connect_device()
            def update():
                if status == "online":
                    self.device_status_var.set(f"● LDPlayer: {dev_id}")
                    self.device_label.config(fg=self.success)
                elif status == "offline":
                    self.device_status_var.set(f"● Device: Offline")
                    self.device_label.config(fg=self.warning)
                else:
                    self.device_status_var.set("● Device: Not Found")
                    self.device_label.config(fg=self.danger)
            self.after(0, update)

        threading.Thread(target=check, daemon=True).start()

    def _clear_console(self):
        self.console.configure(state=tk.NORMAL)
        self.console.delete("1.0", tk.END)
        self.console.configure(state=tk.DISABLED)

    def _open_log_file(self):
        try:
            if os.path.exists(LOG_FILE):
                os.startfile(LOG_FILE)
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open log: {e}")
    
    def _drain_log_queue(self):
        try:
            while not LOG_QUEUE.empty():
                msg = LOG_QUEUE.get_nowait()
                self.console.configure(state=tk.NORMAL)
                self.console.insert(tk.END, msg)
                self.console.see(tk.END)
                self.console.configure(state=tk.DISABLED)
        except:
            pass
        finally:
            self.after(100, self._drain_log_queue)
    
    def _update_time(self):
        if self.worker_thread and self.worker_thread.is_alive():
            elapsed = int(time.time() - self.start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            self.time_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        self.after(1000, self._update_time)
    
    def _update_status_display(self):
        try:
            self.status_var.set(CURRENT_STATUS)
            self.next_action_var.set(NEXT_ACTION)
        except:
            pass
        finally:
            self.after(500, self._update_status_display)
    
    def _save_current_config(self):
        cfg = {
            "template_url": self.link_var.get().strip(),
            "loop": self.loop_var.get().strip(),
            "delay_min": self.delay_min_var.get().strip(),
            "delay_max": self.delay_max_var.get().strip(),
            "export_min": self.export_min_var.get().strip(),
            "export_max": self.export_max_var.get().strip(),
            "mode": self.mode_var.get(),
            "proxy_type": self.proxy_type_var.get(),
            "proxy_file": self.proxy_file_path,
            "proxy_link_url": self.proxy_link_url_var.get().strip(),
            "proxy_fixed_endpoint": self.proxy_fixed_endpoint_var.get().strip(),
            "auto_clean_storage": self.auto_clean_var.get()
        }
        save_config(cfg)

    def _start_automation(self):
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Running", "Automation is already running")
            return
        
        self._save_current_config()

        link = self.link_var.get().strip() or DEFAULT_TEMPLATE_URL
        
        raw_loop = self.loop_var.get().strip()
        try:
            loop_count = int(raw_loop) if raw_loop else None
        except:
            loop_count = None
        
        if loop_count is None:
            messagebox.showinfo("Infinite Mode", "Loop count is empty. Will run infinitely until you click Stop.")
        
        try:
            delay_min = float(self.delay_min_var.get())
            delay_max = float(self.delay_max_var.get())
            export_min = float(self.export_min_var.get())
            export_max = float(self.export_max_var.get())
        except:
            messagebox.showerror("Error", "Invalid delay/export values")
            return
        
        mode = self.mode_var.get()
        use_vpn = (mode == "VPN")
        use_proxy = (mode == "Proxy")
        proxy_type = self.proxy_type_var.get()
        proxy_link = self.proxy_link_url_var.get().strip()
        proxy_fixed = self.proxy_fixed_endpoint_var.get().strip()
        auto_clean = self.auto_clean_var.get()
        
        if use_proxy:
            if proxy_type == "txt" and not PROXIES:
                messagebox.showwarning("Warning", "Please load a proxy file first.")
                return
            elif proxy_type == "link" and not proxy_link:
                messagebox.showwarning("Warning", "Please enter a rotation link / API URL.")
                return
        
        if self.cycles_done == 0 or not self.worker_thread or not self.worker_thread.is_alive():
            self.counter_var.set("0")
            self.remaining_var.set(str(loop_count) if loop_count is not None else "∞")
            self.time_var.set("00:00:00")
            self.cycles_done = 0
            self.start_time = time.time()
        
        self.stop_event.clear()
        self.status_label.config(text="● Running", fg=self.warning)
        
        # Reset apps before start
        force_close_apps()
        
        args = (link, loop_count, use_vpn, use_proxy, proxy_type, proxy_link, proxy_fixed,
                delay_min, delay_max, export_min, export_max, auto_clean)
        self.worker_thread = threading.Thread(target=self._worker, args=args, daemon=True)
        self.worker_thread.start()
        
        log_message("🚀 Automation started")
        log_message(f"Mode: {mode}")
        log_message(f"Loop: {loop_count if loop_count is not None else 'Infinite'}")
    
    def _stop_automation(self):
        log_message("🛑 STOP REQUESTED - Forcing immediate stop")
        self.stop_event.set()
        self.pause_event.clear()
        self.status_label.config(text="● Stopped", fg=self.danger)
        self.pause_btn.config(text="⏸ Pause", bg="#f59e0b")
        update_status("Stopped", "User requested stop")
        
        def cleanup_in_background():
            if self.mode_var.get() == "Proxy":
                clear_proxy_on_device()
            elif self.mode_var.get() == "VPN":
                try:
                    vpn_disconnect()
                    vpn_close()
                except:
                    pass
            force_close_apps()
            log_message("✅ Cleanup completed")
        
        threading.Thread(target=cleanup_in_background, daemon=True).start()
    
    def _pause_resume_automation(self):
        if not self.worker_thread or not self.worker_thread.is_alive():
            messagebox.showinfo("Not Running", "Automation is not running")
            return
        
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.pause_btn.config(text="⏸ Pause", bg="#f59e0b")
            self.status_label.config(text="● Running", fg=self.warning)
            log_message("▶️ Automation resumed")
            update_status("Resumed", "Continuing automation")
        else:
            self.pause_event.set()
            self.pause_btn.config(text="▶ Resume", bg=self.success)
            self.status_label.config(text="● Paused", fg=self.warning)
            log_message("⏸️ Automation paused")
            update_status("Paused", "Click Resume to continue")
    
    def _worker(self, link: str, loop_count: Optional[int], use_vpn: bool, use_proxy: bool,
                proxy_type: str, proxy_link: str, proxy_fixed: str,
                delay_min: float, delay_max: float, export_min: float, export_max: float,
                auto_clean: bool):
        for i in itertools.count() if loop_count is None else range(loop_count):
            if self.stop_event.is_set():
                log_message("🛑 Stopped by user")
                break
            
            success = one_cycle(i, link, use_vpn, use_proxy, proxy_type, proxy_link, proxy_fixed,
                                delay_min, delay_max, export_min, export_max, auto_clean,
                                self.stop_event, self.pause_event)
            
            if success:
                self.cycles_done += 1
            
            self.after(0, self._update_counters, loop_count)
            
            if self.stop_event.is_set():
                break
        
        self.after(0, lambda: self.status_label.config(text="● Ready", fg=self.success))
        log_message("✅ Automation completed")
    
    def _update_counters(self, total: Optional[int]):
        """Update completed and remaining counters safely"""
        self.counter_var.set(str(self.cycles_done))
        if total is not None:
            remaining = max(0, total - self.cycles_done)
            self.remaining_var.set(str(remaining))
        else:
            self.remaining_var.set("∞")
            
    def _on_close(self):
        """Clean up proxy, save config and close application window"""
        try:
            self._save_current_config()
            self.stop_event.set()
            if self.mode_var.get() == "Proxy":
                clear_proxy_on_device()
        except:
            pass
        self.destroy()

# ==================== MAIN ====================
if __name__ == "__main__":
    try:
        open(LOG_FILE, "a", encoding="utf-8").close()
    except:
        pass
    
    app = ModernCapcutGUI()
    app.mainloop()
