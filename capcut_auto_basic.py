import os
import time
import random
import subprocess
from typing import List, Tuple

# ================== CONFIG ==================

# ADB device id (adb devices se jo aati hai)
DEVICE_ID = "emulator-5554"

# CapCut template link (Chrome me ye open hoga)
TEMPLATE_URL = "https://www.capcut.com/template-detail/7573250368646221109"

# Kitni baar ye pura flow run karna hai
EXPORT_COUNT = 1000  # 10 bar export loop

# Random delay range (seconds) - general small waits
DELAY_MIN = 4
DELAY_MAX = 7

# 1st export (top-right) ke baad chhota wait (seconds)
FIRST_EXPORT_WAIT_MIN = 5
FIRST_EXPORT_WAIT_MAX = 7

# Final export (heavy render + download) ke liye wait (seconds)
EXPORT_WAIT_MIN = 25
EXPORT_WAIT_MAX = 40

# ====== Coordinates (720 x 1280 resolution) ======

# Chrome page: "Use template in CapCut" button
BROWSER_USE_TEMPLATE: Tuple[int, int] = (365, 1274)

# CapCut template screen: "Use template" button
CC_USE_TEMPLATE: Tuple[int, int] = (270, 1214)

# CapCut editor: jahan tap se gallery/image selection open hota hai
CLICK_IMAGE_SECTION: Tuple[int, int] = (588, 150)

# Gallery: pehli image
GALLERY_FIRST_IMAGE: Tuple[int, int] = (150, 345)

# Gallery: confirm / next button
GALLERY_CONFIRM: Tuple[int, int] = (620, 1180)

# CapCut preview: top-right Export button
CC_EXPORT_TOP_RIGHT: Tuple[int, int] = (625, 60)

# Export complete screen: final export / save / done button
FINAL_EXPORT_BTN: Tuple[int, int] = (353, 1090)

# Ads ke coords (future ke liye; filhal use nahi ho rahe)
AD_CLOSE_X: Tuple[int, int] = (0, 0)
AD_SKIP_BTN: Tuple[int, int] = (0, 0)


# ================== HELPERS ==================

