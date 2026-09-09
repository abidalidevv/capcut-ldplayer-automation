<div align="center">
  <h1 align="center">🚀 CapCut Automation Bot For LDPlayer</h1>
  <p align="center">
    <i>Automate mass CapCut template video exports on LDPlayer Android Emulator with SOCKS5 / Rotating Proxy & VPN support.</i>
    <br />
    <br />
    <a href="#-key-features"><strong>Explore Features »</strong></a>
    ·
    <a href="#-getting-started"><strong>Quick Start »</strong></a>
    ·
    <a href="docs/DOCUMENTATION.md"><strong>Full Documentation »</strong></a>
  </p>

  ![Status](https://img.shields.io/badge/Status-Production%20Ready-success?style=for-the-badge)
  ![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
  ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20LDPlayer-purple?style=for-the-badge)
  ![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
</div>

---

## 🌟 About The Project

**CapCut Automation Bot** is a desktop automation utility built for Windows that drives an Android emulator (**LDPlayer**, 720x1280 resolution) to mass-generate videos from CapCut templates.

It automates the full creation lifecycle:
1. **Network Rotation**: Rotates through **SOCKS5/HTTP Proxies** (with authentication support) or connects via **Windscribe VPN** or runs directly.
2. **Deep-Link Intent Launch**: Opens template links directly in mobile Chrome.
3. **Smart Element Detection**: Bypasses Android popups (*"Open with"*, *"Allow Media Access"*), taps *"Use template in CapCut"*, and waits for app launch.
4. **Media Import**: Selects images from the emulator gallery and confirms.
5. **Video Export**: Triggers export, tracks completion countdown, closes apps, cleans up proxies, and repeats.

---

## ✨ Key Features

- **🎨 Modern Glassmorphism GUI**: Dark theme UI built with Tkinter, real-time live console, dynamic status updates, and countdown timers.
- **⚡ Real-Time Proxy Tester**: One-click **"⚡ Test Proxy"** button displays active Public IP, Country, and Ping latency in milliseconds directly on the UI and console.
- **🛡️ Dead Proxy Auto-Skip**: Automatically probes proxy health before starting each cycle; dead or unresponsive proxies are skipped without interrupting the queue.
- **🌐 Advanced SOCKS5 & Authenticated Proxy Support**:
  - Built-in **Zero-Config Python Proxy Bridge** (`0.0.0.0:8889`): Routes Android traffic to upstream SOCKS5 and HTTP proxies with full `Username:Password` authentication without requiring any extra APK or root on LDPlayer!
  - **📁 TXT File Rotation**: Load a `.txt` list of proxies; rotates automatically every cycle.
  - **🔗 Rotating Proxy Link / API**: Trigger mobile proxy IP refresh URLs or dynamic proxy fetch APIs before each cycle.
- **🚀 Smart Early Export Completion**: Inspects UIAutomator hierarchy to detect when rendering finishes ("Ready to share" / "Done") and skips remaining sleep—saving **15–25 seconds per video**!
- **🎯 Anti-Detection Click Jitter**: Applies randomized humanized micro-offsets (`±4px`) to tap coordinates to avoid anti-bot fingerprinting.
- **💾 Persistent Settings (`config.json`)**: Automatically saves and restores all inputs (Template URL, loops, delays, proxy settings) across sessions.
- **📱 LDPlayer Live Status & Auto-Reconnect**: Real-time emulator connection badge with one-click port probing (`127.0.0.1:5555`, `emulator-5554`).
- **🧹 Storage Full Protection**: Optional auto-cleaner removes rendered `.mp4` videos from the emulator after each cycle while keeping source gallery images safe.
- **🛡️ Fixed VPN Lifecycle**: Automated Windscribe VPN connect, minimize during cycle, and graceful disconnect at cycle end.
- **🧠 Smart Screen & Popup Handler**: Auto-dismisses Android disambiguation dialogs (*"Open with"*) and media permission prompts.
- **⚡ Safe Coordinate Fallback**: Uses UI dump inspection when available, with automatic fallback to calibrated screen coordinates.
- **⏸️ Non-Blocking Worker**: Multithreaded execution with responsive **Pause / Resume** and immediate **Stop**.
- **♾️ Infinite Mode**: Leave loop count blank to run continuously without crashes.

---

## 🛠️ Supported Proxy Formats

The built-in proxy engine automatically parses:
```text
http://host:port
http://user:pass@host:port
host:port:user:pass
socks5://host:port
socks5://user:pass@host:port
```

---

## 🚀 Getting Started

### Prerequisites
1. **Windows 10 / 11**
2. **LDPlayer 9** set to **Tablet Mode (720 x 1280)** resolution with Root / ADB debugging enabled.
3. **Python 3.10+** (if running from source).

### Running the Application

#### Option 1: Using the Standalone Executable (No Python Required)
Run `CapcutAuto.exe` directly:
```cmd
CapcutAuto.exe
```

#### Option 2: Running from Source
1. Clone the repository:
   ```bash
   git clone https://github.com/abidalidevv/capcut-ldplayer-automation.git
   cd capcut-ldplayer-automation
   ```
2. Launch using the runner script:
   ```bash
   Z-run.bat
   ```
   Or directly with Python:
   ```bash
   python capcut_gui.py
   ```

#### Option 3: Building Standalone Executable
Compile using PyInstaller:
```bash
Z-Build.bat
```

---

## 📋 Configuration Settings

| Setting | Default | Description |
|---|---|---|
| **Template URL** | *CapCut Template Link* | The target CapCut template link to open. |
| **Loop** | `100` | Number of cycles to run. Leave blank for infinite runs. |
| **Min / Max Delay** | `6s / 9s` | Random jitter delay between browser actions for human-like behavior. |
| **Export Min / Max** | `25s / 40s` | Estimated duration for CapCut video rendering. |
| **Connection Mode** | `None` | Choose between `None` (Direct), `VPN` (Windscribe), or `Proxy`. |
| **Auto-Clean Storage** | `Off` | Automatically deletes rendered MP4s from emulator to prevent disk saturation. |

---

## 📁 Repository Structure

```text
├── capcut_gui.py               # Main application source code (v2.0)
├── CapcutAuto.exe              # Standalone compiled Windows executable
├── README.md                   # Project documentation
├── requirements.txt           # Dependency declaration
├── Z-Build.bat                 # PyInstaller one-click build script
├── Z-run.bat                   # Launcher script
├── abc.bat                     # Device helper utility (Reboot, ADB devices)
├── proxy.txt                   # Sample proxy list format
├── test_proxies.txt            # Downloaded test proxy pool
├── icon.png                    # Application icon
├── tools/                      # Bundled Android Platform Tools (adb.exe & DLLs)
├── docs/                       # Comprehensive guides & documentation
│   ├── [BRAIN.md](docs/BRAIN.md)                # Master architectural blueprint & engine specification
│   ├── [DOCUMENTATION.md](docs/DOCUMENTATION.md)        # Detailed technical usage & config guide
│   └── [PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md)      # Engineering reference summary
├── OLD/                        # Dedicated folder for manual old versions
└── archive/                    # Archived scripts and previous builds
    └── builds/                 # Historical build binaries
```

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/abidalidevv/capcut-ldplayer-automation/issues).

---

<div align="center">
  <i>Developed and Maintained by <a href="https://github.com/abidalidevv">Abid Ali</a></i>
</div>
