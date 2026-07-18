import os
import time
import random
import subprocess
from typing import List, Tuple

# ================== CONFIG ==================

# ADB device id (adb devices se jo aati hai)
DEVICE_ID = "emulator-5554"

# CapCut template link
TEMPLATE_URL = "https://www.capcut.com/template-detail/7573250368646221109"

# Kitni baar ye pura flow run karna hai
EXPORT_COUNT = 1  # abhi 1 rakho, baad me badha sakte ho

# Random delay range (seconds)
DELAY_MIN = 3
DELAY_MAX = 7

# Export render ke liye special wait (zyada rakho)
EXPORT_WAIT_SECONDS = 7  # apne template ke hisaab se adjust kar sakte ho

# ====== Coordinates (720 x 1280 resolution) ======

# Chrome page: "Use template in CapCut" button
# BROWSER_USE_TEMPLATE: Tuple[int, int] = (315, 1100)
BROWSER_USE_TEMPLATE: Tuple[int, int] = (365, 1277)


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

# Ads ke coords (filhal mod pe crash aa raha hai to off rakhen)
AD_CLOSE_X: Tuple[int, int] = (0, 0)
AD_SKIP_BTN: Tuple[int, int] = (0, 0)

FINAL_EXPORT_WAIT_MIN = 25
FINAL_EXPORT_WAIT_MAX = 40

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
    """25–40 sec random delay."""
    t = random.uniform(DELAY_MIN, DELAY_MAX)
    if tag:
        print(f"⏳ {tag} | random sleep: {t:.1f}s")
    else:
        print(f"⏳ random sleep: {t:.1f}s")
    time.sleep(t)

def fixed_sleep(sec: float, tag: str = ""):
    """Fixed delay (e.g. render wait)."""
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
            # Typical: mCurrentFocus=Window{... u0 com.android.chrome/com.google...}
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

def close_capcut():
    print("❌ Force closing CapCut...")
    adb(["shell", "am", "force-stop", "com.lemon.lvoverseas"])

def open_template_in_browser(max_attempts: int = 5):
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

        # Yahan 4 sec fixed wait (button ready hone ke liye)
        fixed_sleep(4, "wait for Chrome page & button to be ready")

        # 2) TAP the button (your working coords)
        print("▶️ Clicking 'Use template in CapCut' button...")
        tap(BROWSER_USE_TEMPLATE, "BROWSER_USE_TEMPLATE")

        # 3) CapCut ko auto-open hone ke liye 5 sec do
        fixed_sleep(6, "waiting for CapCut auto-open")

        # 4) Now check if CapCut opened
        fg = get_foreground_package()
        print(f"📱 Foreground now: {fg}")

        if fg == "com.lemon.lvoverseas":
            print("✅ CapCut opened successfully!")
            return  # <-- exit loop

        print("⚠️ CapCut NOT opened. Retrying...")
        fixed_sleep(2, "retry delay")

        if attempt >= max_attempts:
            print("❌ TOO MANY ATTEMPTS. Button coords may be slightly off.")
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
    print("📤 Clicking EXPORT (top-right)...")
    tap(CC_EXPORT_TOP_RIGHT, "CC_EXPORT_TOP_RIGHT")

    # Export render wait (yahan random nahi, fixed long wait)
    fixed_sleep(EXPORT_WAIT_SECONDS, "waiting for render/export")

    # Agar normal version ho aur ad aaye to yahan handle kar sakte:
    # print("🧹 Trying to close ad...")
    # tap(AD_CLOSE_X, "AD_CLOSE_X"); rand_sleep("after ad close X")
    # tap(AD_SKIP_BTN, "AD_SKIP_BTN"); rand_sleep("after ad skip")
    print("✅ Clicking final export/save button...")
    tap(FINAL_EXPORT_BTN, "FINAL_EXPORT_BTN")

    # NEW: random wait 25–40 seconds for download to complete
    wait_time = random.uniform(FINAL_EXPORT_WAIT_MIN, FINAL_EXPORT_WAIT_MAX)
    print(f"⏳ Waiting {wait_time:.1f} seconds for final export to finish...")
    time.sleep(wait_time)


def one_cycle(index: int):
    print("\n" + "=" * 60)
    print(f"🚀 STARTING CYCLE #{index + 1}")
    print("=" * 60)

    # 0️⃣ CLEAN START — Force close both apps
    print("❌ Force closing CapCut & Chrome...")
    adb(["shell", "am", "force-stop", "com.lemon.lvoverseas"])
    adb(["shell", "am", "force-stop", "com.android.chrome"])
    rand_sleep("after force closing apps")

    # 1️⃣ OPEN CHROME + TEMPLATE URL
    open_template_in_browser()

    # 2️⃣ CapCut: Use template
    capcut_use_template()

    # 3️⃣ Select image
    select_image()

    # 4️⃣ Export
    export_video()

    # 5️⃣ END CLEANUP — Force close again
    print("❌ Ending cycle → closing CapCut & Chrome again...")
    adb(["shell", "am", "force-stop", "com.lemon.lvoverseas"])
    adb(["shell", "am", "force-stop", "com.android.chrome"])
    rand_sleep("after final cleanup")

    print(f"🎉 CYCLE #{index + 1} DONE\n")

