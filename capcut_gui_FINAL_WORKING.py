#!/usr/bin/env python3
"""
CapCut Automation Tool - Modern Glassmorphism UI
Features:
- Modern glassmorphism design (2025 style)
- VPN/Proxy/None modes (mutually exclusive)
- Live logs with better ADB connection handling
- Screen loading detection with retries
- Immediate stop functionality
"""

import os
import time
import random
import subprocess
import threading
import itertools
import queue
import ctypes
from typing import List, Tuple, Optional
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

# ==================== CONFIG ====================
DEVICE_ID = "emulator-5554"
LOG_FILE = "capcut_automation.log"

DEFAULT_TEMPLATE_URL = "https://www.capcut.com/template-detail/7573250368646221109"
DEFAULT_LOOP = "100"
DEFAULT_MIN_DELAY = "6"
DEFAULT_MAX_DELAY = "9"
DEFAULT_EXPORT_MIN = "25"
DEFAULT_EXPORT_MAX = "40"

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

# Logging queue
LOG_QUEUE = queue.Queue()

# ==================== LOGGING ====================
def log_message(msg: str):
    """Log message to console, file, and GUI queue"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    
    LOG_QUEUE.put(formatted + "\n")
    
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except:
        pass

def update_status(current: str, next_action: str = "—"):
    """Update global status for GUI"""
    global CURRENT_STATUS, NEXT_ACTION
    CURRENT_STATUS = current
    NEXT_ACTION = next_action
    log_message(f"📍 {current}")

# ==================== ADB HELPERS ====================
def run_cmd(cmd: List[str], wait: bool = True, timeout: float = 20.0):
    """Run command with optional timeout (hides CMD window)"""
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        
        proc = subprocess.Popen(
            cmd, 
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

def adb(args: List[str], wait: bool = True):
    """Execute ADB command"""
    cmd = ["adb", "-s", DEVICE_ID] + args
    log_message(f"🔧 ADB: {' '.join(cmd)}")
    return run_cmd(cmd, wait=wait)

def check_device() -> bool:
    """Check if device is connected and online"""
    log_message("🔍 Checking ADB connection...")
    proc, out, err, timed = run_cmd(["adb", "devices"], timeout=5)
    
    if timed or proc is None:
        log_message("❌ ADB command timed out")
        return False
    
    lines = out.strip().splitlines()
    for line in lines:
        if DEVICE_ID in line:
            if "device" in line and "offline" not in line:
                log_message(f"✅ Device {DEVICE_ID} is ONLINE")
                return True
            elif "offline" in line:
                log_message(f"❌ Device {DEVICE_ID} is OFFLINE - Please restart LDPlayer or reconnect ADB")
                return False
    
    log_message(f"❌ Device {DEVICE_ID} not found")
    return False

def reconnect_adb():
    """Try to reconnect ADB"""
    log_message("🔄 Attempting to reconnect ADB...")
    run_cmd(["adb", "kill-server"], timeout=5)
    time.sleep(1)
    run_cmd(["adb", "start-server"], timeout=5)
    time.sleep(2)
    return check_device()

def tap(coord: Tuple[int, int], tag: str = ""):
    """Tap at coordinates"""
    x, y = coord
    if tag:
        log_message(f"👆 TAP {tag}: ({x}, {y})")
    else:
        log_message(f"👆 TAP: ({x}, {y})")
    adb(["shell", "input", "tap", str(x), str(y)], wait=False)

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

def force_close_apps():
    """Force close CapCut, Chrome, and VPN"""
    log_message("❌ Force closing all apps...")
    adb(["shell", "am", "force-stop", "com.lemon.lvoverseas"])
    adb(["shell", "am", "force-stop", "com.android.chrome"])
    adb(["shell", "am", "force-stop", VPN_PACKAGE])
    time.sleep(1)

# ==================== PROXY FUNCTIONS ====================
def load_proxies_from_file(path: str) -> int:
    """Load proxies from file"""
    global PROXIES, PROXY_ITER
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]
        
        PROXIES = [line for line in lines if line and not line.startswith("#")]
        PROXY_ITER = itertools.cycle(PROXIES) if PROXIES else None
        log_message(f"📂 Loaded {len(PROXIES)} proxies")
        return len(PROXIES)
    except Exception as e:
        log_message(f"❌ Error loading proxies: {e}")
        PROXIES = []
        PROXY_ITER = None
        return 0

def get_next_proxy() -> Optional[str]:
    """Get next proxy from rotation"""
    global PROXY_ITER
    if not PROXY_ITER:
        return None
    with PROXY_LOCK:
        try:
            return next(PROXY_ITER)
        except:
            return None

def apply_proxy_to_device(proxy_line: str) -> bool:
    """Apply proxy to device - supports multiple formats"""
    if not proxy_line:
        return False
    
    # Remove whitespace
    proxy_line = proxy_line.strip()
    
    # Check if SOCKS5 and skip (Android global proxy doesn't support SOCKS5)
    if proxy_line.lower().startswith("socks5://") or proxy_line.lower().startswith("socks4://"):
        log_message(f"⚠️ Skipping SOCKS5 proxy (not supported): {proxy_line}")
        log_message("💡 Use HTTP/HTTPS proxies instead")
        return False
    
    # Remove protocol prefixes (http://, https://)
    proxy_line = proxy_line.replace("http://", "")
    proxy_line = proxy_line.replace("https://", "")
    
    # Parse proxy line
    parts = proxy_line.split(":")
    if len(parts) < 2:
        log_message("❌ Invalid proxy format (need at least host:port)")
        return False
    
    # Extract host and port (ignore username:password if present)
    host = parts[0]
    port = parts[1]
    
    # Log format info
    if len(parts) == 2:
        log_message(f"🔧 Applying HTTP proxy: {host}:{port}")
    elif len(parts) == 4:
        log_message(f"🔧 Applying HTTP proxy: {host}:{port} (auth ignored)")
    else:
        log_message(f"🔧 Applying HTTP proxy: {host}:{port}")
    
    # Apply proxy to device (Android global proxy doesn't support auth)
    adb(["shell", "settings", "put", "global", "http_proxy", f"{host}:{port}"])
    log_message("✅ Proxy applied successfully")
    return True

def clear_proxy_on_device():
    """Clear proxy from device"""
    log_message("🔧 Clearing proxy...")
    adb(["shell", "settings", "put", "global", "http_proxy", ":0"])
    log_message("✅ Proxy cleared and ready for next one")

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
    """Wait for screen to be ready (polling based) with stop check"""
    update_status(f"Waiting for screen: {expected_package}", f"Max {max_wait}s")
    
    checks = int(max_wait / check_interval)
    for i in range(checks):
        # Check stop event
        if stop_event and stop_event.is_set():
            log_message("🛑 Stop detected during screen wait")
            return False
        
        fg = get_foreground_package()
        if fg == expected_package:
            log_message(f"✅ Screen ready: {expected_package}")
            # Extra wait to ensure screen is fully loaded and clickable
            update_status(f"Screen loaded: {expected_package}", "Waiting 2s for stability")
            time.sleep(2)
            return True
        
        if i % 6 == 0 and i > 0:
            elapsed = i * check_interval
            log_message(f"   Still waiting... ({elapsed:.1f}s, current: {fg or 'unknown'})")
        
        time.sleep(check_interval)
    
    log_message(f"⚠️ Timeout waiting for {expected_package}")
    return False

def open_template_in_browser(template_url: str, max_attempts: int = 5, stop_event: threading.Event = None) -> bool:
    """Open template in Chrome with stop check"""
    update_status("Opening browser", "Launching Chrome")
    
    for attempt in range(1, max_attempts + 1):
        # Check stop before each attempt
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
        
        # Check stop after Chrome loads
        if stop_event and stop_event.is_set():
            log_message("🛑 Stop detected after Chrome load")
            return False
        
        update_status("Page loading", "Waiting 4s for content")
        # Wait for page to load with stop checks
        for i in range(8):  # 4 seconds total, check every 0.5s
            if stop_event and stop_event.is_set():
                log_message("🛑 Stop detected during page load")
                return False
            time.sleep(0.5)
        
        update_status("Clicking button", "'Use template in CapCut'")
        log_message("▶️ Clicking 'Use template'")
        tap(BROWSER_USE_TEMPLATE, "BROWSER_USE_TEMPLATE")
        
        # Extra wait after tap to ensure it registers
        update_status("Tap registered", "Waiting 2s")
        time.sleep(2)
        
        if wait_for_screen_ready("com.lemon.lvoverseas", max_wait=15, stop_event=stop_event):
            log_message("✅ CapCut opened!")
            return True
        
        # Check stop before retry
        if stop_event and stop_event.is_set():
            log_message("🛑 Stop detected, aborting")
            return False
        
        log_message("⚠️ CapCut timeout, retrying...")
        time.sleep(2)
    
    log_message("❌ Failed to open CapCut")
    return False

def capcut_use_template(stop_event: threading.Event = None):
    """Click 'Use template' in CapCut with stop check"""
    if stop_event and stop_event.is_set():
        log_message("🛑 Stop detected")
        return
    
    update_status("CapCut: Using template", "Clicking button")
    log_message("▶️ Using template")
    tap(CC_USE_TEMPLATE, "CC_USE_TEMPLATE")
    
    wait_time = random.uniform(2, 3)
    update_status("Template UI loading", f"Waiting {wait_time:.1f}s")
    log_message(f"⏳ Wait {wait_time:.1f}s for template UI")
    
    # Wait with stop checks
    steps = int(wait_time * 2)  # Check every 0.5s
    for _ in range(steps):
        if stop_event and stop_event.is_set():
            log_message("🛑 Stop during wait")
            return
        time.sleep(0.5)

def select_image(stop_event: threading.Event = None):
    """Select image from gallery with stop check"""
    if stop_event and stop_event.is_set():
        log_message("🛑 Stop detected")
        return
    
    update_status("Opening gallery", "Clicking image section")
    log_message("🖼 Opening gallery")
    tap(CLICK_IMAGE_SECTION, "CLICK_IMAGE_SECTION")
    
    # Wait with stop check
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
    tap(GALLERY_CONFIRM, "GALLERY_CONFIRM")
    
    wait_time = random.uniform(1.5, 2.5)
    update_status("Confirmation processing", f"Waiting {wait_time:.1f}s")
    steps = int(wait_time * 2)
    for _ in range(steps):
        if stop_event and stop_event.is_set():
            return
        time.sleep(0.5)

def export_video(export_wait_min: float, export_wait_max: float, stop_event: threading.Event = None):
    """Export video with stop check"""
    if stop_event and stop_event.is_set():
        log_message("🛑 Stop detected")
        return
    
    # Extra wait to ensure screen is ready (especially in NONE mode)
    log_message("⏳ Waiting 2s for screen to stabilize...")
    time.sleep(2)
    
    update_status("Starting export", "Clicking export button")
    log_message("📤 Exporting...")
    tap(CC_EXPORT_TOP_RIGHT, "CC_EXPORT_TOP_RIGHT")
    
    # Small wait and retry tap for reliability
    time.sleep(0.5)
    log_message("🔁 Retry tap for reliability")
    tap(CC_EXPORT_TOP_RIGHT, "CC_EXPORT_TOP_RIGHT")
    
    wait1 = random.uniform(5, 7)
    update_status("Export UI loading", f"Waiting {wait1:.1f}s")
    log_message(f"⏳ Wait {wait1:.1f}s for export UI")
    
    # Wait with stop checks
    steps = int(wait1 * 2)
    for _ in range(steps):
        if stop_event and stop_event.is_set():
            log_message("🛑 Stop during export UI wait")
            return
        time.sleep(0.5)
    
    update_status("Final export", "Clicking final export button")
    log_message("✅ Final export")
    tap(FINAL_EXPORT_BTN, "FINAL_EXPORT_BTN")
    
    wait2 = random.uniform(export_wait_min, export_wait_max)
    update_status("Video exporting", f"Total {wait2:.0f}s")
    log_message(f"⏳ Exporting {wait2:.1f}s...")
    
    elapsed = 0
    while elapsed < wait2:
        if stop_event and stop_event.is_set():
            log_message("🛑 Stop during export")
            return
        
        sleep_chunk = min(1, wait2 - elapsed)  # Check every 1s
        time.sleep(sleep_chunk)
        elapsed += sleep_chunk
        
        # Show progress every 5 seconds
        if int(elapsed) % 5 == 0 and elapsed < wait2:
            remaining = wait2 - elapsed
            update_status("Exporting video", f"{remaining:.0f}s remaining")
            log_message(f"   Progress: {elapsed:.0f}s / {wait2:.0f}s")

# ==================== ONE CYCLE ====================
def one_cycle(index: int, template_url: str, use_vpn: bool, use_proxy: bool,
              delay_min: float, delay_max: float, export_min: float, export_max: float,
              stop_event: threading.Event, pause_event: threading.Event) -> bool:
    """Execute one cycle with pause support"""
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
        
        if use_proxy:
            update_status("Applying proxy", "Rotating proxy")
            proxy = get_next_proxy()
            if proxy:
                apply_proxy_to_device(proxy)
        
        if use_vpn:
            update_status("VPN connecting", "Opening VPN app")
            vpn_open()
            vpn_connect()
            vpn_minimize()  # Keep VPN in background, don't close it
        
        force_close_apps()
        
        # Check stop before opening browser
        if stop_event.is_set():
            log_message("🛑 Stop before browser open")
            return False
        
        if not open_template_in_browser(template_url, stop_event=stop_event):
            log_message("❌ Failed to open template")
            return False
        
        # Check stop after browser
        if stop_event.is_set():
            log_message("🛑 Stop after browser")
            return False
        
        delay = random.uniform(delay_min, delay_max)
        log_message(f"⏳ Delay {delay:.1f}s")
        
        # Delay with stop checks
        steps = int(delay * 2)
        for _ in range(steps):
            if stop_event.is_set():
                log_message("🛑 Stop during delay")
                return False
            time.sleep(0.5)
        
        capcut_use_template(stop_event)
        
        if stop_event.is_set():
            return False
        
        select_image(stop_event)
        
        if stop_event.is_set():
            return False
        
        export_video(export_min, export_max, stop_event)
        
        if use_vpn:
            update_status("VPN disconnecting", "Ending VPN session")
            vpn_open()
            vpn_disconnect()
            vpn_close()  # Only close VPN at end of cycle
        
        if use_proxy:
            clear_proxy_on_device()
        
        force_close_apps()
        
        log_message(f"🎉 CYCLE #{index + 1} DONE")
        return True
        
    except Exception as e:
        log_message(f"⚠️ Error: {e}")
        return False

# ==================== MODERN GUI ====================
class ModernCapcutGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CapCut Automation")
        self.geometry("900x700")
        self.resizable(False, False)
        
        # Apply rounded corners (Windows only)
        try:
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            if hwnd:
                # DWM_WINDOW_CORNER_PREFERENCE = 33
                # DWMWCP_ROUND = 2
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, 33, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int)
                )
        except:
            pass  # Ignore if not on Windows or if it fails
        
        # Modern color scheme
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
        
        # Variables
        self.link_var = tk.StringVar(value=DEFAULT_TEMPLATE_URL)
        self.loop_var = tk.StringVar(value=DEFAULT_LOOP)
        self.delay_min_var = tk.StringVar(value=DEFAULT_MIN_DELAY)
        self.delay_max_var = tk.StringVar(value=DEFAULT_MAX_DELAY)
        self.export_min_var = tk.StringVar(value=DEFAULT_EXPORT_MIN)
        self.export_max_var = tk.StringVar(value=DEFAULT_EXPORT_MAX)
        
        self.mode_var = tk.StringVar(value="None")
        self.previous_mode = "None"  # Track previous mode
        self.proxy_file_var = tk.StringVar(value="No file")
        self.proxy_count_var = tk.StringVar(value="0")
        
        self.counter_var = tk.StringVar(value="0")
        self.remaining_var = tk.StringVar(value="0")
        self.time_var = tk.StringVar(value="00:00:00")
        self.status_var = tk.StringVar(value="Ready")
        self.next_action_var = tk.StringVar(value="—")
        
        self.start_time = 0
        self.cycles_done = 0
        
        self._build_modern_ui()
        self.after(100, self._drain_log_queue)
        self.after(1000, self._update_time)
        self.after(500, self._update_status_display)
    
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
        
        # Status indicator
        self.status_label = tk.Label(
            header,
            text="● Ready",
            font=("Segoe UI", 11),
            bg=self.bg,
            fg=self.success
        )
        self.status_label.pack(side=tk.RIGHT, pady=10, padx=10)
        
        # Main container
        main = tk.Frame(self, bg=self.bg)
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Left panel (Settings)
        left = tk.Frame(main, bg=self.card_bg, width=450)
        left.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        left.pack_propagate(False)
        
        # Settings header
        tk.Label(
            left,
            text="Settings",
            font=("Segoe UI", 14, "bold"),
            bg=self.card_bg,
            fg=self.text
        ).pack(anchor=tk.W, padx=20, pady=(15, 10))
        
        # URL
        self._add_input(left, "Template URL", self.link_var, width=50)
        
        # Loop & Delays in grid
        grid_frame = tk.Frame(left, bg=self.card_bg)
        grid_frame.pack(fill=tk.X, padx=20, pady=5)
        
        self._add_small_input(grid_frame, "Loop", self.loop_var, 0, 0, width=10)
        self._add_small_input(grid_frame, "Min Delay", self.delay_min_var, 0, 1, width=8)
        self._add_small_input(grid_frame, "Max Delay", self.delay_max_var, 0, 2, width=8)
        
        self._add_small_input(grid_frame, "Export Min", self.export_min_var, 1, 0, width=10)
        self._add_small_input(grid_frame, "Export Max", self.export_max_var, 1, 1, width=10)
        
        # Mode selection
        tk.Label(
            left,
            text="Connection Mode",
            font=("Segoe UI", 11, "bold"),
            bg=self.card_bg,
            fg=self.text
        ).pack(anchor=tk.W, padx=20, pady=(15, 5))
        
        mode_frame = tk.Frame(left, bg=self.card_bg)
        mode_frame.pack(fill=tk.X, padx=20, pady=5)
        
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
            ).pack(side=tk.LEFT, padx=5)
        
        # Proxy loader
        proxy_frame = tk.Frame(left, bg=self.card_bg)
        proxy_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.proxy_btn = tk.Button(
            proxy_frame,
            text="📁 Load Proxy File",
            command=self._load_proxy_file,
            bg=self.accent,
            fg="white",
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.proxy_btn.pack(side=tk.LEFT)
        
        tk.Label(
            proxy_frame,
            textvariable=self.proxy_file_var,
            bg=self.card_bg,
            fg=self.text_dim,
            font=("Segoe UI", 9)
        ).pack(side=tk.LEFT, padx=10)
        
        # Initially hide proxy button
        self.proxy_btn.pack_forget()
        self.proxy_label = tk.Label(
            proxy_frame,
            textvariable=self.proxy_file_var,
            bg=self.card_bg,
            fg=self.text_dim,
            font=("Segoe UI", 9)
        )
        self.proxy_label.pack_forget()
        
        # Control buttons
        btn_frame = tk.Frame(left, bg=self.card_bg)
        btn_frame.pack(fill=tk.X, padx=20, pady=20)
        
        self.start_btn = tk.Button(
            btn_frame,
            text="▶ Start",
            command=self._start_automation,
            bg=self.success,
            fg="white",
            font=("Segoe UI", 12, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            width=12,
            height=2
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(
            btn_frame,
            text="■ Stop",
            command=self._stop_automation,
            bg=self.danger,
            fg="white",
            font=("Segoe UI", 12, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            width=12,
            height=2
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.pause_btn = tk.Button(
            btn_frame,
            text="⏸ Pause",
            command=self._pause_resume_automation,
            bg="#f59e0b",
            fg="white",
            font=("Segoe UI", 12, "bold"),
            relief=tk.FLAT,
            cursor="hand2",
            width=12,
            height=2
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            btn_frame,
            text="📄 Log",
            command=self._open_log_file,
            bg=self.card_bg,
            fg=self.text,
            font=("Segoe UI", 10),
            relief=tk.FLAT,
            cursor="hand2",
            width=8
        ).pack(side=tk.LEFT, padx=5)
        
        # Statistics card (MOVED below buttons on LEFT panel)
        stats = tk.Frame(left, bg=self.card_bg)
        stats.pack(fill=tk.X, padx=20, pady=20)
        
        tk.Label(
            stats,
            text="Statistics",
            font=("Segoe UI", 12, "bold"),
            bg=self.card_bg,
            fg=self.text
        ).pack(anchor=tk.W, pady=(0, 10))
        
        stats_grid = tk.Frame(stats, bg=self.card_bg)
        stats_grid.pack(fill=tk.X)
        
        self._add_stat(stats_grid, "Completed", self.counter_var, 0, 0)
        self._add_stat(stats_grid, "Remaining", self.remaining_var, 0, 1)
        self._add_stat(stats_grid, "Time", self.time_var, 0, 2)
        
        # Right panel (Current Status & Console) - EXPANDED
        right = tk.Frame(main, bg=self.bg)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Current Status box - BIGGER (180px for better visibility)
        status_box = tk.Frame(right, bg=self.card_bg, height=180)
        status_box.pack(fill=tk.X, pady=(0, 10))
        status_box.pack_propagate(False)
        
        tk.Label(
            status_box,
            text="Current Status",
            font=("Segoe UI", 13, "bold"),
            bg=self.card_bg,
            fg=self.text
        ).pack(anchor=tk.W, padx=15, pady=(15, 10))
        
        tk.Label(
            status_box,
            textvariable=self.status_var,
            font=("Segoe UI", 11),
            bg=self.card_bg,
            fg=self.accent,
            wraplength=400,
            justify=tk.LEFT,
            anchor=tk.W
        ).pack(fill=tk.X, anchor=tk.W, padx=15, pady=(0, 5))
        
        tk.Label(
            status_box,
            text="Next:",
            font=("Segoe UI", 9),
            bg=self.card_bg,
            fg=self.text_dim
        ).pack(anchor=tk.W, padx=15, pady=(10, 0))
        
        tk.Label(
            status_box,
            textvariable=self.next_action_var,
            font=("Segoe UI", 10),
            bg=self.card_bg,
            fg=self.text_dim,
            wraplength=400,
            justify=tk.LEFT,
            anchor=tk.W
        ).pack(fill=tk.X, anchor=tk.W, padx=15, pady=(0, 15))
        
        # Console - EXPANDED (takes remaining space)
        console_frame = tk.Frame(right, bg=self.card_bg)
        console_frame.pack(fill=tk.BOTH, expand=True)
        
        # Console header with copy button
        console_header = tk.Frame(console_frame, bg=self.card_bg)
        console_header.pack(fill=tk.X, padx=15, pady=(15, 10))
        
        tk.Label(
            console_header,
            text="Console",
            font=("Segoe UI", 13, "bold"),
            bg=self.card_bg,
            fg=self.text
        ).pack(side=tk.LEFT)
        
        tk.Button(
            console_header,
            text="📋",
            command=self._open_log_file,
            bg=self.card_bg,
            fg=self.text,
            font=("Segoe UI", 12),
            relief=tk.FLAT,
            cursor="hand2",
            width=3
        ).pack(side=tk.LEFT, padx=10)
        
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
        """Add input field"""
        frame = tk.Frame(parent, bg=self.card_bg)
        frame.pack(fill=tk.X, padx=20, pady=5)
        
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
        """Add small input in grid"""
        frame = tk.Frame(parent, bg=self.card_bg)
        frame.grid(row=row, column=col, padx=5, pady=5, sticky=tk.W)
        
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
        """Add stat display"""
        frame = tk.Frame(parent, bg=self.card_bg)
        frame.grid(row=row, column=col, padx=10, sticky=tk.W)
        
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
        """Handle mode change - show/hide proxy button"""
        mode = self.mode_var.get()
        
        # ONLY clear proxy if switching FROM Proxy to None/VPN
        if self.previous_mode == "Proxy" and mode != "Proxy":
            def clear_in_background():
                try:
                    clear_proxy_on_device()
                    log_message(f"✅ Proxy cleared (switched from Proxy to {mode})")
                except Exception as e:
                    log_message(f"⚠️ Error clearing proxy: {e}")
            
            # Run in background thread
            threading.Thread(target=clear_in_background, daemon=True).start()
        
        # Update previous mode
        self.previous_mode = mode
        
        # Show/hide proxy button based on mode
        if mode == "Proxy":
            self.proxy_btn.config(state=tk.NORMAL, bg=self.accent)
            self.proxy_btn.pack(side=tk.LEFT)
            self.proxy_label.pack(side=tk.LEFT, padx=10)
        else:
            self.proxy_btn.pack_forget()
            self.proxy_label.pack_forget()
    
    def _load_proxy_file(self):
        """Load proxy file"""
        path = filedialog.askopenfilename(
            title="Select Proxy File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            count = load_proxies_from_file(path)
            self.proxy_file_var.set(f"{os.path.basename(path)} ({count})")
    
    def _open_log_file(self):
        """Open log file"""
        try:
            if os.path.exists(LOG_FILE):
                os.startfile(LOG_FILE)
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open log: {e}")
    
    def _drain_log_queue(self):
        """Drain log queue"""
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
        """Update elapsed time"""
        if self.worker_thread and self.worker_thread.is_alive():
            elapsed = int(time.time() - self.start_time)
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            self.time_var.set(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        self.after(1000, self._update_time)
    
    def _update_status_display(self):
        """Update status display from global variables"""
        try:
            self.status_var.set(CURRENT_STATUS)
            self.next_action_var.set(NEXT_ACTION)
        except:
            pass
        finally:
            self.after(500, self._update_status_display)
    
    def _start_automation(self):
        """Start automation"""
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Running", "Already running")
            return
        
        # Device check removed to prevent GUI freeze
        # Worker thread will handle connection errors
        
        link = self.link_var.get().strip() or DEFAULT_TEMPLATE_URL
        
        try:
            loop_count = int(self.loop_var.get().strip()) if self.loop_var.get().strip() else None
        except:
            loop_count = None  # Infinite loop
        
        # If loop is None or empty, run infinite
        if loop_count is None:
            messagebox.showinfo("Infinite Loop", "Loop count is empty. Will run infinitely until you click Stop.")
        
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
        
        if use_proxy and not PROXIES:
            messagebox.showwarning("Warning", "No proxies loaded")
            return
        
        # Only reset counters when starting fresh (not when resuming)
        # Keep existing values visible if stopping/restarting
        if self.cycles_done == 0 or not self.worker_thread or not self.worker_thread.is_alive():
            self.counter_var.set("0")
            self.remaining_var.set(str(loop_count) if loop_count is not None else "∞")
            self.time_var.set("00:00:00")
            self.cycles_done = 0
            self.start_time = time.time()
        
        self.stop_event.clear()
        self.status_label.config(text="● Running", fg=self.warning)
        
        force_close_apps()
        
        args = (link, loop_count, use_vpn, use_proxy, delay_min, delay_max, export_min, export_max)
        self.worker_thread = threading.Thread(target=self._worker, args=args, daemon=True)
        self.worker_thread.start()
        
        log_message("🚀 Automation started")
        log_message(f"Mode: {mode}")
        log_message(f"Loop: {loop_count if loop_count else 'Infinite'}")
    
    def _stop_automation(self):
        """Stop automation immediately and clean up everything"""
        log_message("🛑 STOP REQUESTED - Forcing immediate stop")
        self.stop_event.set()
        self.pause_event.clear()  # Clear pause if paused
        self.status_label.config(text="● Stopped", fg=self.danger)
        self.pause_btn.config(text="⏸ Pause")  # Reset pause button
        update_status("Stopped", "User requested stop")
        
        # Run cleanup in background thread to avoid freezing GUI
        def cleanup_in_background():
            # Only clear proxy if Proxy mode is selected
            if self.mode_var.get() == "Proxy":
                try:
                    clear_proxy_on_device()
                    log_message("✅ Proxy cleared")
                except Exception as e:
                    log_message(f"⚠️ Error clearing proxy: {e}")
            
            # Force close all apps to ensure clean state
            log_message("🧹 Cleaning up all background apps...")
            force_close_apps()
            log_message("✅ All apps closed")
        
        # Run in background thread
        threading.Thread(target=cleanup_in_background, daemon=True).start()
    
    def _pause_resume_automation(self):
        """Toggle pause/resume"""
        if not self.worker_thread or not self.worker_thread.is_alive():
            messagebox.showinfo("Not Running", "Automation is not running")
            return
        
        if self.pause_event.is_set():
            # Resume
            self.pause_event.clear()
            self.pause_btn.config(text="⏸ Pause", bg="#f59e0b")
            self.status_label.config(text="● Running", fg=self.warning)
            log_message("▶️ Automation resumed")
            update_status("Resumed", "Continuing automation")
        else:
            # Pause
            self.pause_event.set()
            self.pause_btn.config(text="▶ Resume", bg=self.success)
            self.status_label.config(text="● Paused", fg=self.warning)
            log_message("⏸️ Automation paused")
            update_status("Paused", "Click Resume to continue")
    
    def _worker(self, link: str, loop_count: Optional[int], use_vpn: bool, use_proxy: bool,
                delay_min: float, delay_max: float, export_min: float, export_max: float):
        """Worker thread - supports infinite loop if loop_count is None"""
        for i in itertools.count() if loop_count is None else range(loop_count):
            if self.stop_event.is_set():
                log_message("🛑 Stopped by user")
                break
            
            success = one_cycle(i, link, use_vpn, use_proxy, 
                              delay_min, delay_max, export_min, export_max, 
                              self.stop_event, self.pause_event)
            
            if success:
                self.cycles_done += 1
            
            self.after(0, self._update_counters, loop_count)
            
            if self.stop_event.is_set():
                break
        
        self.after(0, lambda: self.status_label.config(text="● Ready", fg=self.success))
        log_message("✅ Automation completed")
    
    def _update_counters(self, total: int):
        """Update counters"""
        self.counter_var.set(str(self.cycles_done))
        remaining = max(0, total - self.cycles_done)
        self.remaining_var.set(str(remaining))

# ==================== MAIN ====================
if __name__ == "__main__":
    try:
        open(LOG_FILE, "a", encoding="utf-8").close()
    except:
        pass
    
    app = ModernCapcutGUI()
    app.mainloop()
