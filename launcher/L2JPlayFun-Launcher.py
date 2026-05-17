#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L2J Play Fun Launcher v10
=========================
Windows launcher for Lineage II server.
- Parallel downloads (8 threads)
- Download speed display
- Orphaned file cleanup on verify
- Custom alert dialogs (no Windows messagebox)
- Handles UAC elevation for game launch
- No redundant success popups (status bar only)
- Download progress shown during verify
"""

import os
import sys
import json
import hashlib
import threading
import time
import concurrent.futures
import urllib.request
import urllib.error
from tkinter import (
    Tk, Frame, Label, Button, Entry, StringVar, IntVar,
    filedialog, ttk, PhotoImage, Toplevel
)
import subprocess
import shutil

# ─── CONFIG ───────────────────────────────────────────────────────
CONFIG_FILE = os.path.expanduser("~/.l2jplayfun-launcher.ini")
DEFAULT_IP = "la2play.fun"
DEFAULT_PORT = "8080"
GAME_DIR_NAME = "Lineage2PlayFun"
EXE_NAME = "l2.exe"
VERSION_FILE = "version.txt"
DOWNLOAD_WORKERS = 8
CHUNK_SIZE = 262144  # 256 KB

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"ip": DEFAULT_IP, "port": DEFAULT_PORT}
    import configparser
    config = configparser.ConfigParser()
    try:
        config.read(CONFIG_FILE, encoding="utf-8")
        return {
            "ip": config.get("Server", "ip", fallback=DEFAULT_IP),
            "port": config.get("Server", "port", fallback=DEFAULT_PORT),
        }
    except Exception:
        return {"ip": DEFAULT_IP, "port": DEFAULT_PORT}

def save_config(ip, port):
    import configparser
    config = configparser.ConfigParser()
    config["Server"] = {"ip": ip, "port": port}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        config.write(f)

_cfg = load_config()
SERVER_IP = _cfg["ip"]
SERVER_PORT = _cfg["port"]
SERVER_URL = f"http://{SERVER_IP}:{SERVER_PORT}"
API_URL = f"{SERVER_URL}/launcher/api.php"
STATUS_URL = f"{SERVER_URL}/api.php"
# ──────────────────────────────────────────────────────────────────

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def suppress_windows_error_dialogs():
    """Prevent Windows from showing system error dialogs."""
    if os.name == 'nt':
        import ctypes
        SEM_FAILCRITICALERRORS = 0x0001
        SEM_NOGPFAULTERRORBOX = 0x0002
        SEM_NOOPENFILEERRORBOX = 0x8000
        ctypes.windll.kernel32.SetErrorMode(
            SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX
        )


class ServerStatus:
    def __init__(self, root, parent_frame):
        self.frame = Frame(parent_frame, bg="#0a0e1a", bd=0)
        self.frame.pack(fill="x", pady=(0, 15))
        self.login_var = StringVar(value="Перевірка...")
        self.game_var = StringVar(value="Перевірка...")
        self.players_var = StringVar(value="—")
        cards = [
            ("LOGIN SERVER", self.login_var, "#4caf50"),
            ("PLAYERS", self.players_var, "#d4af37"),
            ("GAME SERVER", self.game_var, "#4caf50"),
        ]
        for title, var, color in cards:
            card = Frame(self.frame, bg="#12182e", bd=1, relief="solid",
                         highlightbackground="#1a1f35", highlightthickness=1)
            card.pack(side="left", expand=True, fill="both", padx=5, pady=2)
            Label(card, text=title, font=("Segoe UI", 8, "bold"),
                  bg="#12182e", fg="#666", pady=5).pack()
            Label(card, textvariable=var, font=("Segoe UI", 14, "bold"),
                  bg="#12182e", fg=color, pady=5).pack()
        self.refresh_status()

    def refresh_status(self):
        def fetch():
            try:
                req = urllib.request.Request(
                    f"{STATUS_URL}?action=status",
                    headers={"User-Agent": "L2JPlayFun-Launcher"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.login_var.set(
                        "ONLINE" if data.get("login_status") == "online" else "OFFLINE"
                    )
                    self.game_var.set(
                        "ONLINE" if data.get("game_status") == "online" else "OFFLINE"
                    )
                    self.players_var.set(str(data.get("players_online", "—")))
            except Exception:
                self.login_var.set("?")
                self.game_var.set("?")
                self.players_var.set("?")
        threading.Thread(target=fetch, daemon=True).start()
        self.frame.after(15000, self.refresh_status)


class LauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("L2J Play Fun — Launcher")
        self.root.geometry("720x700")
        self.root.configure(bg="#0a0e1a")
        self.root.resizable(False, False)
        try:
            self.root.iconbitmap(resource_path("launcher.ico"))
        except Exception:
            pass
        self.game_path = StringVar()
        self.status_text = StringVar(value="Виберіть директорію та натисніть Встановити")
        self.progress = IntVar(value=0)
        self.speed_text = StringVar(value="")
        self.local_version = StringVar(value="Немає")
        self.remote_version = StringVar(value="—")
        self.is_installing = False
        self.load_saved_path()
        self.build_ui()
        self.check_version()

    def load_saved_path(self):
        config = os.path.expanduser("~/.l2jplayfun.conf")
        if os.path.exists(config):
            try:
                with open(config, "r", encoding="utf-8") as f:
                    saved = f.read().strip()
                    if saved:
                        self.game_path.set(os.path.normpath(saved))
            except Exception:
                pass

    def save_path(self):
        config = os.path.expanduser("~/.l2jplayfun.conf")
        try:
            with open(config, "w", encoding="utf-8") as f:
                f.write(self.game_path.get())
        except Exception:
                pass

    # ─── CUSTOM ALERTS (no Windows messagebox) ─────────────────────
    def show_alert(self, title, message, msg_type="info"):
        """Show a custom styled alert dialog inside the launcher (no Windows messagebox)."""
        def _create():
            win = Toplevel(self.root)
            win.title(title)
            win.configure(bg="#0a0e1a")
            win.geometry("450x200")
            win.resizable(False, False)
            win.transient(self.root)
            win.grab_set()
            win.focus_force()

            # Icon color based on type
            icon_color = "#4caf50" if msg_type == "info" else "#d4af37" if msg_type == "warning" else "#f44336"
            icon_text = "✓" if msg_type == "info" else "⚠" if msg_type == "warning" else "✗"

            Label(win, text=icon_text, font=("Segoe UI", 32), bg="#0a0e1a", fg=icon_color).pack(pady=(15, 5))
            Label(win, text=title, font=("Segoe UI", 12, "bold"), bg="#0a0e1a", fg="#fff").pack()
            Label(win, text=message, font=("Segoe UI", 10), bg="#0a0e1a", fg="#ccc",
                  wraplength=400, justify="center").pack(pady=10, padx=20)

            btn_color = "#1a2a4a"
            btn_fg = "#4a90d9"
            btn_hover = "#2a3a5a"
            btn = Button(win, text="OK", font=("Segoe UI", 10, "bold"),
                         bg=btn_color, fg=btn_fg, activebackground=btn_hover, activeforeground="#fff",
                         relief="flat", padx=30, pady=5, cursor="hand2",
                         command=win.destroy)
            btn.pack(pady=10)

            win.protocol("WM_DELETE_WINDOW", win.destroy)
            win.bind("<Return>", lambda e: win.destroy())
            win.bind("<Escape>", lambda e: win.destroy())

            # Center the window
            win.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (win.winfo_width() // 2)
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (win.winfo_height() // 2)
            win.geometry(f"+{x}+{y}")

        self.root.after(0, _create)

    def show_yesno(self, title, message, on_yes, on_no=None):
        """Show a custom yes/no dialog inside the launcher."""
        def _create():
            win = Toplevel(self.root)
            win.title(title)
            win.configure(bg="#0a0e1a")
            win.geometry("450x200")
            win.resizable(False, False)
            win.transient(self.root)
            win.grab_set()
            win.focus_force()

            Label(win, text="⚠", font=("Segoe UI", 32), bg="#0a0e1a", fg="#d4af37").pack(pady=(15, 5))
            Label(win, text=title, font=("Segoe UI", 12, "bold"), bg="#0a0e1a", fg="#fff").pack()
            Label(win, text=message, font=("Segoe UI", 10), bg="#0a0e1a", fg="#ccc",
                  wraplength=400, justify="center").pack(pady=10, padx=20)

            btn_frame = Frame(win, bg="#0a0e1a")
            btn_frame.pack(pady=10)

            def _yes():
                win.destroy()
                if on_yes:
                    on_yes()

            def _no():
                win.destroy()
                if on_no:
                    on_no()

            Button(btn_frame, text="Так", font=("Segoe UI", 10, "bold"),
                   bg="#c62828", fg="#fff", activebackground="#8e0000",
                   relief="flat", padx=25, pady=5, cursor="hand2",
                   command=_yes).pack(side="left", padx=10)
            Button(btn_frame, text="Ні", font=("Segoe UI", 10, "bold"),
                   bg="#1a2a4a", fg="#4a90d9", activebackground="#2a3a5a",
                   relief="flat", padx=25, pady=5, cursor="hand2",
                   command=_no).pack(side="left", padx=10)

            win.protocol("WM_DELETE_WINDOW", _no)
            win.bind("<Return>", lambda e: _yes())
            win.bind("<Escape>", lambda e: _no())

            win.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (win.winfo_width() // 2)
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (win.winfo_height() // 2)
            win.geometry(f"+{x}+{y}")

        self.root.after(0, _create)

    # ───────────────────────────────────────────────────────────────

    def build_ui(self):
        header = Frame(self.root, bg="#0a0e1a", height=160)
        header.pack(fill="x")
        header.pack_propagate(False)
        try:
            img_path = resource_path("logo_128.png")
            if os.path.exists(img_path):
                self.logo_img = PhotoImage(file=img_path)
                Label(header, image=self.logo_img, bg="#0a0e1a").pack(pady=(10, 0))
        except Exception:
            pass
        Label(header, text="L2J PLAY FUN", font=("Orbitron", 24, "bold"),
              bg="#0a0e1a", fg="#d4af37").pack(pady=(5, 0))
        Label(header, text="EPIC CHRONICLES — HIGH FIVE", font=("Segoe UI", 9),
              bg="#0a0e1a", fg="#4a90d9").pack()
        self.status_widget = ServerStatus(self.root, self.root)
        content = Frame(self.root, bg="#0a0e1a")
        content.pack(fill="both", expand=True, padx=30, pady=10)
        dir_frame = Frame(content, bg="#0a0e1a")
        dir_frame.pack(fill="x", pady=5)
        Label(dir_frame, text="Директорія:", font=("Segoe UI", 10),
              bg="#0a0e1a", fg="#ccc").pack(side="left")
        self.path_entry = Entry(dir_frame, textvariable=self.game_path, font=("Segoe UI", 9),
                                bg="#1a2332", fg="#fff", insertbackground="#fff",
                                relief="flat", width=42, state="readonly",
                                readonlybackground="#1a2332", disabledforeground="#fff")
        self.path_entry.pack(side="left", padx=5)
        btn_style = {"font": ("Segoe UI", 9, "bold"), "bg": "#1a2a4a",
                     "fg": "#4a90d9", "activebackground": "#2a3a5a",
                     "activeforeground": "#fff", "relief": "flat",
                     "padx": 15, "pady": 5, "cursor": "hand2"}
        Button(dir_frame, text="Вибрати...", command=self.select_dir, **btn_style).pack(side="left", padx=5)
        ver_frame = Frame(content, bg="#0a0e1a")
        ver_frame.pack(fill="x", pady=5)
        Label(ver_frame, text="Локальна:", font=("Segoe UI", 9),
              bg="#0a0e1a", fg="#888").pack(side="left")
        Label(ver_frame, textvariable=self.local_version, font=("Segoe UI", 9, "bold"),
              bg="#0a0e1a", fg="#d4af37").pack(side="left", padx=5)
        Label(ver_frame, text="Серверна:", font=("Segoe UI", 9),
              bg="#0a0e1a", fg="#888").pack(side="left", padx=(20, 0))
        Label(ver_frame, textvariable=self.remote_version, font=("Segoe UI", 9, "bold"),
              bg="#0a0e1a", fg="#4a90d9").pack(side="left", padx=5)
        # Server settings
        server_frame = Frame(content, bg="#0a0e1a")
        server_frame.pack(fill="x", pady=5)
        Label(server_frame, text="Адреса сервера:", font=("Segoe UI", 9),
              bg="#0a0e1a", fg="#888").pack(side="left")
        self.ip_entry = Entry(server_frame, font=("Segoe UI", 9),
                              bg="#1a2332", fg="#fff", insertbackground="#fff",
                              relief="flat", width=18)
        self.ip_entry.insert(0, SERVER_IP)
        self.ip_entry.pack(side="left", padx=5)
        Label(server_frame, text=":", font=("Segoe UI", 9, "bold"),
              bg="#0a0e1a", fg="#888").pack(side="left")
        self.port_entry = Entry(server_frame, font=("Segoe UI", 9),
                                bg="#1a2332", fg="#fff", insertbackground="#fff",
                                relief="flat", width=6)
        self.port_entry.insert(0, SERVER_PORT)
        self.port_entry.pack(side="left", padx=5)
        Button(server_frame, text="💾", command=self.save_server_settings,
               font=("Segoe UI", 8), bg="#1a2a4a", fg="#4a90d9",
               activebackground="#2a3a5a", relief="flat", width=3,
               cursor="hand2").pack(side="left", padx=5)
        Frame(content, bg="#1a1f35", height=1).pack(fill="x", pady=10)
        self.progress_bar = ttk.Progressbar(content, variable=self.progress,
                                           maximum=100, length=500, mode="determinate")
        self.progress_bar.pack(fill="x", pady=10)
        self.speed_label = Label(content, textvariable=self.speed_text,
                                 font=("Segoe UI", 9, "bold"),
                                 bg="#0a0e1a", fg="#4a90d9")
        self.speed_label.pack()
        Label(content, textvariable=self.status_text, font=("Segoe UI", 9),
              bg="#0a0e1a", fg="#aaa", wraplength=500).pack()
        btn_frame = Frame(content, bg="#0a0e1a")
        btn_frame.pack(pady=15)
        action_style = {"font": ("Segoe UI", 10, "bold"), "width": 14,
                        "relief": "flat", "padx": 10, "pady": 8, "cursor": "hand2"}
        self.btn_install = Button(btn_frame, text="⬇ Встановити",
                                  command=self.start_install,
                                  bg="#2e7d32", fg="#fff",
                                  activebackground="#1b5e20", **action_style)
        self.btn_install.pack(side="left", padx=5)
        self.btn_verify = Button(btn_frame, text="🔍 Перевірити",
                                 command=self.start_verify,
                                 bg="#1565c0", fg="#fff",
                                 activebackground="#0d47a1", **action_style)
        self.btn_verify.pack(side="left", padx=5)
        self.btn_launch = Button(btn_frame, text="▶ Запустити",
                                 command=self.start_launch,
                                 bg="#d4af37", fg="#0a0e1a",
                                 activebackground="#f0d878", **action_style)
        self.btn_launch.pack(side="left", padx=5)
        self.btn_delete = Button(btn_frame, text="🗑 Видалити",
                                 command=self.delete_game,
                                 bg="#c62828", fg="#fff",
                                 activebackground="#8e0000", **action_style)
        self.btn_delete.pack(side="left", padx=5)
        footer = Frame(self.root, bg="#0a0e1a")
        footer.pack(fill="x", pady=(0, 10))
        Label(footer, text="L2J Play Fun Launcher v10.0 | github.com/AriesT/l2j-playfun-launcher",
              font=("Segoe UI", 8), bg="#0a0e1a", fg="#444").pack()

    def save_server_settings(self):
        ip = self.ip_entry.get().strip()
        port = self.port_entry.get().strip()
        if not ip or not port.isdigit():
            self.show_alert("Помилка", "Введіть коректний IP та порт", "error")
            return
        save_config(ip, port)
        self.show_alert("Збережено",
            f"Налаштування сервера оновлено!\n\n"
            f"Адреса: {ip}:{port}\n"
            f"Перезапустіть лаунчер для застосування.", "info")

    def select_dir(self):
        path = filedialog.askdirectory(title="Виберіть директорію для гри")
        if path:
            full_path = os.path.normpath(os.path.join(path, GAME_DIR_NAME))
            self.game_path.set(full_path)
            self.save_path()
            self.check_version()

    def get_local_version(self):
        ver_file = os.path.join(self.game_path.get(), VERSION_FILE)
        if os.path.exists(ver_file):
            try:
                with open(ver_file, "r") as f:
                    return f.read().strip()
            except Exception:
                pass
        return None

    def check_version(self):
        local = self.get_local_version()
        self.local_version.set(local if local else "Немає")
        def fetch_remote():
            try:
                req = urllib.request.Request(
                    f"{API_URL}?action=version",
                    headers={"User-Agent": "L2JPlayFun-Launcher"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    self.remote_version.set(data.get("version", "—"))
            except Exception:
                self.remote_version.set("?")
        threading.Thread(target=fetch_remote, daemon=True).start()

    def get_full_game_dir(self):
        return self.game_path.get()

    def start_install(self):
        if self.is_installing:
            return
        if not self.game_path.get():
            self.show_alert("Помилка", "Спочатку виберіть директорію!", "error")
            return
        threading.Thread(target=self._safe_thread, args=(self.install_game,), daemon=True).start()

    def start_verify(self):
        if self.is_installing:
            return
        if not self.game_path.get() or not os.path.exists(self.game_path.get()):
            self.show_alert("Помилка", "Гра не встановлена!", "error")
            return
        threading.Thread(target=self._safe_thread, args=(self.verify_game,), daemon=True).start()

    def start_launch(self):
        threading.Thread(target=self._safe_thread, args=(self.launch_game,), daemon=True).start()

    def _safe_thread(self, target_func):
        """Wrapper to catch all exceptions and show in launcher (no Windows dialog)."""
        try:
            target_func()
        except Exception as e:
            self.root.after(0, lambda: self.show_alert("Помилка", str(e), "error"))
            self.root.after(0, lambda: self.set_status(f"❌ Помилка: {e}", 0))
            self.root.after(0, lambda: self.set_buttons_state("normal"))
            self.is_installing = False

    def install_game(self):
        self.is_installing = True
        self.set_buttons_state("disabled")
        self.download_stats = None
        self.stop_ui_update = threading.Event()
        try:
            game_dir = self.get_full_game_dir()
            os.makedirs(game_dir, exist_ok=True)
            self.set_status("Отримання списку файлів...", 5)
            self.set_speed_text("")
            req = urllib.request.Request(
                f"{API_URL}?action=manifest",
                headers={"User-Agent": "L2JPlayFun-Launcher"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if "error" in data:
                raise Exception(f"Server error: {data['error']}")
            files = data.get("files", [])
            if not files:
                raise Exception("Файли гри не знайдені на сервері")
            total = len(files)
            remote_version = data.get("version", "1.0.0")

            # Determine which files actually need downloading
            files_to_download = []
            self.set_status(f"Аналіз {total} файлів...", 8)
            for f_info in files:
                rel_path = f_info["path"]
                expected_md5 = f_info["md5"]
                local_file = os.path.join(game_dir, rel_path.replace("/", os.sep))
                if os.path.exists(local_file):
                    local_md5 = self.get_md5(local_file)
                    if local_md5 and local_md5 == expected_md5:
                        continue
                files_to_download.append(f_info)

            if not files_to_download:
                self._write_version(game_dir, remote_version)
                self.set_status("✅ Всі файли актуальні!", 100)
                self.set_speed_text("")
                self.show_alert("Готово", "Всі файли вже актуальні.", "info")
                return

            # Shared stats for UI updates
            self.download_stats = {
                "processed": 0,
                "total": len(files_to_download),
                "start_time": time.time(),
                "total_bytes": 0,
                "lock": threading.Lock(),
                "errors": [],
                "cancelled": False,
            }

            def download_worker(f_info):
                if self.download_stats["cancelled"]:
                    return
                rel_path = f_info["path"]
                file_url = f_info["url"]
                expected_md5 = f_info["md5"]
                local_file = os.path.join(game_dir, rel_path.replace("/", os.sep))
                try:
                    bytes_dl = self.download_file_with_size(file_url, local_file, expected_md5)
                    with self.download_stats["lock"]:
                        self.download_stats["processed"] += 1
                        self.download_stats["total_bytes"] += bytes_dl
                except Exception as e:
                    with self.download_stats["lock"]:
                        self.download_stats["errors"].append(f"{rel_path}: {e}")
                        self.download_stats["cancelled"] = True

            # Start UI update background thread
            ui_thread = threading.Thread(target=self._ui_update_loop, daemon=True)
            ui_thread.start()

            max_workers = min(DOWNLOAD_WORKERS, len(files_to_download))
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(download_worker, f) for f in files_to_download]
                concurrent.futures.wait(futures)

            self.stop_ui_update.set()

            if self.download_stats["errors"]:
                err_msg = "\n".join(self.download_stats["errors"][:5])
                raise Exception(f"Помилки завантаження:\n{err_msg}")

            self._write_version(game_dir, remote_version)
            self.set_status("✅ Встановлення завершено!", 100)
            self.set_speed_text("")
            self.show_alert("Готово", "Гру успішно встановлено!", "info")
        except urllib.error.HTTPError as e:
            self.set_status(f"❌ HTTP помилка {e.code}: сервер недоступний", 0)
            self.show_alert("Помилка сервера",
                f"Не вдалося підключитися до сервера ({SERVER_URL}).\n\n"
                f"Переконайтеся, що у вас є інтернет-з'єднання.", "error")
        except Exception as e:
            self.set_status(f"❌ Помилка: {e}", 0)
            self.show_alert("Помилка", str(e), "error")
        finally:
            self.is_installing = False
            self.set_buttons_state("normal")
            self.stop_ui_update.set()

    def _write_version(self, game_dir, version):
        """Write version.txt and update UI."""
        try:
            with open(os.path.join(game_dir, VERSION_FILE), "w") as vf:
                vf.write(version)
            self.root.after(0, lambda: self.local_version.set(version))
        except Exception as e:
            raise Exception(f"Не вдалося зберегти версію: {e}")

    def _ui_update_loop(self):
        """Background thread updating speed and progress every 500ms."""
        while not self.stop_ui_update.is_set():
            if self.download_stats is None:
                time.sleep(0.5)
                continue
            with self.download_stats["lock"]:
                processed = self.download_stats["processed"]
                total = self.download_stats["total"]
                total_bytes = self.download_stats["total_bytes"]
                elapsed = time.time() - self.download_stats["start_time"]
            if elapsed > 0 and total > 0:
                speed_mbps = (total_bytes / (1024 * 1024)) / elapsed
                progress = 10 + int((processed / total) * 85)
                self.set_speed_text(f"⚡ {speed_mbps:.2f} MB/s")
                self.set_status(f"Завантаження... {processed}/{total} файлів", progress)
            time.sleep(0.5)

    def download_file_with_size(self, url, local_path, expected_md5):
        """Download file and return number of bytes downloaded."""
        headers = {"User-Agent": "L2JPlayFun-Launcher"}
        temp_path = local_path + ".tmp"
        dir_name = os.path.dirname(local_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        req = urllib.request.Request(url, headers=headers)
        bytes_downloaded = 0
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(temp_path, "wb") as f:
                while True:
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
        actual_md5 = self.get_md5(temp_path)
        if actual_md5 != expected_md5:
            try:
                os.remove(temp_path)
            except Exception:
                pass
            raise Exception(f"MD5 mismatch for {os.path.basename(local_path)}")
        try:
            os.replace(temp_path, local_path)
        except Exception as e:
            raise Exception(f"Cannot move {temp_path} to {local_path}: {e}")
        return bytes_downloaded

    def get_md5(self, filepath):
        hash_md5 = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_md5.update(chunk)
        except Exception:
            return None
        return hash_md5.hexdigest()

    def verify_game(self):
        self.is_installing = True
        self.set_buttons_state("disabled")
        try:
            game_dir = self.get_full_game_dir()
            self.set_status("Отримання списку файлів...", 5)
            req = urllib.request.Request(
                f"{API_URL}?action=manifest",
                headers={"User-Agent": "L2JPlayFun-Launcher"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            files = data.get("files", [])
            total = len(files)
            remote_version = data.get("version", "1.0.0")

            # Build normalized manifest path set for orphaned detection
            manifest_paths = set()
            for f_info in files:
                rel_path = f_info["path"].replace("/", os.sep).lower()
                manifest_paths.add(rel_path)

            # Find orphaned files (not in manifest and not version file)
            orphaned_files = []
            for root_walk, dirs, files_walk in os.walk(game_dir):
                # Skip hidden/system directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for filename in files_walk:
                    if filename.lower() == VERSION_FILE.lower():
                        continue
                    full_path = os.path.join(root_walk, filename)
                    rel_path = os.path.relpath(full_path, game_dir).lower()
                    if rel_path not in manifest_paths:
                        orphaned_files.append(full_path)

            missing = 0
            corrupted = 0
            for i, f_info in enumerate(files):
                rel_path = f_info["path"]
                expected_md5 = f_info["md5"]
                local_file = os.path.join(game_dir, rel_path.replace("/", os.sep))
                self.set_status(f"[{i+1}/{total}] Перевірка {rel_path}...",
                               int((i / total) * 100))
                if not os.path.exists(local_file):
                    missing += 1
                    # Show downloading status for this specific file
                    self.set_status(f"[{i+1}/{total}] ⬇ Завантаження {rel_path}...",
                                   int((i / total) * 100))
                    self.download_file_with_size(f_info["url"], local_file, expected_md5)
                elif self.get_md5(local_file) != expected_md5:
                    corrupted += 1
                    self.set_status(f"[{i+1}/{total}] ⬇ Завантаження {rel_path}...",
                                   int((i / total) * 100))
                    self.download_file_with_size(f_info["url"], local_file, expected_md5)

            # Delete orphaned files
            deleted_orphaned = 0
            if orphaned_files:
                self.set_status(f"🗑 Видалення зайвих файлів...", 95)
                for op in orphaned_files:
                    try:
                        os.remove(op)
                        deleted_orphaned += 1
                    except Exception:
                        pass
                # Remove empty directories
                for root_walk, dirs, files_walk in os.walk(game_dir, topdown=False):
                    for d in dirs:
                        dir_path = os.path.join(root_walk, d)
                        if not os.listdir(dir_path):
                            try:
                                os.rmdir(dir_path)
                            except Exception:
                                pass

            # Update version after successful verify
            self._write_version(game_dir, remote_version)

            # Build status message — NO popup, just status bar
            if missing == 0 and corrupted == 0 and deleted_orphaned == 0:
                self.set_status("✅ Всі файли цілі! Перевірку завершено.", 100)
            else:
                parts = ["✅ Перевірку завершено!"]
                if missing > 0:
                    parts.append(f"Відсутніх завантажено: {missing}")
                if corrupted > 0:
                    parts.append(f"Пошкоджених відновлено: {corrupted}")
                if deleted_orphaned > 0:
                    parts.append(f"Зайвих видалено: {deleted_orphaned}")
                self.set_status(" | ".join(parts), 100)
        except urllib.error.HTTPError as e:
            self.set_status(f"❌ HTTP помилка {e.code}", 0)
            self.show_alert("Помилка", f"Сервер недоступний ({SERVER_URL})", "error")
        except Exception as e:
            self.set_status(f"❌ Помилка: {e}", 0)
            self.show_alert("Помилка", str(e), "error")
        finally:
            self.is_installing = False
            self.set_buttons_state("normal")

    def launch_game(self):
        game_dir = self.get_full_game_dir()
        if not game_dir:
            raise Exception("Гра не встановлена! Спочатку встановіть її.")
        if not os.path.exists(game_dir):
            raise Exception(f"Директорія гри не знайдена:\n{game_dir}")
        sys_dir = os.path.join(game_dir, "system")
        exe_path = os.path.join(sys_dir, EXE_NAME)
        if not os.path.exists(exe_path):
            raise Exception(f"Файл гри не знайдено:\n{exe_path}\n\nСпочатку встановіть гру.")

        # Try launching the game
        try:
            if os.name == 'nt':
                subprocess.Popen(
                    [exe_path, f"IP={SERVER_IP}"],
                    cwd=sys_dir,
                    shell=False,
                    creationflags=0
                )
            else:
                subprocess.Popen(
                    [exe_path, f"IP={SERVER_IP}"],
                    cwd=sys_dir,
                    shell=False
                )
            self.set_status("🎮 Гра запущена!", 100)
        except Exception as e:
            # Broad check for elevation error (740)
            err_str = str(e).lower()
            is_elevation_error = (
                getattr(e, 'winerror', 0) == 740 or
                getattr(e, 'errno', 0) == 740 or
                '740' in err_str or
                'elevation' in err_str or
                'requires elevation' in err_str
            )
            if is_elevation_error and os.name == 'nt':
                self._try_elevated_launch(exe_path, sys_dir)
            else:
                raise Exception(f"Не вдалося запустити гру: {e}")

    def _try_elevated_launch(self, exe_path, sys_dir):
        """Try to launch with UAC elevation using ShellExecuteW."""
        if os.name == 'nt':
            import ctypes
            try:
                ret = ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", exe_path,
                    f"IP={SERVER_IP}", sys_dir, 1
                )
                if ret <= 32:
                    # Error codes: https://docs.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecutew
                    if ret == 5:
                        raise Exception("Відмовлено в доступі (користувач відхилив UAC)")
                    elif ret == 8:
                        raise Exception("Недостатньо пам'яті")
                    elif ret == 27:
                        raise Exception("Помилка асоціації файлу")
                    elif ret == 31:
                        raise Exception("Не знайдено програму для запуску .exe")
                    elif ret == 1155:
                        raise Exception("Не вказано програму для відкриття цього файлу")
                    else:
                        raise Exception(f"ShellExecute повернув код помилки {ret}")
                # If ret > 32, ShellExecute succeeded — UAC prompt was shown
                self.set_status("🎮 Запит прав адміністратора відправлено. Підтвердіть UAC.", 100)
            except Exception as e2:
                # If ShellExecuteW itself failed, show instructions
                raise Exception(
                    f"Гра потребує прав адміністратора для запуску.\n\n"
                    f"Варіанти вирішення:\n"
                    f"1. Натисніть кнопку Запустити — з'явиться запит UAC → Підтвердіть\n"
                    f"2. Закрийте лаунчер, натисніть ПКМ на ярлику → Запустити від імені адміністратора\n\n"
                    f"Технічна інформація: {e2}"
                )
        else:
            raise Exception("Гра потребує прав адміністратора для запуску.")

    def delete_game(self):
        game_dir = self.get_full_game_dir()
        if not os.path.exists(game_dir):
            self.show_alert("Інформація", "Гра не встановлена.", "info")
            return
        def _do_delete():
            try:
                shutil.rmtree(game_dir)
                self.local_version.set("Немає")
                self.set_status("🗑 Гру видалено", 0)
                self.show_alert("Готово", "Файли гри успішно видалено.", "info")
            except Exception as e:
                self.show_alert("Помилка", str(e), "error")

        self.show_yesno(
            "⚠ Підтвердження видалення",
            f"Ви впевнені, що хочете видалити гру з:\n\n{game_dir}\n\n"
            "Ця дія незворотна!",
            on_yes=_do_delete
        )

    def set_status(self, text, progress_val):
        self.root.after(0, lambda: self.status_text.set(text))
        self.root.after(0, lambda: self.progress.set(progress_val))

    def set_speed_text(self, text):
        self.root.after(0, lambda: self.speed_text.set(text))

    def set_buttons_state(self, state):
        self.root.after(0, lambda: self.btn_install.config(state=state))
        self.root.after(0, lambda: self.btn_verify.config(state=state))
        self.root.after(0, lambda: self.btn_launch.config(state=state))
        self.root.after(0, lambda: self.btn_delete.config(state=state))


def main():
    suppress_windows_error_dialogs()
    root = Tk()
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("Horizontal.TProgressbar",
                    background="#d4af37", troughcolor="#12182e",
                    borderwidth=0, lightcolor="#d4af37", darkcolor="#d4af37")
    app = LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