# ================== MAIN ==================

def main():
    if not check_device():
        print(f"❌ Device {DEVICE_ID} not found in 'adb devices'.")
        return

    print(f"✅ Using device: {DEVICE_ID}")
    print(f"🎯 Template URL: {TEMPLATE_URL}")
    print(f"🔁 Cycles planned: {EXPORT_COUNT}")

    for i in range(EXPORT_COUNT):
        try:
            one_cycle(i)
        except KeyboardInterrupt:
            print("⏹️ Stopped by user (Ctrl+C).")
            break
        except Exception as e:
            print(f"⚠️ Error in cycle #{i + 1}: {e}")
            try:
                screenshot(f"error_cycle_{i + 1}.png")
            except Exception as _:
                pass
            rand_sleep("after error")

    print("✅ Script finished.")


if __name__ == "__main__":
    main()


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def remove_duplicates(lst: list) -> list:
    return list(dict.fromkeys(lst))


def human_size(n_bytes: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n_bytes < 1024:
            return f'{n_bytes:.1f} {unit}'
        n_bytes /= 1024
    return f'{n_bytes:.1f} PB'


def color_hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def snake_to_camel(name: str) -> str:
    components = name.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def is_valid_email(email: str) -> bool:
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def flatten(nested: list) -> list:
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result


def slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text)


def human_size(n_bytes: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n_bytes < 1024:
            return f'{n_bytes:.1f} {unit}'
        n_bytes /= 1024
    return f'{n_bytes:.1f} PB'


def color_hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def deep_merge(base: dict, override: dict) -> dict:
    out = base.copy()
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def zip_dicts(*dicts: dict) -> dict:
    result = {}
    for d in dicts:
        result.update(d)
    return result


class SingletonMeta(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


def get_env(key: str, default: str = '') -> str:
    import os
    return os.environ.get(key, default)


def is_palindrome(s: str) -> bool:
    cleaned = ''.join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]


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


def truncate(text: str, length: int = 100, suffix: str = '...') -> str:
    if len(text) <= length:
        return text
    return text[:length - len(suffix)] + suffix


def deep_get(d: dict, *keys, default=None):
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key, default)
    return d


def is_palindrome(s: str) -> bool:
    cleaned = ''.join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]


def batch(iterable, n: int):
    from itertools import islice
    it = iter(iterable)
    while chunk := list(islice(it, n)):
        yield chunk


def chunk_list(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


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


def get_env(key: str, default: str = '') -> str:
    import os
    return os.environ.get(key, default)


def retry(fn, attempts: int = 3, delay: float = 1.0):
    import time
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(delay)
    raise last


def zip_dicts(*dicts: dict) -> dict:
    result = {}
    for d in dicts:
        result.update(d)
    return result


def snake_to_camel(name: str) -> str:
    components = name.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def is_valid_email(email: str) -> bool:
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def snake_to_camel(name: str) -> str:
    components = name.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def batch(iterable, n: int):
    from itertools import islice
    it = iter(iterable)
    while chunk := list(islice(it, n)):
        yield chunk


def retry(fn, attempts: int = 3, delay: float = 1.0):
    import time
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(delay)
    raise last


def chunk_list(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def is_valid_email(email: str) -> bool:
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def format_currency(amount: float, symbol: str = '$') -> str:
    return f'{symbol}{amount:,.2f}'


def snake_to_camel(name: str) -> str:
    components = name.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def retry(fn, attempts: int = 3, delay: float = 1.0):
    import time
    last = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(delay)
    raise last


def chunk_list(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def human_size(n_bytes: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n_bytes < 1024:
            return f'{n_bytes:.1f} {unit}'
        n_bytes /= 1024
    return f'{n_bytes:.1f} PB'


def deep_merge(base: dict, override: dict) -> dict:
    out = base.copy()
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def deep_get(d: dict, *keys, default=None):
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key, default)
    return d


def slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text)


def remove_duplicates(lst: list) -> list:
    return list(dict.fromkeys(lst))


def zip_dicts(*dicts: dict) -> dict:
    result = {}
    for d in dicts:
        result.update(d)
    return result


def deep_get(d: dict, *keys, default=None):
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key, default)
    return d


def safe_divide(a, b, default=0):
    return a / b if b != 0 else default


def memoize(fn):
    cache = {}
    def wrapper(*args):
        if args not in cache:
            cache[args] = fn(*args)
        return cache[args]
    return wrapper

// [2026-02-01 09:00:00]
// update

// [2026-03-27 09:00:00]
// update

// [2026-04-14 09:00:00]
// update

// [2026-05-16 10:17:00]
// update

// [2026-04-05 09:00:00]
// update

// [2026-04-22 10:17:00]
// update

// [2026-06-27 09:00:00]
// update

// [2026-06-27 10:17:00]
// update

// [2026-07-11 10:17:00]
// update

// [2026-01-30 09:00:00]
// update

// [2026-02-13 09:00:00]
// update

// [2026-03-18 09:00:00]
// update

// [2026-03-31 11:34:00]
// update

// [2026-07-13 09:00:00]
// update

// [2026-02-01 09:00:00]
// update

// [2026-02-19 09:00:00]
// update

// [2026-05-31 09:00:00]
// update

// [2026-07-18 09:00:00]
// update
