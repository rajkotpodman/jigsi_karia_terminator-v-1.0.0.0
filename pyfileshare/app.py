#!/usr/bin/env python3
"""
PyFileShare - Single-File HTTPS File Server with System Tray & Auto-Start
=========================================================================

A production-ready, cross-platform desktop application that:

  * Lets you pick any local folder (or mounted Google Drive path).
  * Serves that folder over HTTP on a local port (default 8000) using
    Python's built-in ``http.server``.
  * Creates a random, secure public HTTPS link by launching a Cloudflare
    Quick Tunnel (``cloudflared``) as a background subprocess.
  * Bundles the ``cloudflared`` binary INSIDE the executable via PyInstaller
    (``--add-binary``), so the app is a single self-contained file with zero
    external runtime dependencies.
  * Can install a persistent auto-start entry (Windows Registry Run key,
    macOS LaunchAgent, or Linux systemd user service) that points directly at
    the selected folder and serves it automatically after every OS reboot.
  * Keeps running in the background (system tray) when the window is closed.

``cloudflared`` lookup order (``get_cloudflared_path``)
-------------------------------------------------------
  1. PyInstaller extraction directory (``sys._MEIPASS``) - the embedded copy.
  2. The current working directory (portable override).
  3. The application directory (where the executable lives).
  4. The system ``PATH``.

Run (source)
------------

    # 1. Install Python dependencies
    python -m pip install -r requirements.txt

    # 2. Run the GUI app
    python app.py

    # 3. Headless / CLI mode (no GUI, useful on servers and for auto-start)
    python app.py --serve /path/to/folder [--port 8000] [--no-tunnel]

Build (single-file executable with embedded cloudflared)
--------------------------------------------------------

    # Place the correct cloudflared binary in THIS folder first
    #   Windows: cloudflared.exe
    #   macOS:   cloudflared
    #   Linux:   cloudflared
    # Then run:
    pyinstaller app.spec

    # Windows installer (optional, requires Inno Setup 6):
    #   ISCC.exe installer.iss

The generated ``dist/PyFileShare`` (or ``dist/PyFileShare.exe`` /
``dist/PyFileShare.app``) is fully self-contained: run it anywhere, no
Python, no cloudflared, and no other dependency required.
"""

import json
import logging
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:  # noqa: BLE001 - pystray may fail headless (no X11/Win32/Cocoa)
    pystray = None
    Image = None
    ImageDraw = None

APP_NAME = "PyFileShare"
if getattr(sys, "frozen", False):  # PyInstaller onefile unpacks __file__ to a temp dir
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent


def _user_data_dir():
    """Per-user directory for config/logs when the app dir is not writable."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


def _writable_data_dir():
    """Prefer APP_DIR (portable mode); fall back to a per-user data dir."""
    for candidate in (APP_DIR, _user_data_dir()):
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            if os.access(candidate, os.W_OK):
                return candidate
        except OSError:
            continue
    return _user_data_dir()


DATA_DIR = _writable_data_dir()
CONFIG_FILE = DATA_DIR / "config.json"
LOG_FILE = DATA_DIR / "app.log"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_handlers = []
try:
    _handlers.append(logging.FileHandler(LOG_FILE, encoding="utf-8"))
except OSError as exc:
    sys.stderr.write(f"Warning: cannot write log at {LOG_FILE}: {exc}\n")
if sys.stdout is not None:  # sys.stdout is None under PyInstaller --noconsole
    _handlers.append(logging.StreamHandler(sys.stdout))
if not _handlers:  # never leave the logger without any handler
    _handlers.append(logging.NullHandler())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=_handlers,
)
log = logging.getLogger("pyfileshare")


class AppError(Exception):
    """Base exception for expected application failures."""


class ServerError(AppError):
    """Raised when the local HTTP server cannot start."""


class TunnelError(AppError):
    """Raised when no tunnel provider is available or a tunnel fails."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def port_is_free(port):
    """Return True if the given TCP port is available on all interfaces."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("0.0.0.0", int(port)))
            return True
        except OSError:
            return False


def find_free_port(start=8000, count=50):
    """Return the first free port at or above *start*."""
    for port in range(int(start), int(start) + int(count)):
        if port_is_free(port):
            return port
    raise ServerError(f"Could not find a free port starting at {start}")


def load_config():
    """Read config.json into a dict. Never raises."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("Could not read %s: %s", CONFIG_FILE, exc)
        return {}


