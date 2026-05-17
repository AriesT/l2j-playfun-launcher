#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
L2J Play Fun Launcher v7
========================
Windows launcher for Lineage II server.
"""

import os
import sys
import json
import hashlib
import threading
import urllib.request
import urllib.error
from tkinter import (
    Tk, Frame, Label, Button, Entry, StringVar, IntVar,
    filedialog, messagebox, ttk, PhotoImage
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
        self.root.geometry("720x680")
        self.root.configure(bg="#0a0e1a")
        self.root.resizable(False, False)
        try:
            self.root.iconbitmap(resource_path("launcher.ico"))
        except Exception:
            pass
        self.game_path = StringVar()
        self.status_text = StringVar(value="Виберіть директорію та натисніть Встановити")
        self.progress = IntVar(value=0)
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
                                 command=self.launch_game,
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
        Label(footer, text="L2J Play Fun Launcher v7.0 | github.com/AriesT/l2j-playfun-launcher",
              font=("Segoe UI", 8), bg="#0a0e1a", fg="#444").pack()

    def save_server_settings(self):
        ip = self.ip_entry.get().strip()
        port = self.port_entry.get().strip()
        if not ip or not port.isdigit():
            messagebox.showerror("Помилка", "Введіть коректний IP та порт")
            return
        save_config(ip, port)
        messagebox.showinfo("Збережено",
            f"Налаштування сервера оновлено!\n\n"
            f"Адреса: {ip}:{port}\n"
            f"Перезапустіть лаунчер для застосування.")

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
            messagebox.showerror("Помилка", "Спочатку виберіть директорію!")
            return
        threading.Thread(target=self._safe_thread, args=(self.install_game,), daemon=True).start()

    def _safe_thread(self, target_func):
        """Wrapper to catch all exceptions and prevent Windows error dialogs."""
        try:
            target_func()
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Помилка", str(e)))
            self.root.after(0, lambda: self.set_status(f"❌ Помилка: {e}", 0))
            self.root.after(0, lambda: self.set_buttons_state("normal"))
            self.is_installing = False

    def install_game(self):
        self.is_installing = True
        self.set_buttons_state("disabled")
        try:
            game_dir = self.get_full_game_dir()
            os.makedirs(game_dir, exist_ok=True)
            self.set_status("Отримання списку файлів...", 5)
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
            self.set_status(f"Завантаження {total} файлів...", 10)
            for i, f_info in enumerate(files):
                rel_path = f_info["path"]
                file_url = f_info["url"]  # Already URL-encoded from server
                expected_md5 = f_info["md5"]
                rel_path_fixed = rel_path.replace("/", os.sep)
                local_file = os.path.join(game_dir, rel_path_fixed)
                os.makedirs(os.path.dirname(local_file), exist_ok=True)
                if os.path.exists(local_file):
                    local_md5 = self.get_md5(local_file)
                    if local_md5 and local_md5 == expected_md5:
                        self.set_status(f"[{i+1}/{total}] {rel_path} — актуальний", 
                                       10 + int((i / total) * 85))
                        continue
                self.set_status(f"[{i+1}/{total}] {rel_path}",
                               10 + int((i / total) * 85))
                self.download_file(file_url, local_file, expected_md5)
            with open(os.path.join(game_dir, VERSION_FILE), "w") as vf:
                vf.write(remote_version)
            self.local_version.set(remote_version)
            self.set_status("✅ Встановлення завершено!", 100)
            messagebox.showinfo("Готово", "Гру успішно встановлено!")
        except urllib.error.HTTPError as e:
            self.set_status(f"❌ HTTP помилка {e.code}: сервер недоступний", 0)
            messagebox.showerror("Помилка сервера", 
                f"Не вдалося підключитися до сервера ({SERVER_URL}).\n\n"
                f"Переконайтеся, що у вас є інтернет-з'єднання.")
        except Exception as e:
            self.set_status(f"❌ Помилка: {e}", 0)
            messagebox.showerror("Помилка", str(e))
        finally:
            self.is_installing = False
            self.set_buttons_state("normal")

    def download_file(self, url, local_path, expected_md5):
        """Download file using already URL-encoded URL from manifest."""
        headers = {"User-Agent": "L2JPlayFun-Launcher"}
        temp_path = local_path + ".tmp"
        
        # Ensure directory exists before download
        dir_name = os.path.dirname(local_path)
        if dir_name and not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name, exist_ok=True)
            except Exception as e:
                raise Exception(f"Cannot create directory '{dir_name}': {e}")
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                with open(temp_path, "wb") as f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f.write(chunk)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            raise
        # Verify MD5
        actual_md5 = self.get_md5(temp_path)
        if actual_md5 != expected_md5:
            try:
                os.remove(temp_path)
            except:
                pass
            raise Exception(f"MD5 mismatch for {os.path.basename(local_path)}")
        try:
            os.replace(temp_path, local_path)
        except Exception as e:
            raise Exception(f"Cannot move {temp_path} to {local_path}: {e}")

    def get_md5(self, filepath):
        hash_md5 = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hash_md5.update(chunk)
        except Exception:
            return None
        return hash_md5.hexdigest()

    def start_verify(self):
        if self.is_installing:
            return
        if not self.game_path.get() or not os.path.exists(self.game_path.get()):
            messagebox.showerror("Помилка", "Гра не встановлена!")
            return
        threading.Thread(target=self._safe_thread, args=(self.verify_game,), daemon=True).start()

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
                    self.download_file(f_info["url"], local_file, expected_md5)
                elif self.get_md5(local_file) != expected_md5:
                    corrupted += 1
                    self.download_file(f_info["url"], local_file, expected_md5)
            msg = f"Перевірку завершено!"
            if missing == 0 and corrupted == 0:
                msg += "\nВсі файли цілі ✅"
            else:
                msg += f"\nВідсутніх: {missing}\nПошкоджених: {corrupted}\nВідновлено ✅"
            self.set_status(msg.replace("\n", " | "), 100)
            messagebox.showinfo("Готово", msg)
        except urllib.error.HTTPError as e:
            self.set_status(f"❌ HTTP помилка {e.code}", 0)
            messagebox.showerror("Помилка", f"Сервер недоступний ({SERVER_URL})")
        except Exception as e:
            self.set_status(f"❌ Помилка: {e}", 0)
            messagebox.showerror("Помилка", str(e))
        finally:
            self.is_installing = False
            self.set_buttons_state("normal")

    def launch_game(self):
        game_dir = self.get_full_game_dir()
        exe_path = os.path.join(game_dir, "system", EXE_NAME)
        if not os.path.exists(exe_path):
            messagebox.showerror("Помилка", "Гра не знайдена! Спочатку встановіть її.")
            return
        try:
            sys_dir = os.path.join(game_dir, "system")
            subprocess.Popen(
                [EXE_NAME, "IP=188.40.83.149"],
                cwd=sys_dir,
                shell=False,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            self.set_status("🎮 Гра запущена!", 100)
        except Exception as e:
            messagebox.showerror("Помилка запуску", str(e))

    def delete_game(self):
        game_dir = self.get_full_game_dir()
        if not os.path.exists(game_dir):
            messagebox.showinfo("Інформація", "Гра не встановлена.")
            return
        result = messagebox.askyesno(
            "⚠ Підтвердження видалення",
            f"Ви впевнені, що хочете видалити гру з:\n\n{game_dir}\n\n"
            "Ця дія незворотна!",
            icon="warning"
        )
        if result:
            try:
                shutil.rmtree(game_dir)
                self.local_version.set("Немає")
                self.set_status("🗑 Гру видалено", 0)
                messagebox.showinfo("Готово", "Файли гри успішно видалено.")
            except Exception as e:
                messagebox.showerror("Помилка", str(e))

    def set_status(self, text, progress_val):
        self.root.after(0, lambda: self.status_text.set(text))
        self.root.after(0, lambda: self.progress.set(progress_val))

    def set_buttons_state(self, state):
        self.root.after(0, lambda: self.btn_install.config(state=state))
        self.root.after(0, lambda: self.btn_verify.config(state=state))
        self.root.after(0, lambda: self.btn_launch.config(state=state))
        self.root.after(0, lambda: self.btn_delete.config(state=state))


def main():
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
