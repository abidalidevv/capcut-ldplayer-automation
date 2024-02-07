import os
import time
import random
import subprocess
from typing import List, Tuple, Optional

# ================== CONFIG ==================

# ADB device id (adb devices se jo aati hai)
DEVICE_ID = "emulator-5554"

# CapCut template link (Chrome me ye open hoga)
TEMPLATE_URL = "https://www.capcut.com/template-detail/7573250368646221109"

# Kitni baar ye pura flow run karna hai
EXPORT_COUNT = 10  # 10 bar export loop

# Random delay range (seconds) - general small waits
DELAY_MIN = 4
DELAY_MAX = 7

# 1st export (top-right) ke baad chhota wait (seconds)
FIRST_EXPORT_WAIT_MIN = 5
FIRST_EXPORT_WAIT_MAX = 7

# 2nd export (heavy render) ke liye CPU-based max wait (seconds)
SECOND_EXPORT_CPU_MAX_WAIT = 45  # typical 25–40, upper cap 45

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

# Ads ke coords (filhal mod pe crash aa raha hai to off rakhen)
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
    """Random delay."""
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


def get_capcut_cpu() -> Optional[float]:
    """
    'top' se CapCut process ka CPU% estimate karega.
    """
    try:
        proc = subprocess.Popen(
            ["adb", "-s", DEVICE_ID, "shell", "top -n 1 | grep com.lemon.lvoverseas"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        out, err = proc.communicate(timeout=5)
        if not out or not out.strip():
            return None
        line = out.strip().splitlines()[0]
        tokens = line.split()
        # token jisme '%' ho, usse number nikaal lenge
        for tok in tokens:
            if "%" in tok:
                num = "".join(c for c in tok if (c.isdigit() or c == "."))
                if num:
                    try:
                        cpu_val = float(num)
                        print(f"🔍 CapCut CPU: {cpu_val}%")
                        return cpu_val
                    except ValueError:
                        continue
        return None
    except Exception as e:
        print("ERR get_capcut_cpu:", e)
        return None


def wait_for_export_cpu(max_wait: int) -> bool:
    """
    CPU-based detection for export completion.
    Jab tak CPU high hai, render chal raha hota hai.
    Jab CPU kuch time tak low ho jaye, assume export done.
    """
    print(f"🧠 CPU-based export wait (max {max_wait}s)...")
    start = time.time()
    stable_low = 0
    STABLE_NEEDED = 3         # itne samples low hone chahiye
    INTERVAL = 5              # har 5 sec me check
    CPU_THRESHOLD = 15.0      # is se kam hua to low maana

    while True:
        elapsed = time.time() - start
        if elapsed > max_wait:
            print("⌛ CPU-based wait timeout reached.")
            return False

        cpu = get_capcut_cpu()
        if cpu is None:
            print("⚠️ CapCut CPU not found, resetting stable counter.")
            stable_low = 0
        elif cpu < CPU_THRESHOLD:
            stable_low += 1
            print(f"✅ CPU below threshold ({cpu} < {CPU_THRESHOLD}), stable_low={stable_low}")
            if stable_low >= STABLE_NEEDED:
                print("🎯 CPU stable low — export likely finished.")
                return True
        else:
            print(f"⚠️ CPU still high ({cpu} >= {CPU_THRESHOLD}), resetting stable counter.")
            stable_low = 0

        time.sleep(INTERVAL)


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
        fixed_sleep(8, "waiting for CapCut auto-open")

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

def export_video() -> bool:
    """
    1st step: top-right export button (5–7 sec chhota wait)
    2nd step: final export button + CPU-based detection (25–40 sec heavy work)
    Return True if CPU-based wait succeeded, False if timeout.
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

    # 2nd export ke liye CPU-based wait (25–40 sec typical, max ~45)
    cpu_ok = wait_for_export_cpu(max_wait=SECOND_EXPORT_CPU_MAX_WAIT)

    if not cpu_ok:
        print("⚠️ CPU-based export detection timed out (2nd export).")
    else:
        print("🎯 CPU-based export detection says: finished.")

    # At the very end, thoda extra safety wait de dete hain
    extra = random.uniform(3, 6)
    print(f"⏳ Extra safety wait {extra:.1f}s after CPU detection...")
    time.sleep(extra)

    return cpu_ok


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

        # Export
        cpu_ok = export_video()

        # END CLEANUP — Force close again
        print("❌ Ending cycle → closing CapCut & Chrome again...")
        adb(["shell", "am", "force-stop", "com.lemon.lvoverseas"])
        adb(["shell", "am", "force-stop", "com.android.chrome"])
        rand_sleep("after final cleanup")

        if not cpu_ok:
            print(f"⚠️ Cycle #{index + 1}: export CPU detection failed (timeout).")
            return False

        print(f"🎉 CYCLE #{index + 1} DONE (CPU-based export OK)\n")
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



# Chrome button se pehle → 7s
# Chrome button ke baad CapCut → 5s
# Top-right export ke baad → 5–7s
# 2nd export heavy render → CPU-based up to ~45s
# End pe extra 3–6s

# im[put feld main user apna link dyga 
# atomate loop main btaye ga k loop kitni bar chalana hy if empty ye infinite loop chly ga until stop 
# random delay min max main 6 - 8 ye random time h delays ka jo ab kam kr rha hasattr
# Export Rand time ramdom tme hy  e.g. 2nd export 45-60 s
# Load .txt proxy file main agr file upload krdi to open say phly proxy load hogi otherwise jesy abi chl raha hy wesy e clta ahy ga 
# agr  vpn wala butto check kr dya tu is main kuch cord or add h jayein gy jo ik vpn application ko open krain gy start main phr baki flow chly ga or eend main wo vpn ko close kr dy gy 
# Counter btaye ga kitny expiort h gye 
# Remainin btaye ga kitny rh gyem(agr  automate loop koi number hoga tu thk otherwise remainng or time wala XXX aye ga) , ya Unlimited 
# Expected time bteye ga kitna timee  or lgy ga sb export krny main 


# Start say start hoga rpgram 
# Stop  say stop hoga progrmam




def count_words(text: str) -> int:
    return len(text.split())


def read_json(path: str) -> dict:
    import json
    from pathlib import Path
    return json.loads(Path(path).read_text(encoding='utf-8'))


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in ('1', 'true', 'yes', 'on')


def get_env(key: str, default: str = '') -> str:
    import os
    return os.environ.get(key, default)


def color_hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def format_currency(amount: float, symbol: str = '$') -> str:
    return f'{symbol}{amount:,.2f}'


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


def chunk_list(lst: list, size: int):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def timer(fn):
    import time, functools
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = time.perf_counter() - t0
        print(f'{fn.__name__} took {elapsed:.4f}s')
        return result
    return wrapper


def unique_preserve_order(seq: list) -> list:
    seen = set()
    return [x for x in seq if not (x in seen or seen.add(x))]


def safe_divide(a, b, default=0):
    return a / b if b != 0 else default


def human_size(n_bytes: int) -> str:
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n_bytes < 1024:
            return f'{n_bytes:.1f} {unit}'
        n_bytes /= 1024
    return f'{n_bytes:.1f} PB'


def count_words(text: str) -> int:
    return len(text.split())


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def get_env(key: str, default: str = '') -> str:
    import os
    return os.environ.get(key, default)


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


def read_json(path: str) -> dict:
    import json
    from pathlib import Path
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path: str, data: dict, indent: int = 2) -> None:
    import json
    from pathlib import Path
    Path(path).write_text(json.dumps(data, indent=indent, ensure_ascii=False))


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def read_json(path: str) -> dict:
    import json
    from pathlib import Path
    return json.loads(Path(path).read_text(encoding='utf-8'))


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


def is_palindrome(s: str) -> bool:
    cleaned = ''.join(c.lower() for c in s if c.isalnum())
    return cleaned == cleaned[::-1]


def unique_preserve_order(seq: list) -> list:
    seen = set()
    return [x for x in seq if not (x in seen or seen.add(x))]


def memoize(fn):
    cache = {}
    def wrapper(*args):
        if args not in cache:
            cache[args] = fn(*args)
        return cache[args]
    return wrapper


def flatten(nested: list) -> list:
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(flatten(item))
        else:
            result.append(item)
    return result


def count_words(text: str) -> int:
    return len(text.split())


def write_json(path: str, data: dict, indent: int = 2) -> None:
    import json
    from pathlib import Path
    Path(path).write_text(json.dumps(data, indent=indent, ensure_ascii=False))


def is_valid_email(email: str) -> bool:
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def camel_to_snake(name: str) -> str:
    import re
    s1 = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def read_json(path: str) -> dict:
    import json
    from pathlib import Path
    return json.loads(Path(path).read_text(encoding='utf-8'))


def get_env(key: str, default: str = '') -> str:
    import os
    return os.environ.get(key, default)


def deep_get(d: dict, *keys, default=None):
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key, default)
    return d


def memoize(fn):
    cache = {}
    def wrapper(*args):
        if args not in cache:
            cache[args] = fn(*args)
        return cache[args]
    return wrapper


def is_valid_email(email: str) -> bool:
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '-', text)


def unique_preserve_order(seq: list) -> list:
    seen = set()
    return [x for x in seq if not (x in seen or seen.add(x))]


def memoize(fn):
    cache = {}
    def wrapper(*args):
        if args not in cache:
            cache[args] = fn(*args)
        return cache[args]
    return wrapper