def save_config(config):
    """Persist a config dict to config.json. Never raises."""
    try:
        CONFIG_FILE.write_text(
            json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError as exc:
        log.warning("Could not write %s: %s", CONFIG_FILE, exc)


# ---------------------------------------------------------------------------
# Auto-start / OS startup persistence
# ---------------------------------------------------------------------------

AUTOSTART_ID = "pyfileshare-server"  # registry value / plist label / unit name

_MAC_PLIST_LABEL = "com.pyfileshare.server"
_MAC_PLIST_PATH = Path.home() / "Library/LaunchAgents" / f"{_MAC_PLIST_LABEL}.plist"
_LINUX_UNIT_PATH = Path.home() / ".config/systemd/user" / f"{AUTOSTART_ID}.service"


def _server_command(folder, port):
    """Return the argv for this app serving *folder* headlessly at *port*."""
    args = ["--serve", folder, "--port", str(int(port))]
    if getattr(sys, "frozen", False):
        return [str(Path(sys.executable).resolve())] + args
    return [sys.executable, str(APP_DIR / "app.py")] + args


# -- Windows ---------------------------------------------------------------

def _win_run_key():
    import winreg
    return winreg.CreateKey(
        winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"
    )


def _install_autostart_windows(folder, port):
    import winreg
    command = subprocess.list2cmdline(_server_command(folder, port))
    with _win_run_key() as key:
        winreg.SetValueEx(key, AUTOSTART_ID, 0, winreg.REG_SZ, command)
    log.info("Auto-start installed (Windows Run key): %s", command)


def _uninstall_autostart_windows():
    import winreg
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.DeleteValue(key, AUTOSTART_ID)
        log.info("Auto-start removed (Windows Run key)")
    except FileNotFoundError:
        pass


def _autostart_windows_installed():
    import winreg
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ,
        ) as key:
            winreg.QueryValueEx(key, AUTOSTART_ID)
        return True
    except FileNotFoundError:
        return False


# -- macOS -----------------------------------------------------------------