def run(cmd: List[str], wait: bool = True):
    """Generic shell command runner."""
    print(">>", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    if wait:
        out, err = proc.communicate()
        if out:
            print(out.strip())
        if err and "Warning" not in err:
            print("ERR:", err.strip())
    return proc

def adb(args: List[str], wait: bool = True):
    """Run adb command for given device."""
    cmd = ["adb", "-s", DEVICE_ID] + args
    return run(cmd, wait=wait)

def rand_sleep(tag: str = ""):
    """Random delay (general chhota wait)."""
    t = random.uniform(DELAY_MIN, DELAY_MAX)
    if tag:
        print(f"⏳ {tag} | random sleep: {t:.1f}s")
    else:
        print(f"⏳ random sleep: {t:.1f}s")
    time.sleep(t)

def fixed_sleep(sec: float, tag: str = ""):
    """Fixed delay (e.g. initial page load)."""
    if tag:
        print(f"⏳ {tag} | fixed sleep: {sec:.1f}s")
    else:
        print(f"⏳ fixed sleep: {sec:.1f}s")
    time.sleep(sec)

def tap(coord: Tuple[int, int], tag: str = ""):
    x, y = coord
    if tag:
        print(f"👆 TAP {tag}: ({x}, {y})")
    else:
        print(f"👆 TAP: ({x}, {y})")
    adb(["shell", "input", "tap", str(x), str(y)])

def keyevent(code: int, tag: str = ""):
    if tag:
        print(f"⌨ keyevent {code} ({tag})")
    else:
        print(f"⌨ keyevent {code}")
    adb(["shell", "input", "keyevent", str(code)])

def screenshot(name: str):
    remote = "/sdcard/__capcut_auto_screen.png"
    adb(["shell", "screencap", "-p", remote])
    adb(["pull", remote, name])

def get_foreground_package() -> str:
    """
    Abhi ka foreground app ka package name return karega.
    Example: 'com.android.chrome' ya 'com.lemon.lvoverseas'
    """
    try:
        proc = subprocess.Popen(
            ["adb", "-s", DEVICE_ID, "shell", "dumpsys", "window", "windows"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, _ = proc.communicate(timeout=5)
    except Exception as e:
        print("ERR get_foreground_package:", e)
        return ""

    for line in out.splitlines():
        if "mCurrentFocus" in line or "mFocusedApp" in line:
            parts = line.split()
            for part in parts:
                if "/" in part and "." in part:
                    comp = part.strip().strip("}").strip()
                    pkg = comp.split("/")[0]
                    return pkg
    return ""


# ================== STEPS ==================

def check_device() -> bool:
    print("🔍 Checking ADB devices...")
    proc = subprocess.Popen(["adb", "devices"], stdout=subprocess.PIPE, text=True)
    out, _ = proc.communicate()
    print(out)
    return DEVICE_ID in out

def open_template_in_browser(max_attempts: int = 5):
    """
    Chrome me TEMPLATE_URL open karo, button tap karo,
    7s wait (page ready), 5s wait (CapCut auto-open),
    jab tak CapCut foreground me na aa jaye retry karo.
    """
    print("🌐 Opening template in Chrome...")

    attempt = 0

    while True:
        attempt += 1
        print(f"\n🔁 Attempt #{attempt} to open CapCut via Chrome")

        # 1) Open template link in Chrome
        adb([
            "shell", "am", "start",
            "-a", "android.intent.action.VIEW",
            "-d", TEMPLATE_URL
        ])

        # 7 sec wait for page + button
        fixed_sleep(7, "wait for Chrome page & button to be ready")

        # 2) TAP the button (your working coords)
        print("▶️ Clicking 'Use template in CapCut' button...")
        tap(BROWSER_USE_TEMPLATE, "BROWSER_USE_TEMPLATE")

        # 3) CapCut ko auto-open hone ke liye 5 sec do
        fixed_sleep(9, "waiting for CapCut auto-open")

        # 4) Check if CapCut opened
        fg = get_foreground_package()
        print(f"📱 Foreground now: {fg}")

        if fg == "com.lemon.lvoverseas":
            print("✅ CapCut opened successfully!")
            return  # <-- exit function

        print("⚠️ CapCut NOT opened. Retrying...")
        fixed_sleep(2, "retry delay")

        if attempt >= max_attempts:
            print("❌ TOO MANY ATTEMPTS. Button coords/flow may be wrong.")
            return


def capcut_use_template():
    print("▶️ Clicking 'Use template' inside CapCut...")
    tap(CC_USE_TEMPLATE, "CC_USE_TEMPLATE")
    rand_sleep("after CC use template")

def select_image():
    print("🖼 Opening image section / gallery...")
    tap(CLICK_IMAGE_SECTION, "CLICK_IMAGE_SECTION")
    rand_sleep("after open gallery")

    print("🖼 Selecting first image in gallery...")
    tap(GALLERY_FIRST_IMAGE, "GALLERY_FIRST_IMAGE")
    rand_sleep("after select first image")

    print("✅ Confirming gallery selection...")
    tap(GALLERY_CONFIRM, "GALLERY_CONFIRM")
    rand_sleep("after gallery confirm")

def export_video():
    """
    1st step: top-right export button (5–7 sec chhota wait)
    2nd step: final export button + time-based wait (45–60 sec)
    """
    # 1) Top-right EXPORT (1st export)
    print("📤 Clicking EXPORT (top-right)...")
    tap(CC_EXPORT_TOP_RIGHT, "CC_EXPORT_TOP_RIGHT")

    # 1st export ke baad chhota random wait (5–7 sec)
    short_wait = random.uniform(FIRST_EXPORT_WAIT_MIN, FIRST_EXPORT_WAIT_MAX)
    print(f"⏳ Waiting {short_wait:.1f}s after first export button (UI to show 2nd export)...")
    time.sleep(short_wait)

    # 2) Final export/save button (2nd export – heavy)
    print("✅ Clicking final export/save button (2nd export)...")
    tap(FINAL_EXPORT_BTN, "FINAL_EXPORT_BTN")

    # 2nd export ke liye time-based wait (45–60 sec)
    heavy_wait = random.uniform(EXPORT_WAIT_MIN, EXPORT_WAIT_MAX)
    print(f"⏳ Waiting {heavy_wait:.1f}s for final export & download...")
    time.sleep(heavy_wait)


def one_cycle(index: int) -> bool:
    """
    Ek pure export cycle ko run karega.
    Return True = success, False = fail (exception ya major issue).
    """
    print("\n" + "=" * 60)
    print(f"🚀 STARTING CYCLE #{index + 1}")
    print("=" * 60)

    try:
        # CLEAN START — Force close both apps
        print("❌ Force closing CapCut & Chrome...")
        adb(["shell", "am", "force-stop", "com.lemon.lvoverseas"])
        adb(["shell", "am", "force-stop", "com.android.chrome"])
        rand_sleep("after force closing apps")

        # OPEN CHROME + TEMPLATE URL (until CapCut foreground)
        open_template_in_browser()

        # Double-check CapCut foreground before continuing
        fg = get_foreground_package()
        if fg != "com.lemon.lvoverseas":
            print(f"❌ CapCut is not foreground after browser flow. Got: {fg}")
            return False

        # CapCut: Use template
        capcut_use_template()

        # Select image
        select_image()

        # Export (pure time-based)
        export_video()

        # END CLEANUP — Force close again
        print("❌ Ending cycle → closing CapCut & Chrome again...")
        adb(["shell", "am", "force-stop", "com.lemon.lvoverseas"])
        adb(["shell", "am", "force-stop", "com.android.chrome"])
        rand_sleep("after final cleanup")

        print(f"🎉 CYCLE #{index + 1} DONE\n")
        return True

    except KeyboardInterrupt:
        print("⏹️ Stopped by user (Ctrl+C).")
        raise
    except Exception as e:
        print(f"⚠️ Exception in cycle #{index + 1}: {e}")
        try:
            screenshot(f"error_cycle_{index + 1}.png")
        except Exception:
            pass
        rand_sleep("after error")
        return False


# ================== MAIN ==================

def main():
    if not check_device():
        print(f"❌ Device {DEVICE_ID} not found in 'adb devices'.")
        return

    print(f"✅ Using device: {DEVICE_ID}")
    print(f"🎯 Template URL: {TEMPLATE_URL}")
    print(f"🔁 Cycles planned: {EXPORT_COUNT}")

    success_count = 0
    fail_count = 0

    for i in range(EXPORT_COUNT):
        ok = one_cycle(i)
        if ok:
            success_count += 1
        else:
            fail_count += 1

        print(f"📊 Progress after {i + 1} cycles → Success: {success_count}, Fail: {fail_count}")

    print("\n================ SUMMARY ================")
    print(f"✅ Total Success: {success_count}")
    print(f"❌ Total Fail: {fail_count}")
    print("=========================================")
    print("✅ Script finished.")


if __name__ == "__main__":
    main()


def chunk_list(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def memoize(fn):
    cache = {}
    def wrapper(*args):
        if args not in cache:
            cache[args] = fn(*args)
        return cache[args]
    return wrapper


class SingletonMeta(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


def flatten(nested: list) -> list:
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result


def paginate(items: list, page: int, per_page: int) -> dict:
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    return {
        'items': items[start:end],
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': (total + per_page - 1) // per_page,
    }


class SingletonMeta(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


def batch(iterable, n: int):
    from itertools import islice
    it = iter(iterable)
    while chunk := list(islice(it, n)):
        yield chunk


def levenshtein(s1: str, s2: str) -> int:
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if not s2:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[-1] + 1, prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]


def slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text)


def get_env(key: str, default: str = '') -> str:
    import os
    return os.environ.get(key, default)


def count_words(text: str) -> int:
    return len(text.split())