def _plist_xml(folder, port):
    args = _server_command(folder, port)
    strings = "".join(f"<string>{_xml_escape(a)}</string>" for a in args)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{_MAC_PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        {strings}
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
"""


def _xml_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _install_autostart_macos(folder, port):
    _MAC_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MAC_PLIST_PATH.write_text(_plist_xml(folder, port), encoding="utf-8")
    subprocess.run(["launchctl", "unload", str(_MAC_PLIST_PATH)], capture_output=True)
    subprocess.run(["launchctl", "load", str(_MAC_PLIST_PATH)], check=True)
    log.info("Auto-start installed (LaunchAgent): %s", _MAC_PLIST_PATH)


def _uninstall_autostart_macos():
    if _MAC_PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(_MAC_PLIST_PATH)], capture_output=True)
        try:
            _MAC_PLIST_PATH.unlink()
        except OSError as exc:
            log.warning("Could not remove %s: %s", _MAC_PLIST_PATH, exc)
        log.info("Auto-start removed (LaunchAgent)")


def _autostart_macos_installed():
    return _MAC_PLIST_PATH.exists()


# -- Linux -----------------------------------------------------------------

def _systemd_unit(folder, port):
    command = subprocess.list2cmdline(_server_command(folder, port))
    return (
        "[Unit]\n"
        "Description=PyFileShare HTTPS File Server\n"
        "After=network.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={command}\n"
        "Restart=on-failure\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def _systemd(*args, check=False):
    subprocess.run(["systemctl", "--user", *args], capture_output=True, check=check)


def _install_autostart_linux(folder, port):
    _LINUX_UNIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LINUX_UNIT_PATH.write_text(_systemd_unit(folder, port), encoding="utf-8")
    _systemd("daemon-reload", check=True)
    _systemd("enable", AUTOSTART_ID)
    log.info("Auto-start installed (systemd user unit): %s", _LINUX_UNIT_PATH)


def _uninstall_autostart_linux():
    _systemd("disable", AUTOSTART_ID)
    _systemd("daemon-reload")
    if _LINUX_UNIT_PATH.exists():
        try:
            _LINUX_UNIT_PATH.unlink()
        except OSError as exc:
            log.warning("Could not remove %s: %s", _LINUX_UNIT_PATH, exc)
    log.info("Auto-start removed (systemd user unit)")


def _autostart_linux_installed():
    return _LINUX_UNIT_PATH.exists()


# -- platform dispatch ------------------------------------------------------

def install_autostart(folder, port):
    """Install an OS auto-start entry that serves *folder* on *port* at boot."""
    folder = os.path.abspath(folder)
    if not os.path.isdir(folder):
        raise AppError(f"Folder does not exist: {folder}")
    if os.name == "nt":
        _install_autostart_windows(folder, port)
    elif sys.platform == "darwin":
        _install_autostart_macos(folder, port)
    else:
        _install_autostart_linux(folder, port)


def uninstall_autostart():
    """Remove the OS auto-start entry installed by :func:`install_autostart`."""
    if os.name == "nt":
        _uninstall_autostart_windows()
    elif sys.platform == "darwin":
        _uninstall_autostart_macos()
    else:
        _uninstall_autostart_linux()


def autostart_installed():
    """Return True when this app has an active OS auto-start entry."""
    if os.name == "nt":
        return _autostart_windows_installed()
    if sys.platform == "darwin":
        return _autostart_macos_installed()
    return _autostart_linux_installed()


# ---------------------------------------------------------------------------
# Local HTTP file server
# ---------------------------------------------------------------------------

class QuietHTTPHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler that logs through the standard logger."""

    def log_message(self, fmt, *args):
        log.info("HTTP %s - %s", self.address_string(), fmt % args)


class FileServer:
    """Runs a ThreadingHTTPServer on a background daemon thread."""

    def __init__(self, directory, port=None):
        self.directory = os.path.abspath(directory)
        self.port = int(port) if port else None
        self._httpd = None
        self._thread = None

    @property
    def running(self):
        return self._httpd is not None

    def start(self):
        """Start serving. Returns the actual port in use."""
        if self._httpd is not None:
            return self.port

        if not self.port or self.port <= 0 or not port_is_free(self.port):
            self.port = find_free_port(self.port if self.port else 8000)

        handler = partial(QuietHTTPHandler, directory=self.directory)
        try:
            self._httpd = ThreadingHTTPServer(("0.0.0.0", self.port), handler)
        except OSError as exc:
            self._httpd = None
            raise ServerError(f"Cannot bind 0.0.0.0:{self.port}: {exc}") from exc

        self._thread = threading.Thread(
            target=self._httpd.serve_forever, daemon=True, name="http-server"
        )
        self._thread.start()
        log.info("HTTP server serving %s on 0.0.0.0:%s", self.directory, self.port)
        return self.port

    def stop(self):
        """Stop the server and release the port."""
        if self._httpd is not None:
            try:
                self._httpd.shutdown()
            finally:
                self._httpd.server_close()
            self._httpd = None
            self._thread = None
            log.info("HTTP server stopped")


# ---------------------------------------------------------------------------
# HTTPS tunnel management (cloudflared, portable path detection)
# ---------------------------------------------------------------------------

_TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")

_CLOUDFLARED_NAMES = ("cloudflared.exe", "cloudflared") if os.name == "nt" else ("cloudflared",)


def _meipass_dir():
    """Return PyInstaller's onefile extraction dir, or None when not frozen."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return None


def get_cloudflared_path():
    """Locate the ``cloudflared`` executable.

    Search order:
      1. PyInstaller extraction directory (``sys._MEIPASS``) - this is where
         the binary embedded with ``--add-binary`` is unpacked at runtime.
      2. The current working directory (portable override).
      3. The application directory (where the executable / ``app.py`` lives).
      4. The system ``PATH``.

    Returns the path to the executable as a string, or ``None`` if it could
    not be found anywhere.
    """
    for name in _CLOUDFLARED_NAMES:
        embedded = _meipass_dir()
        if embedded is not None:
            candidate = embedded / name
            if candidate.is_file():
                log.info("Using embedded cloudflared: %s", candidate)
                return str(candidate)
        local = Path.cwd() / name
        if local.is_file():
            log.info("Using cloudflared from working directory: %s", local)
            return str(local)
        bundled = APP_DIR / name
        if bundled.is_file():
            log.info("Using cloudflared from app folder: %s", bundled)
            return str(bundled)
        found = shutil.which(name)
        if found:
            log.info("Using cloudflared from PATH: %s", found)
            return found
    return None


class TunnelManager:
    """
    Manages a single random Cloudflare Quick Tunnel.

    ``start()`` tears down any existing tunnel and launches a brand-new one,
    which is exactly what the GUI's "Refresh Link" button needs. The public
    URL is delivered asynchronously through the ``on_ready(url)`` callback.
    """

    def __init__(self, local_port, on_ready=None, on_failed=None):
        self.local_port = int(local_port)
        self.on_ready = on_ready
        self.on_failed = on_failed
        self._lock = threading.Lock()
        self._process = None
        self._url = None
        self._stop_event = threading.Event()

    @property
    def url(self):
        with self._lock:
            return self._url

    @property
    def active(self):
        with self._lock:
            return self._url is not None

    def start(self):
        """Kill any existing tunnel and start a brand-new one."""
        with self._lock:
            self._stop_event.set()
            self._teardown_locked()
            self._url = None
            self._stop_event = threading.Event()

            cloudflared = get_cloudflared_path()
            if cloudflared is None:
                raise TunnelError(
                    "cloudflared was not found.\n\n"
                    "Either install it (see the README) or simply place the "
                    "cloudflared executable in the same folder as the app:\n"
                    f"{APP_DIR}"
                )
            self._launch_cloudflared_locked(cloudflared)
            return self._url

    def stop(self):
        """Stop the current tunnel and forget the URL."""
        with self._lock:
            self._stop_event.set()
            self._teardown_locked()
            self._url = None
            log.info("Tunnel stopped")

    # -- internals (must be called with self._lock held) -------------------

    def _teardown_locked(self):
        if self._process is not None:
            self._terminate_process_locked()

    def _terminate_process_locked(self):
        proc = self._process
        self._process = None
        if proc is None:
            return
        pid = proc.pid
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except OSError:
                pass
        except (ProcessLookupError, OSError):
            pass
        log.info("cloudflared terminated (pid %s)", pid)

    def _launch_cloudflared_locked(self, cloudflared_path):
        cmd = [
            cloudflared_path,
            "tunnel",
            "--url",
            f"http://localhost:{self.local_port}",
            "--no-autoupdate",
            "--loglevel",
            "info",
        ]
        log.info("Launching cloudflared: %s", " ".join(cmd))
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=flags,
            )
        except OSError as exc:
            self._process = None
            raise TunnelError(f"Failed to launch cloudflared: {exc}") from exc
        threading.Thread(
            target=self._read_cloudflared_output, daemon=True, name="cloudflared-reader"
        ).start()

    def _read_cloudflared_output(self):
        proc = self._process
        if proc is None:
            return
        delivered = False
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    log.info("[cloudflared] %s", line)
                match = _TUNNEL_URL_RE.search(line)
                if match and not self._stop_event.is_set():
                    with self._lock:
                        if self._url is None:
                            self._url = match.group(0)
                    if not delivered:
                        delivered = True
                        log.info("Tunnel URL ready: %s", self._url)
                        if self.on_ready is not None:
                            self.on_ready(self._url)
        except Exception as exc:  # pragma: no cover - defensive
            log.error("Error reading cloudflared output: %s", exc)
        finally:
            if (
                not self._stop_event.is_set()
                and not delivered
                and self._url is None
            ):
                log.error(
                    "cloudflared exited without producing a tunnel URL (exit=%s)",
                    proc.poll(),
                )
                if self.on_failed is not None:
                    self.on_failed(
                        "cloudflared exited without producing a tunnel URL."
                    )


# ---------------------------------------------------------------------------
# Main application (Tkinter GUI + system tray)
# ---------------------------------------------------------------------------

class PyFileShareApp:
    """Tkinter front-end plus the system-tray lifecycle manager."""

    BADGE_COLORS = {"ONLINE": "#16a34a", "OFFLINE": "#dc2626", "CONNECTING": "#d97706"}

    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} - Secure HTTPS File Server")
        self.root.geometry("680x400")
        self.root.minsize(620, 380)

        self.events = queue.Queue()  # cross-thread GUI events
        self.server = None
        self.tunnel = None
        self.tray = None
        self._stopping = threading.Event()  # set once shutdown begins

        self.cfg = load_config()
        self.selected_dir = tk.StringVar(value=self.cfg.get("folder", ""))
        self.port_var = tk.StringVar(value=str(self.cfg.get("port", 8000)))
        self.url_var = tk.StringVar()
        self.status_text = tk.StringVar(value="OFFLINE")
        self.banner_text = tk.StringVar(value="Ready")
        self.autostart_text = tk.StringVar(
            value="Auto-start: installed" if autostart_installed()
            else "Auto-start: not installed"
        )

        self._build_ui()
        self._setup_tray()
        self.root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        self.root.after(100, self._poll_events)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        row_pad = {"padx": 10, "pady": 5}

        # Folder picker
        row = ttk.Frame(self.root)
        row.pack(fill="x", **row_pad)
        ttk.Label(row, text="Folder:").pack(side="left")
        ttk.Entry(row, textvariable=self.selected_dir).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(row, text="Browse...", command=self.browse_folder).pack(side="left")

        # Port configuration
        row = ttk.Frame(self.root)
        row.pack(fill="x", **row_pad)
        ttk.Label(row, text="Port:").pack(side="left")
        ttk.Entry(row, textvariable=self.port_var, width=8).pack(side="left", padx=6)
        ttk.Label(row, text="   (default 8000)").pack(side="left")

        # Status badge
        row = ttk.Frame(self.root)
        row.pack(fill="x", **row_pad)
        self.badge = tk.Label(
            row,
            textvariable=self.status_text,
            fg="white",
            font=("Helvetica", 11, "bold"),
            padx=16,
            pady=4,
        )
        self.badge.pack(side="left")
        ttk.Label(row, textvariable=self.banner_text).pack(side="left", padx=14)

        # Live HTTPS URL
        row = ttk.Frame(self.root)
        row.pack(fill="x", **row_pad)
        ttk.Label(row, text="HTTPS URL:").pack(side="left")
        self.url_entry = ttk.Entry(row, textvariable=self.url_var, state="readonly")
        self.url_entry.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text="Copy Link", command=self.copy_link).pack(side="left")

        # Actions
        row = ttk.Frame(self.root)
        row.pack(fill="x", **row_pad)
        self.btn_start = ttk.Button(row, text="Start Server", command=self.start_server)
        self.btn_start.pack(side="left", padx=4)
        self.btn_refresh = ttk.Button(
            row, text="Refresh Link", command=self.refresh_link, state="disabled"
        )
        self.btn_refresh.pack(side="left", padx=4)
        self.btn_shutdown = ttk.Button(
            row, text="Shutdown Server", command=self.shutdown_all
        )
        self.btn_shutdown.pack(side="left", padx=4)

        # Auto-start persistence
        row = ttk.Frame(self.root)
        row.pack(fill="x", **row_pad)
        self.btn_autostart = ttk.Button(
            row, text="Install Auto-Start Server", command=self.install_autostart
        )
        self.btn_autostart.pack(side="left", padx=4)
        self.btn_autostart_remove = ttk.Button(
            row, text="Remove Auto-Start", command=self.remove_autostart
        )
        self.btn_autostart_remove.pack(side="left", padx=4)
        ttk.Label(row, textvariable=self.autostart_text).pack(side="left", padx=14)

        self._set_badge("OFFLINE")

    def _set_badge(self, status):
        self.status_text.set(status)
        self.badge.config(bg=self.BADGE_COLORS.get(status, "#6b7280"))

    def _remember_config(self):
        self.cfg["folder"] = self.selected_dir.get().strip()
        try:
            self.cfg["port"] = int(self.port_var.get().strip())
        except ValueError:
            pass
        save_config(self.cfg)

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select the folder to share")
        if folder:
            self.selected_dir.set(folder)
            self._remember_config()

    def copy_link(self):
        url = self.url_var.get()
        if not url:
            messagebox.showinfo("No link", "There is no active HTTPS link yet.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self.banner_text.set("Link copied to clipboard")

    # -------------------------------------------------- auto-start actions

    def _autostart_folder_port(self):
        folder = self.selected_dir.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror(
                "Invalid folder", "Please select a valid folder to share first."
            )
            return None, None
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid port", "The port must be a whole number.")
            return None, None
        return folder, port

    def install_autostart(self):
        folder, port = self._autostart_folder_port()
        if folder is None:
            return
        self._remember_config()
        self.btn_autostart.config(state="disabled")
        self.banner_text.set("Installing auto-start entry...")
        threading.Thread(
            target=self._autostart_install_worker, args=(folder, port), daemon=True
        ).start()

    def _autostart_install_worker(self, folder, port):
        if self._stopping.is_set():
            return
        try:
            install_autostart(folder, port)
        except Exception as exc:  # noqa: BLE001 - surface anything to the user
            log.exception("Auto-start installation failed")
            self.events.put(("error", f"Could not install auto-start: {exc}"))
            return
        self.events.put(("autostart_status", True))

    def remove_autostart(self):
        self.btn_autostart_remove.config(state="disabled")
        self.banner_text.set("Removing auto-start entry...")
        threading.Thread(target=self._autostart_remove_worker, daemon=True).start()

    def _autostart_remove_worker(self):
        if self._stopping.is_set():
            return
        try:
            uninstall_autostart()
        except Exception as exc:  # noqa: BLE001 - surface anything to the user
            log.exception("Auto-start removal failed")
            self.events.put(("error", f"Could not remove auto-start: {exc}"))
            return
        self.events.put(("autostart_status", False))

    def _set_autostart_ui(self, installed):
        if installed:
            self.autostart_text.set("Auto-start: installed")
            self.banner_text.set(
                "Auto-start installed - the folder will be served after each reboot."
            )
        else:
            self.autostart_text.set("Auto-start: not installed")
            self.banner_text.set("Auto-start removed.")
        self.btn_autostart.config(state="normal")
        self.btn_autostart_remove.config(state="normal")

    # ------------------------------------------------------- server actions

    def start_server(self):
        folder = self.selected_dir.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showerror(
                "Invalid folder", "Please select a valid folder to share first."
            )
            return
        if self.server is not None and self.server.running:
            messagebox.showinfo(
                "Already running",
                "The server is already running. Use 'Refresh Link' or "
                "'Shutdown Server' instead.",
            )
            return
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid port", "The port must be a whole number.")
            return

        self._remember_config()
        self._stopping.clear()
        self._set_badge("CONNECTING")
        self.banner_text.set("Starting local HTTP server...")
        self.btn_start.config(state="disabled")
        threading.Thread(
            target=self._start_worker, args=(folder, port), daemon=True
        ).start()

    def _start_worker(self, folder, port):
        if self._stopping.is_set():
            return
        try:
            self.server = FileServer(folder, port)
            self.server.start()
        except Exception as exc:  # noqa: BLE001 - surface anything to the user
            log.exception("Failed to start HTTP server")
            self.server = None
            self.events.put(("status_reset", None))
            self.events.put(("error", f"Failed to start server: {exc}"))
            return

        # A shutdown may have been requested while the server was starting.
        if self._stopping.is_set():
            try:
                self.server.stop()
            except Exception:  # noqa: BLE001
                pass
            self.server = None
            return

        self.events.put(("server_started", self.server.port))

        try:
            self.tunnel = TunnelManager(
                self.server.port,
                on_ready=self._on_tunnel_ready,
                on_failed=self._on_tunnel_failed,
            )
            self.tunnel.start()
        except TunnelError as exc:
            log.exception("Failed to start tunnel")
            if not self._stopping.is_set():
                self.events.put(("tunnel_failed", str(exc)))

    def refresh_link(self):
        if self.tunnel is None:
            messagebox.showinfo("Not running", "Start the server first.")
            return
        self._set_badge("CONNECTING")
        self.banner_text.set("Refreshing tunnel link...")
        self.btn_refresh.config(state="disabled")
        threading.Thread(target=self._refresh_worker, daemon=True).start()

    def _refresh_worker(self):
        try:
            self.tunnel.start()
        except TunnelError as exc:
            log.exception("Tunnel refresh failed")
            if not self._stopping.is_set():
                self.events.put(("tunnel_failed", str(exc)))

    def shutdown_all(self):
        """Stop tunnel + server, then exit."""
        self._stopping.set()
        self.btn_start.config(state="disabled")
        self.btn_refresh.config(state="disabled")
        self.btn_shutdown.config(state="disabled")
        self._set_badge("OFFLINE")
        self.banner_text.set("Shutting down...")
        threading.Thread(target=self._shutdown_worker, daemon=True).start()

    def _shutdown_worker(self):
        if self.tunnel is not None:
            try:
                self.tunnel.stop()
            except Exception as exc:  # noqa: BLE001
                log.error("Error stopping tunnel: %s", exc)
        if self.server is not None:
            try:
                self.server.stop()
            except Exception as exc:  # noqa: BLE001
                log.error("Error stopping server: %s", exc)
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed to stop tray icon: %s", exc)
        self.events.put(("shutdown_done", None))

    # --------------------------------------------- cross-thread callbacks

    def _on_tunnel_ready(self, url):
        """Called from the tunnel reader thread."""
        if self._stopping.is_set():
            return
        self.events.put(("tunnel_ready", url))

    def _on_tunnel_failed(self, message):
        if self._stopping.is_set():
            return
        self.events.put(("tunnel_failed", message))

    # ------------------------------------------------------- event loop

    def _poll_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                self._handle_event(kind, payload)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _handle_event(self, kind, payload):
        if kind == "show_gui":
            self._show_gui()
        elif kind == "shutdown":
            self.shutdown_all()
        elif kind == "server_started":
            self.banner_text.set(
                f"Local server on 0.0.0.0:{payload}. Connecting tunnel..."
            )
        elif kind == "tunnel_ready":
            self.url_var.set(payload)
            self._set_badge("ONLINE")
            self.banner_text.set("Tunnel active")
            self.btn_refresh.config(state="normal")
            self.btn_shutdown.config(state="normal")
            self.btn_start.config(state="disabled")
        elif kind == "tunnel_failed":
            self._set_badge("OFFLINE")
            self.banner_text.set("Tunnel failed. Click 'Refresh Link' to retry.")
            self.btn_refresh.config(state="normal")
            self.btn_shutdown.config(state="normal")
            self.btn_start.config(state="disabled")
            messagebox.showerror("Tunnel error", payload)
        elif kind == "error":
            messagebox.showerror("Error", payload)
        elif kind == "autostart_status":
            self._set_autostart_ui(payload)
        elif kind == "status_reset":
            self._set_badge("OFFLINE")
            self.banner_text.set("Ready")
            self.btn_start.config(state="normal")
            self.btn_refresh.config(state="disabled")
        elif kind == "shutdown_done":
            self.root.destroy()

    # ------------------------------------------------------------ tray

    def _create_tray_image(self):
        size = 64
        image = Image.new("RGB", (size, size), "#1e1e2e")
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((10, 10, size - 10, size - 10), radius=12, fill="#16a34a")
        draw.rectangle((24, 24, size - 24, size - 24), fill="#ffffff")
        return image

    def _setup_tray(self):
        if pystray is None or Image is None:
            log.warning("pystray/Pillow not installed; system tray disabled")
            self.tray = None
            return
        try:
            menu = pystray.Menu(
                pystray.MenuItem("Show GUI", self._tray_show),
                pystray.MenuItem("Shutdown & Exit", self._tray_shutdown),
            )
            self.tray = pystray.Icon(
                "pyfileshare",
                self._create_tray_image(),
                f"{APP_NAME} - HTTPS File Server",
                menu,
            )
            # run_detached() must be called from the main thread (macOS-safe).
            self.tray.run_detached()
            log.info("System tray icon active")
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to initialize system tray: %s", exc)
            self.tray = None

    def _tray_show(self, _icon, _item):
        self.events.put(("show_gui", None))

    def _tray_shutdown(self, _icon, _item):
        self.events.put(("shutdown", None))

    def _show_gui(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        if self.tunnel is not None and self.tunnel.active:
            self.banner_text.set("Tunnel active")
        else:
            self.banner_text.set("Ready")

    def _hide_to_tray(self):
        if self.tray is not None:
            self.banner_text.set("Running in background (system tray).")
            self.root.withdraw()
        else:
            self.shutdown_all()


# ---------------------------------------------------------------------------
# Headless / CLI mode (useful on servers and for smoke tests)
# ---------------------------------------------------------------------------

def run_cli(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=f"{APP_NAME} headless mode")
    parser.add_argument("--serve", help="Folder to serve over HTTPS")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-tunnel", action="store_true", help="Serve locally only")
    args = parser.parse_args(argv)

    folder = args.serve or os.environ.get("PYFILESHARE_FOLDER")
    if not folder or not os.path.isdir(folder):
        parser.error("Provide an existing folder with --serve /path/to/folder")
        return 2

    server = FileServer(folder, args.port)
    port = server.start()
    print(f"Local server: http://localhost:{port}")

    manager = None
    if not args.no_tunnel:
        manager = TunnelManager(
            port,
            on_ready=lambda url: print(f"PUBLIC_URL={url}"),
            on_failed=lambda msg: print(f"TUNNEL_ERROR={msg}"),
        )
        try:
            manager.start()
        except TunnelError as exc:
            print(f"Tunnel error: {exc}")
    else:
        print("Tunnel disabled (--no-tunnel).")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if manager is not None:
            try:
                manager.stop()
            except Exception:  # noqa: BLE001
                pass
        server.stop()
        print("Stopped.")
    return 0


def main():
    if "--serve" in sys.argv or os.environ.get("PYFILESHARE_HEADLESS") == "1":
        sys.exit(run_cli())
    root = tk.Tk()
    PyFileShareApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
