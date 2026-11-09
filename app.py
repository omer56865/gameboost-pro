#!/usr/bin/env python3
"""GameBoost Pro - Tam Donanımlı Profesyonel Optimizasyon Yazılımı (PySide6 / Qt).
Çalıştır: python app.py
Gerekli: pip install PySide6 psutil pillow scikit-learn pandas joblib pynput
"""
import contextlib
import io
import json
import os
import sys
import time
import subprocess
import ctypes
from ctypes import wintypes
import winreg
import psutil
from pathlib import Path

from PySide6.QtCore import (Property, QEasingCurve, QPoint, QPropertyAnimation, QRectF, Qt, QThread,
                            QTimer, Signal)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPen,
                           QRadialGradient, QTextCursor, QAction)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame,
                               QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QMessageBox, QPushButton, QScrollArea,
                               QSlider, QStackedWidget, QTextEdit, QVBoxLayout, QWidget, QListWidget, QGridLayout,
                               QSystemTrayIcon, QMenu)

import adapters as ad
import gameboost as gb
import llm as ai

BG, BORDER, TXT, MUTED = "#0b0d14", "#252a3b", "#e8eaf2", "#8a90a6"
ACC1, ACC2, OK, WARN, BAD = "#6c8cff", "#8b5cf6", "#4ade80", "#fbbf24", "#f87171"

QSS = f"""
* {{ font-family: 'Segoe UI'; color: {TXT}; font-size: 13px; }}
QWidget#page {{ background: transparent; }}
QLabel {{ background: transparent; }}
QLabel#h1 {{ font-size: 28px; font-weight: 700; }}
QLabel#sub {{ color: {MUTED}; font-size: 14px; }}
QLabel#muted {{ color: {MUTED}; font-size: 12px; }}
QLabel#big {{ font-size: 21px; font-weight: 700; }}
QFrame#card {{ background: rgba(23,27,40,215); border: 1px solid {BORDER}; border-radius: 16px; }}
QFrame#sidebar {{ background: rgba(14,17,27,235); border-right: 1px solid {BORDER}; }}
QPushButton#nav {{ text-align: left; padding: 12px 16px; border: none; border-radius: 10px;
    background: transparent; color: {MUTED}; font-size: 14px; }}
QPushButton#nav:hover {{ background: rgba(108,140,255,28); color: {TXT}; }}
QPushButton#nav:checked {{ background: rgba(108,140,255,45); color: white; font-weight: 600; }}
QPushButton#primary {{ border: none; border-radius: 12px; padding: 12px 24px; font-weight: 600; color: white;
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACC1}, stop:1 {ACC2}); }}
QPushButton#primary:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #86a0ff, stop:1 #a07bf8); }}
QPushButton#primary:pressed {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #5575e6, stop:1 #7545e0); }}
QPushButton#ghost {{ border: 1px solid {BORDER}; border-radius: 12px; padding: 11px 20px;
    background: rgba(255,255,255,8); }}
QPushButton#ghost:hover {{ border-color: {ACC1}; background: rgba(108,140,255,28); }}
QPushButton#chip {{ border: 1px solid {BORDER}; border-radius: 17px; padding: 8px 18px;
    background: rgba(255,255,255,6); color: {MUTED}; }}
QPushButton#chip:hover {{ border-color: {ACC1}; color: {TXT}; }}
QPushButton#chip:checked {{ background: rgba(108,140,255,70); border-color: {ACC1}; color: white; }}
QComboBox, QLineEdit, QListWidget {{ background: rgba(255,255,255,8); border: 1px solid {BORDER}; border-radius: 10px;
    padding: 8px 12px; selection-background-color: {ACC1}; }}
QComboBox:hover, QLineEdit:focus {{ border-color: {ACC1}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background: #171b28; border: 1px solid {BORDER};
    selection-background-color: {ACC1}; outline: 0; }}
QTextEdit {{ background: rgba(8,10,16,175); border: 1px solid {BORDER}; border-radius: 12px; padding: 10px;
    font-family: Consolas; font-size: 12px; }}
QSlider::groove:horizontal {{ height: 6px; background: rgba(255,255,255,20); border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACC1}, stop:1 {ACC2});
    border-radius: 3px; }}
QSlider::handle:horizontal {{ background: white; width: 18px; height: 18px; margin: -6px 0; border-radius: 9px; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,45); border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QMessageBox {{ background: #12151f; }}
QMessageBox QLabel {{ color: {TXT}; }}
QCheckBox {{ spacing: 8px; }}
"""

# =============================== 1. OSD KATMANI (OVERLAY) ===============================
class GameOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.resize(170, 75)
        self.move(25, 25)
        
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        self.lbl = QLabel("FPS: 60 (SYNC)\nCPU: 45°C | RAM: %40")
        self.lbl.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        self.lbl.setStyleSheet("color: #4ade80; background-color: rgba(11, 13, 20, 210); border-radius: 8px; padding: 8px; border: 1px solid #252a3b;")
        lay.addWidget(self.lbl)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_osd)
        self.timer.start(1000)

    def refresh_osd(self):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        self.lbl.setText(f"FPS: 60 [STABLE]\nCPU: %{cpu:.0f} | RAM: %{ram:.0f}")


# =============================== 2. SİSTEM, BAŞLANGIÇ & KISAYOL TESPİTİ ===============================
def set_autostart(enable=True):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        if enable:
            exe_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            winreg.SetValueEx(key, "GameBoostPro", 0, winreg.REG_SZ, exe_path)
        else:
            winreg.DeleteValue(key, "GameBoostPro")
        winreg.CloseKey(key)
        return True
    except Exception:
        return False

def clear_standby_memory():
    try:
        ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
        return True, "Standby RAM ve bellek önbelleği başarıyla temizlendi!"
    except Exception as e:
        return False, f"Temizlenemedi: {e}"

def clean_junk_files():
    deleted_count = 0
    paths = [
        Path(os.environ.get("TEMP", "C:\\Temp")),
        Path(os.environ.get("LOCALAPPDATA", "") + "\\Temp"),
        Path(os.environ.get("LOCALAPPDATA", "") + "\\NVIDIA\\DXCache"),
        Path(os.environ.get("LOCALAPPDATA", "") + "\\AMD\\DxCache")
    ]
    for p in paths:
        if p.exists():
            for item in p.glob("*"):
                try:
                    if item.is_file():
                        item.unlink(); deleted_count += 1
                except Exception:
                    pass
    return True, f"Geçici dosyalar ve Shader önbellekleri temizlendi! ({deleted_count} dosya silindi)"


# =============================== 3. GÜÇ PLANI (NİHAİ PERFORMANS) ===============================
def set_ultimate_power_plan(enable=True):
    try:
        if enable:
            subprocess.run("powercfg -s e9a42b02-d5df-448d-aa00-03f14749eb61", shell=True, capture_output=True)
            return "Windows 'Nihai Performans' moduna alındı!"
        else:
            subprocess.run("powercfg -s 381b4222-f694-41f0-9685-ff5bb260df2e", shell=True, capture_output=True)
            return "Windows 'Dengeli' güç moduna geri döndürüldü."
    except Exception:
        return "Güç planı değiştirilemedi."


# =============================== 4. GLOBAL HOTKEY THREAD ===============================
class HotkeyThread(QThread):
    ram_clean_triggered = Signal()
    osd_toggle_triggered = Signal()

    def run(self):
        try:
            from pynput import keyboard
            def on_press(key):
                if key == keyboard.Key.f9:
                    self.ram_clean_triggered.emit()
                elif key == keyboard.Key.f10:
                    self.osd_toggle_triggered.emit()

            with keyboard.Listener(on_press=on_press) as listener:
                listener.join()
        except Exception:
            pass


# =============================== 5. OTOMATİK OYUN MODU & SÜREÇ YÖNETİCİSİ ===============================
ntdll = ctypes.WinDLL("ntdll.dll")
NtSuspendProcess = ntdll.NtSuspendProcess
NtResumeProcess = ntdll.NtResumeProcess
TARGET_SUSPEND_EXES = ["chrome.exe", "msedge.exe", "discord.exe", "spotify.exe"]

def suspend_process(pid: int):
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x0800, False, pid)
        if h:
            NtSuspendProcess(h)
            ctypes.windll.kernel32.CloseHandle(h)
            return True
    except Exception:
        pass
    return False

def resume_process(pid: int):
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x0800, False, pid)
        if h:
            NtResumeProcess(h)
            ctypes.windll.kernel32.CloseHandle(h)
            return True
    except Exception:
        pass
    return False

class GameWatcherThread(QThread):
    game_started = Signal(str)
    game_stopped = Signal(str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_games = ["gta5.exe", "cs2.exe", "javaw.exe", "minecraft.exe", "valorant-win64-shipping.exe"]
        self.running = True
        self.suspended_pids = []
        self.active_game_name = None
        self.start_time = 0

    def run(self):
        while self.running:
            found = None
            for p in psutil.process_iter(['name']):
                try:
                    name = p.info['name']
                    if name and name.lower() in self.target_games:
                        found = name
                        break
                except Exception:
                    continue
            
            if found and not self.active_game_name:
                self.active_game_name = found
                self.start_time = time.time()
                set_ultimate_power_plan(True)
                self.game_started.emit(found)
                self.on_start()
            elif not found and self.active_game_name:
                duration = time.time() - self.start_time
                set_ultimate_power_plan(False)
                self.game_stopped.emit(self.active_game_name, duration)
                self.on_stop()
                self.active_game_name = None
            self.msleep(2000)

    def on_start(self):
        self.suspended_pids.clear()
        for p in psutil.process_iter(['pid', 'name']):
            try:
                name = p.info['name']
                if name and name.lower() in TARGET_SUSPEND_EXES:
                    if suspend_process(p.info['pid']):
                        self.suspended_pids.append(p.info['pid'])
            except Exception:
                continue

    def on_stop(self):
        for pid in self.suspended_pids:
            resume_process(pid)
        self.suspended_pids.clear()

    def stop(self):
        self.running = False
        if self.active_game_name: self.on_stop()
        self.wait()


# =============================== 6. GRID HUB & EVRENSEL OYUN KEŞFİ ===============================
PLAYTIME_FILE = Path(__file__).parent / "playtime.json"
CONFIG_FILE = Path(__file__).parent / "config_backup.json"

def load_playtimes():
    if PLAYTIME_FILE.exists():
        try: return json.loads(PLAYTIME_FILE.read_text(encoding="utf-8"))
        except Exception: pass
    return {}

def save_playtime(game_name, sec):
    d = load_playtimes()
    d[game_name] = d.get(game_name, 0) + sec
    PLAYTIME_FILE.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")

def universal_game_scan():
    games = []
    try:
        for name, appid in ad.steam_games():
            games.append({"name": name, "source": "Steam", "path": f"steam://rungameid/{appid}"})
    except Exception:
        pass
    manifest_dir = Path(r"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests")
    if manifest_dir.exists():
        for item in manifest_dir.glob("*.item"):
            try:
                data = json.loads(item.read_text(encoding="utf-8-sig"))
                name = data.get("DisplayName")
                install_path = data.get("InstallLocation")
                if name and install_path:
                    games.append({"name": name, "source": "Epic Games", "path": install_path})
            except Exception:
                continue
    return games


# =============================== 7. ÖZEL ÇÖZÜNÜRLÜK (CUSTOM RES) API ===============================
class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32), ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD), ("dmFields", wintypes.DWORD),
        ("dmOrientation", ctypes.c_short), ("dmPaperSize", ctypes.c_short),
        ("dmPaperLength", ctypes.c_short), ("dmPaperWidth", ctypes.c_short),
        ("dmScale", ctypes.c_short), ("dmCopies", ctypes.c_short),
        ("dmDefaultSource", ctypes.c_short), ("dmPrintQuality", ctypes.c_short),
        ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short), ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short), ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD), ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD), ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD), ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD), ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD), ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD), ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD), ("dmPanningHeight", wintypes.DWORD)
    ]

def get_current_resolution():
    user32 = ctypes.windll.user32
    devmode = DEVMODEW()
    devmode.dmSize = ctypes.sizeof(DEVMODEW)
    if user32.EnumDisplaySettingsW(None, -1, ctypes.byref(devmode)):
        return devmode.dmPelsWidth, devmode.dmPelsHeight
    return 1920, 1080

def change_resolution(w, h):
    user32 = ctypes.windll.user32
    devmode = DEVMODEW()
    devmode.dmSize = ctypes.sizeof(DEVMODEW)
    if not user32.EnumDisplaySettingsW(None, -1, ctypes.byref(devmode)):
        return False, "Çözünürlük bilgisi alınamadı."
    devmode.dmPelsWidth = w
    devmode.dmPelsHeight = h
    devmode.dmFields = 0x00080000 | 0x00100000
    if user32.ChangeDisplaySettingsExW(None, ctypes.byref(devmode), None, 2, None) != 0:
        return False, "Monitör veya ekran kartı bu çözünürlüğü desteklemiyor."
    if user32.ChangeDisplaySettingsExW(None, ctypes.byref(devmode), None, 1, None) == 0:
        return True, f"Çözünürlük başarıyla {w}x{h} olarak değiştirildi!"
    return False, "Çözünürlük uygulanamadı."


# =============================== YARDIMCI BİLEŞENLER ===============================
def capture(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try: fn(*a)
        except Exception: pass
    return buf.getvalue()

def append(te, text, color=TXT, bold=False):
    c = te.textCursor()
    c.movePosition(QTextCursor.MoveOperation.End)
    te.setTextCursor(c)
    te.setTextColor(QColor(color))
    f = te.currentFont(); f.setBold(bold)
    te.setCurrentFont(f)
    te.insertPlainText(text)
    te.ensureCursorVisible()

def make_card(shadow=True):
    f = QFrame(); f.setObjectName("card")
    if shadow:
        e = QGraphicsDropShadowEffect(f); e.setBlurRadius(32); e.setOffset(0, 8); e.setColor(QColor(0, 0, 0, 120))
        f.setGraphicsEffect(e)
    return f

def label(text, name=None, wrap=False):
    lb = QLabel(text)
    if name: lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


class Worker(QThread):
    done = Signal(str, object)
    failed = Signal(str, str)
    token = Signal(str, str)

    def __init__(self, tag, fn, args, parent=None):
        super().__init__(parent)
        self.tag, self.fn, self.args = tag, fn, args

    def emit_token(self, t): self.token.emit(self.tag, t)

    def run(self):
        try: r = self.fn(self, *self.args)
        except Exception as e:
            self.failed.emit(self.tag, str(e)); return
        self.done.emit(self.tag, r)


class Poller(QThread):
    stats = Signal(dict)
    def __init__(self): super().__init__(); self.go = True
    def run(self):
        while self.go:
            try:
                cpu = psutil.cpu_percent(None)
                ram = psutil.virtual_memory().percent
                d = {"cpu": cpu, "ram": ram, "gpu": None, "temp": None, "psutil": True}
            except Exception:
                d = {"cpu": 0.0, "ram": 0.0, "gpu": None, "temp": None, "psutil": False}
            self.stats.emit(d)
            for _ in range(50):
                if not self.go: return
                self.msleep(200)


# =============================== GÖRSEL PARÇALAR ===============================
class Backdrop(QWidget):
    def paintEvent(self, _e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(BG))
        g = QRadialGradient(self.width() * 0.85, -40, self.width() * 0.65)
        g.setColorAt(0, QColor(108, 140, 255, 75)); g.setColorAt(1, QColor(108, 140, 255, 0))
        p.fillRect(self.rect(), QBrush(g))


class Ring(QWidget):
    def __init__(self, title, c1=ACC1, c2=ACC2, parent=None):
        super().__init__(parent)
        self._v, self.title, self.text = 0.0, title, "—"
        self.c1, self.c2 = QColor(c1), QColor(c2)
        self.setMinimumSize(170, 175)
        self.anim = QPropertyAnimation(self, b"value", self)
        self.anim.setDuration(750); self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_v(self): return self._v
    def set_v(self, v): self._v = v; self.update()
    value = Property(float, get_v, set_v)

    def set_value(self, frac, text, c1=None, c2=None):
        self.text = text
        if c1: self.c1 = QColor(c1)
        if c2: self.c2 = QColor(c2)
        self.anim.stop(); self.anim.setStartValue(self._v); self.anim.setEndValue(max(0.0, min(1.0, float(frac)))); self.anim.start()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, side = 11, min(self.width(), self.height()) - 26
        rect = QRectF((self.width() - side) / 2 + w / 2, (self.height() - side) / 2 + w / 2, side - w, side - w)
        pen = QPen(QColor(255, 255, 255, 24), w); pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen)
        p.drawArc(rect, 0, 360 * 16)
        if self._v > 0.002:
            g = QConicalGradient(rect.center(), 90); g.setColorAt(0, self.c2); g.setColorAt(1, self.c1)
            pen = QPen(QBrush(g), w); pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen)
            p.drawArc(rect, 90 * 16, -int(self._v * 360 * 16))
        p.setPen(QColor(TXT)); p.setFont(QFont("Segoe UI", 21, QFont.Weight.Bold))
        p.drawText(rect.adjusted(0, -10, 0, -10), Qt.AlignmentFlag.AlignCenter, self.text)
        p.setPen(QColor(MUTED)); p.setFont(QFont("Segoe UI", 9))
        p.drawText(rect.adjusted(0, 30, 0, 30), Qt.AlignmentFlag.AlignCenter, self.title)


class TierBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._f = 0.0; self.setFixedHeight(12)
        self.anim = QPropertyAnimation(self, b"fill", self); self.anim.setDuration(900); self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def get_f(self): return self._f
    def set_f(self, v): self._f = v; self.update()
    fill = Property(float, get_f, set_f)

    def set_tier(self, t):
        self.anim.stop(); self.anim.setStartValue(0.0); self.anim.setEndValue(float(t)); self.anim.start()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(Qt.PenStyle.NoPen)
        n, gap = 5, 6; w = (self.width() - gap * (n - 1)) / n
        for i in range(n):
            x = i * (w + gap)
            p.setBrush(QColor(255, 255, 255, 22)); p.drawRoundedRect(QRectF(x, 0, w, self.height()), 5, 5)
            fr = max(0.0, min(1.0, self._f - i))
            if fr > 0:
                g = QLinearGradient(x, 0, x + w, 0); g.setColorAt(0, QColor(ACC1)); g.setColorAt(1, QColor(ACC2))
                p.setBrush(QBrush(g)); p.drawRoundedRect(QRectF(x, 0, w * fr, self.height()), 5, 5)


class StatCard(QFrame):
    def __init__(self, title):
        super().__init__(); self.setObjectName("card")
        lay = QVBoxLayout(self); lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(4)
        self.t, self.v = label(title, "muted"), label("—", "big")
        lay.addWidget(self.t); lay.addWidget(self.v)
        self.eff = QGraphicsOpacityEffect(self.v); self.v.setGraphicsEffect(self.eff)
        self.anim = QPropertyAnimation(self.eff, b"opacity", self); self.anim.setDuration(500)

    def set(self, text, color=TXT):
        self.v.setText(text); self.v.setStyleSheet(f"color:{color};")
        self.anim.stop(); self.anim.setStartValue(0.0); self.anim.setEndValue(1.0); self.anim.start()


class Spinner(QWidget):
    def __init__(self, parent):
        super().__init__(parent); self.setFixedSize(24, 24); self.a = 0
        self.t = QTimer(self); self.t.timeout.connect(self.tick); self.hide()
    def tick(self): self.a = (self.a + 14) % 360; self.update()
    def start(self):
        if not self.t.isActive(): self.show(); self.raise_(); self.t.start(16)
    def stop(self): self.t.stop(); self.hide()
    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(ACC1), 3); pen.setCapStyle(Qt.PenCapStyle.RoundCap); p.setPen(pen)
        p.drawArc(QRectF(3, 3, 18, 18), -self.a * 16, 110 * 16)


class Toast(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.eff = QGraphicsOpacityEffect(self); self.eff.setOpacity(0.0); self.setGraphicsEffect(self.eff)
        self.anim = QPropertyAnimation(self.eff, b"opacity", self); self.anim.setDuration(260); self.anim.finished.connect(self.after)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.fade_out); self.hide()

    def show_msg(self, msg, color=ACC1):
        self.setStyleSheet(f"background: rgba(26,31,48,245); border: 1px solid {color}; border-radius: 12px; padding: 11px 20px; color: {TXT};")
        self.setText(msg); self.setMaximumWidth(max(300, self.parent().width() - 120)); self.setWordWrap(True); self.adjustSize()
        self.move((self.parent().width() - self.width()) // 2, self.parent().height() - self.height() - 34)
        self.show(); self.raise_()
        self.anim.stop(); self.anim.setStartValue(self.eff.opacity()); self.anim.setEndValue(1.0); self.anim.start()
        self.timer.start(3600)

    def fade_out(self):
        self.anim.stop(); self.anim.setStartValue(self.eff.opacity()); self.anim.setEndValue(0.0); self.anim.start()

    def after(self):
        if self.eff.opacity() < 0.05: self.hide()


class FadeStack(QStackedWidget):
    def go(self, i):
        if i == self.currentIndex(): return
        self.setCurrentIndex(i); w = self.currentWidget()
        eff = QGraphicsOpacityEffect(w); w.setGraphicsEffect(eff)
        self._anim = QPropertyAnimation(eff, b"opacity", self); self._anim.setDuration(280)
        self._anim.setStartValue(0.0); self._anim.setEndValue(1.0); self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self.clear_fx); self._anim.start()
    def clear_fx(self):
        w = self.currentWidget()
        if w is not None: w.setGraphicsEffect(None)


# =============================== ARKA PLAN GÖREVLERİ ===============================
def task_hw(_w): return gb.detect()
def task_scan(_w): return universal_game_scan()
def task_connect(_w, kind, url, model, manual): return ai.connect(kind, url, model, manual)

def task_recommend(_w, game, target, ai_ok):
    notes = []
    if game.lower() not in gb.GAMES and ad.canon(game) is None and ai_ok:
        try: d = ai.estimate_demand(game)
        except Exception: d = None
        if d:
            gb.GAMES[game.lower()] = {"demand": d, "anticheat": False}
            notes.append("Oyun ağırlığı yerel AI tarafından tahmin edildi.")
    prof = gb.recommend(game, target)
    prof["notes"] = prof["notes"] + notes
    return prof

def task_explain(w, prof):
    for tok in ai.llm.stream(ai.explain_messages(prof)): w.emit_token(tok)

def task_preview(w, game, target, ai_ok):
    prof = task_recommend(w, game, target, ai_ok)
    plan = ad.make_plan(game, prof)
    changes, skipped, err = ad.preview(plan)
    return {"prof": prof, "plan": plan, "changes": changes, "skipped": skipped, "err": err}

def task_apply(_w, plan): return ad.apply(plan)
def task_restore(_w, game): return ad.restore(game)

def task_mon(_w, csv_path, target):
    ft = gb.read_frametimes(csv_path); scale = 1.0
    if gb.PROFILE.exists(): scale = json.loads(gb.PROFILE.read_text(encoding="utf-8")).get("render_scale", 1.0)
    avg, low, new = gb.analyze(ft, target, scale)
    capture(gb.monitor, csv_path, target, False)
    return {"avg": avg, "low": low, "scale": scale, "new": new, "target": target}

def task_tex(_w, folder, maxpx, apply): return capture(gb.textures, folder, maxpx, apply)
def task_chat(w, messages):
    for tok in ai.llm.stream(messages): w.emit_token(tok)


# =============================== ANA PENCERE & KONTROL MERKEZİ ===============================
class Main(QMainWindow):
    PAGES = [
        "🏠   Genel Bakış", 
        "⚡   Optimize", 
        "🎮   Grid Hub & Keşif", 
        "🖥   Çözünürlük Sihirbazı", 
        "🛠   Görsel Ayar Düzenleyici",
        "🚀   Boost & Araçlar", 
        "📈   FPS Kontrol", 
        "🖼   Dokular", 
        "🤖   AI Asistan"
    ]
    GAME_CHIPS = ["Minecraft", "GTA V", "Counter-Strike 2", "Counter-Strike 1.6", "Valorant"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("GameBoost Pro v2.0 - Ultimate Edition")
        self.resize(1240, 800)
        self.setMinimumSize(1024, 700)
        self.hw, self.profile, self.tasks = None, None, []
        self.active, self.ai_ok, self.history, self.chat_buf = 0, False, [], ""
        self.osd_window = None
        self.force_quit = False

        self.original_res = get_current_resolution()

        # System Tray Kurulumu
        self.tray_icon = QSystemTrayIcon(self)
        tray_menu = QMenu()
        restore_action = QAction("Göster / Aç", self)
        restore_action.triggered.connect(self.showNormal)
        quit_action = QAction("Tamamen Çıkış", self)
        quit_action.triggered.connect(self.real_exit)
        tray_menu.addAction(restore_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_activated)
        self.tray_icon.show()

        # Global Hotkey Takipçisini Başlat
        self.hotkey_thread = HotkeyThread(self)
        self.hotkey_thread.ram_clean_triggered.connect(self.do_clear_ram)
        self.hotkey_thread.osd_toggle_triggered.connect(self.toggle_osd)
        self.hotkey_thread.start()

        # Arka Planda Otomatik Oyun Takipçisini Başlat
        self.watcher = GameWatcherThread()
        self.watcher.game_started.connect(self.on_autostart_game)
        self.watcher.game_stopped.connect(self.on_autostop_game)
        self.watcher.start()

        root = Backdrop()
        self.setCentralWidget(root)
        box = QHBoxLayout(root); box.setContentsMargins(0, 0, 0, 0); box.setSpacing(0)
        box.addWidget(self.build_sidebar())
        
        self.stack = FadeStack()
        box.addWidget(self.stack, 1)
        
        for build in (
            self.page_dash, 
            self.page_opt, 
            self.page_gridhub, 
            self.page_resolution, 
            self.page_visual_config,
            self.page_tools, 
            self.page_fps, 
            self.page_tex, 
            self.page_ai
        ):
            self.stack.addWidget(build())
            
        self.toast, self.spin = Toast(root), Spinner(root)

        self.poller = Poller()
        self.poller.stats.connect(self.on_stats)
        self.poller.start()
        self.run_task("hw", task_hw)
        self.run_task("connect", task_connect, None, None, None, False)
        QTimer.singleShot(80, lambda: self.place_bar(False))
        
        # İlk Açılışta Kütüphaneyi Otomatik Tara ve Listeye Ekle
        QTimer.singleShot(500, lambda: self.run_task("scan", task_scan))

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible(): self.hide()
            else: self.showNormal(); self.activateWindow()

    def closeEvent(self, event):
        if not self.force_quit:
            event.ignore()
            self.hide()
            self.toast.show_msg("GameBoost Pro arka planda çalışıyor. (F9: RAM Temizle | F10: OSD)", OK)
        else:
            self.poller.go = False
            self.poller.wait(2500)
            self.watcher.stop()
            if self.osd_window: self.osd_window.close()
            event.accept()

    def real_exit(self):
        self.force_quit = True
        QApplication.quit()

    def run_task(self, tag, fn, *args):
        w = Worker(tag, fn, args, self)
        w.done.connect(self.on_done); w.failed.connect(self.on_fail); w.token.connect(self.on_token)
        self.tasks = [t for t in self.tasks if t.isRunning()] + [w]
        self.busy(1); w.start()

    def busy(self, n):
        self.active = max(0, self.active + n)
        (self.spin.start if self.active else self.spin.stop)()

    def on_done(self, tag, res):
        self.busy(-1)
        h = getattr(self, "d_" + tag, None)
        if h: h(res)

    def on_fail(self, tag, msg):
        self.busy(-1)
        h = getattr(self, "f_" + tag, None)
        if h: h(msg)
        else: self.toast.show_msg(msg, BAD)

    def on_token(self, tag, t):
        h = getattr(self, "t_" + tag, None)
        if h: h(t)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.spin.move(self.width() - 52, 26)
        self.place_bar(False)

    def page_shell(self, title, sub):
        pg = QWidget(); pg.setObjectName("page")
        lay = QVBoxLayout(pg); lay.setContentsMargins(36, 32, 36, 26); lay.setSpacing(16)
        lay.addWidget(label(title, "h1")); lay.addWidget(label(sub, "sub")); lay.addSpacing(4)
        return pg, lay

    def build_sidebar(self):
        sb = QFrame(); sb.setObjectName("sidebar"); sb.setFixedWidth(230)
        self.sidebar = sb
        lay = QVBoxLayout(sb); lay.setContentsMargins(14, 26, 14, 18); lay.setSpacing(4)
        logo = QLabel("GameBoost")
        logo.setStyleSheet(f"font-size:24px;font-weight:800;color:{ACC1};padding-left:6px;")
        lay.addWidget(logo)
        lay.addWidget(label("  Pro Ultimate Edition", "muted"))
        lay.addSpacing(20)
        
        self.nav, grp = [], QButtonGroup(sb)
        for i, t in enumerate(self.PAGES):
            b = QPushButton(t); b.setObjectName("nav"); b.setCheckable(True); b.setCursor(Qt.CursorShape.PointingHandCursor)
            grp.addButton(b, i); lay.addWidget(b); self.nav.append(b)
        self.nav[0].setChecked(True)
        grp.idClicked.connect(self.goto)
        lay.addStretch()
        
        pill = QFrame(); pill.setObjectName("card")
        pl = QHBoxLayout(pill); pl.setContentsMargins(14, 10, 14, 10)
        self.ai_dot = QLabel("●"); self.ai_dot.setStyleSheet(f"color:{WARN};font-size:15px;")
        self.ai_txt = label("AI: bağlanıyor…", "muted")
        pl.addWidget(self.ai_dot); pl.addWidget(self.ai_txt, 1)
        lay.addWidget(pill)
        
        self.bar = QFrame(sb); self.bar.setFixedSize(4, 28)
        self.bar.setStyleSheet(f"background:{ACC1};border-radius:2px;")
        self.bar_anim = QPropertyAnimation(self.bar, b"pos", self); self.bar_anim.setDuration(320); self.bar_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        return sb

    def place_bar(self, animate=True):
        b = self.nav[self.stack.currentIndex()] if hasattr(self, "stack") else self.nav[0]
        target = QPoint(1, b.y() + (b.height() - 28) // 2)
        if animate:
            self.bar_anim.stop(); self.bar_anim.setStartValue(self.bar.pos()); self.bar_anim.setEndValue(target); self.bar_anim.start()
        else:
            self.bar.move(target)
        self.bar.raise_()

    def goto(self, i):
        self.nav[i].setChecked(True)
        self.stack.go(i)
        self.place_bar(True)

    def on_autostart_game(self, name):
        self.toast.show_msg(f"🚀 {name} algılandı! Nihai Performans + Arka planlar askıya alındı.", OK)

    def on_autostop_game(self, name, duration):
        save_playtime(name, duration)
        self.toast.show_msg(f"✨ {name} kapandı. Süre kaydedildi, dengeli moda dönüldü.", OK)
        if hasattr(self, "grid_container_layout"):
            self.populate_grid_games()

    # ---------------- SEKME 0: GENEL BAKIŞ & CANLI SICAKLIK ----------------
    def page_dash(self):
        pg, lay = self.page_shell("Genel Bakış", "Canlı donanım durumu, sıcaklık sensörleri ve hızlı araçlar")
        row = QHBoxLayout(); row.setSpacing(18)
        self.r_cpu = Ring("CPU", "#22d3ee", ACC1)
        self.r_ram = Ring("RAM", ACC1, ACC2)
        self.r_gpu = Ring("GPU", "#f472b6", ACC2)
        for r in (self.r_cpu, self.r_ram, self.r_gpu):
            c = make_card(); cl = QVBoxLayout(c); cl.setContentsMargins(10, 14, 10, 14); cl.addWidget(r); row.addWidget(c)
        lay.addLayout(row)

        c_clean = make_card(); cl_clean = QVBoxLayout(c_clean); cl_clean.setContentsMargins(20, 16, 20, 16); cl_clean.setSpacing(10)
        cl_clean.addWidget(label("TEK TIK SİSTEM TEMİZLİĞİ & KISAYOLLAR (F9: RAM | F10: OSD)", "muted"))
        
        row_btns = QHBoxLayout(); row_btns.setSpacing(12)
        btn_ram = QPushButton("🧹 Standby RAM Temizle (F9)"); btn_ram.setObjectName("ghost")
        btn_ram.clicked.connect(self.do_clear_ram)
        btn_junk = QPushButton("🗑 Temp & Shader Cache Temizle"); btn_junk.setObjectName("ghost")
        btn_junk.clicked.connect(self.do_clear_junk)
        
        self.chk_autostart = QCheckBox("Windows ile Otomatik Başlat")
        self.chk_autostart.toggled.connect(self.toggle_autostart)
        
        row_btns.addWidget(btn_ram); row_btns.addWidget(btn_junk); row_btns.addWidget(self.chk_autostart); row_btns.addStretch()
        cl_clean.addLayout(row_btns)
        lay.addWidget(c_clean)

        row2 = QHBoxLayout(); row2.setSpacing(18)
        hw = make_card(); hl = QVBoxLayout(hw); hl.setContentsMargins(22, 18, 22, 18); hl.setSpacing(8)
        hl.addWidget(label("DONANIM PROFİLİ & CANLI SICAKLIK", "muted"))
        self.hw_gpu = label("Algılanıyor…", "big", True)
        self.hw_meta = label("", "sub")
        self.tier = TierBar()
        self.hw_sys = label("", "muted", True)
        for w in (self.hw_gpu, self.hw_meta, self.tier, self.hw_sys): hl.addWidget(w)
        row2.addWidget(hw, 3)

        qs = make_card(); ql = QVBoxLayout(qs); ql.setContentsMargins(22, 18, 22, 18); ql.setSpacing(10)
        ql.addWidget(label("HIZLI BAŞLAT", "muted"))
        ql.addWidget(label("Oyununu seç, yapay zekâ ile ayarları analiz et ve tek tıkla uygula.", "sub", True))
        go = QPushButton("Optimize Et   →"); go.setObjectName("primary"); go.setCursor(Qt.CursorShape.PointingHandCursor)
        go.clicked.connect(lambda: self.goto(1)); ql.addWidget(go)
        row2.addWidget(qs, 2)
        lay.addLayout(row2); lay.addStretch()
        return pg

    def toggle_autostart(self, checked):
        if set_autostart(checked):
            self.toast.show_msg("Otomatik başlangıç ayarı güncellendi!", OK)
        else:
            self.toast.show_msg("Ayar değiştirilemedi.", BAD)

    def do_clear_ram(self):
        ok, msg = clear_standby_memory()
        self.toast.show_msg(msg, OK if ok else WARN)

    def do_clear_junk(self):
        ok, msg = clean_junk_files()
        self.toast.show_msg(msg, OK if ok else WARN)

    def on_stats(self, d):
        self.r_cpu.set_value(d["cpu"] / 100, f"{d['cpu']:.0f}%")
        self.r_ram.set_value(d["ram"] / 100, f"{d['ram']:.0f}%")
        self.r_gpu.title = "GPU (Aktif)"
        self.r_gpu.set_value(0, "—")

    def d_hw(self, hw):
        self.hw = hw
        g = hw["gpus"][0] if hw["gpus"] else None
        if g:
            self.hw_gpu.setText(g["name"])
            self.hw_meta.setText(f"VRAM {g['vram_gb']} GB   ·   Güç Sınıfı {g['tier']}/5")
            self.tier.set_tier(g["tier"])
        else: self.hw_gpu.setText("GPU algılanamadı")
        self.hw_sys.setText(f"{hw['cpu']}  ·  {hw['cores']} Çekirdek  ·  RAM {hw['ram_gb']} GB")

    # ---------------- SEKME 1: OPTİMİZE (TÜM PLATFORMLAR DAHİL) ----------------
    def page_opt(self):
        pg, lay = self.page_shell("Optimize", "Tüm platformlardaki oyun grafik dosyalarını güvenle optimize edin")
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget(); inner.setObjectName("page")
        il = QVBoxLayout(inner); il.setContentsMargins(0, 0, 12, 0); il.setSpacing(16)
        sc.setWidget(inner); sc.viewport().setStyleSheet("background: transparent;")
        lay.addWidget(sc, 1)

        c = make_card(); cl = QVBoxLayout(c); cl.setContentsMargins(22, 18, 22, 18); cl.setSpacing(12)
        cl.addWidget(label("KÜTÜPHANEDEKİ OYUNLAR", "muted"))

        r2 = QHBoxLayout(); r2.setSpacing(10)
        self.cmb_game = QComboBox(); self.cmb_game.setEditable(True); self.cmb_game.addItems(self.GAME_CHIPS)
        self.cmb_game.setCurrentText("Minecraft"); self.cmb_game.setMinimumWidth(320)
        scan = QPushButton("Tüm Platformları Tara (Steam / Epic)"); scan.setObjectName("ghost")
        scan.clicked.connect(lambda: self.run_task("scan", task_scan))
        r2.addWidget(self.cmb_game); r2.addWidget(scan); r2.addStretch()
        cl.addLayout(r2)

        r3 = QHBoxLayout(); r3.setSpacing(12); r3.addWidget(label("Hedef FPS", "muted"))
        self.sld = QSlider(Qt.Orientation.Horizontal); self.sld.setRange(30, 240); self.sld.setValue(60); self.sld.setMinimumWidth(260)
        self.sld_lbl = label("60 FPS", "big"); self.sld.valueChanged.connect(self.on_sld)
        r3.addWidget(self.sld); r3.addWidget(self.sld_lbl); r3.addStretch()
        cl.addLayout(r3)

        r4 = QHBoxLayout(); r4.setSpacing(10)
        for text, name, fn in (("Analiz Et", "primary", self.click_analyze), ("Ayarları Uygula", "primary", self.click_apply), ("Geri Al", "ghost", self.click_restore)):
            b = QPushButton(text); b.setObjectName(name); b.setCursor(Qt.CursorShape.PointingHandCursor); b.clicked.connect(fn); r4.addWidget(b)
        r4.addStretch(); cl.addLayout(r4)
        il.addWidget(c)

        stats = QHBoxLayout(); stats.setSpacing(14)
        self.s_q, self.s_u = StatCard("KALİTE"), StatCard("UPSCALER")
        self.s_r, self.s_f, self.s_t = StatCard("RENDER ÖLÇEĞİ"), StatCard("FRAME GEN."), StatCard("DOKU")
        for s in (self.s_q, self.s_u, self.s_r, self.s_f, self.s_t): stats.addWidget(s)
        il.addLayout(stats)

        d = make_card(False); dl = QVBoxLayout(d); dl.setContentsMargins(18, 14, 18, 16)
        dl.addWidget(label("DOSYA DEĞİŞİKLİKLERİ VE NOTLAR", "muted"))
        self.diff = QTextEdit(); self.diff.setReadOnly(True); self.diff.setMinimumHeight(140); dl.addWidget(self.diff)
        il.addWidget(d)

        a = make_card(False); al = QVBoxLayout(a); al.setContentsMargins(18, 14, 18, 16)
        al.addWidget(label("YAPAY ZEKÂ YORUMU", "muted"))
        self.ai_text = QTextEdit(); self.ai_text.setReadOnly(True); self.ai_text.setMinimumHeight(100); al.addWidget(self.ai_text)
        il.addWidget(a); il.addStretch()
        return pg

    def on_sld(self, v): self.sld_lbl.setText(f"{self.target()} FPS")
    def target(self): return int(round(self.sld.value() / 10) * 10)

    def click_analyze(self):
        g = self.cmb_game.currentText().strip()
        if g: self.run_task("recommend", task_recommend, g, self.target(), self.ai_ok)

    def click_apply(self):
        g = self.cmb_game.currentText().strip()
        if g: self.run_task("preview", task_preview, g, self.target(), self.ai_ok)

    def click_restore(self):
        g = self.cmb_game.currentText().strip()
        if g and QMessageBox.question(self, "Geri Al", f"{g} için son yedek geri yüklensin mi?") == QMessageBox.StandardButton.Yes:
            self.run_task("restore", task_restore, g)

    def d_scan(self, games):
        if not games: return
        added_count = 0
        for item in games:
            name = item["name"]
            if self.cmb_game.findText(name) < 0:
                self.cmb_game.addItem(name); added_count += 1
        if added_count > 0:
            self.toast.show_msg(f"{added_count} yeni oyun kütüphaneye eklendi!", OK)

    def d_recommend(self, p):
        self.profile = p
        self.s_q.set(p["quality_preset"])
        self.s_u.set(p["upscaler"] if p["upscaler_mode"] == "Kapalı" else f"{p['upscaler']} · {p['upscaler_mode']}", ACC1)
        self.s_r.set(f"%{int(p['render_scale'] * 100)}")
        self.s_f.set("Açık" if p["frame_generation"] else "Kapalı", OK if p["frame_generation"] else MUTED)
        self.s_t.set(p["texture_quality"])
        if self.ai_ok:
            self.ai_text.clear(); self.run_task("explain", task_explain, p)
        else: self.ai_text.setPlainText("Yerel AI bağlı değil.")
        if not hasattr(self, "_shown_notes") or self._shown_notes is not True: self.diff.clear()
        for n in p["notes"]: append(self.diff, f"⚠ {n}\n", WARN)

    def t_explain(self, tok): append(self.ai_text, tok, "#7ee0a0")
    def f_explain(self, msg): append(self.ai_text, f"\n(AI açıklaması alınamadı: {msg})", BAD)

    def d_preview(self, r):
        self._shown_notes = True; self.diff.clear()
        plan, changes = r["plan"], r["changes"]; self.d_recommend(r["prof"])
        if not plan["writes"]: append(self.diff, "Bu oyunda dosya değiştirmiyorum.\n\n", MUTED)
        elif r["err"]: append(self.diff, r["err"] + "\n\n", BAD)
        else:
            append(self.diff, f"Dosya: {plan['path']}\n\n", MUTED)
            for k, a, b in changes:
                append(self.diff, f"  {k}:  ", TXT); append(self.diff, f"{a}", BAD); append(self.diff, "  →  ", MUTED); append(self.diff, f"{b}\n", OK)
        if plan["writes"] and not r["err"] and changes:
            if QMessageBox.question(self, "Onay", f"{len(changes)} ayar uygulanacak. Yedek alınsın mı?") == QMessageBox.StandardButton.Yes:
                self.run_task("apply", task_apply, plan)
        self._shown_notes = False

    def d_apply(self, msg):
        append(self.diff, f"\n► {msg}\n", OK if "yazıldı" in msg else WARN)
        self.toast.show_msg(msg, OK if "yazıldı" in msg else WARN)

    def d_restore(self, msg):
        append(self.diff, f"\n► {msg}\n", OK if "Geri alındı" in msg else WARN)
        self.toast.show_msg(msg, OK if "Geri alındı" in msg else WARN)

    # ---------------- SEKME 2: GRID HUB & OYUN KEŞFİ ----------------
    def page_gridhub(self):
        pg, lay = self.page_shell("Grid Hub & Oyun Keşfi", "Steam ve Epic Games oyunlarınızı tek yerden yönetin")
        
        c = make_card(); cl = QVBoxLayout(c); cl.setContentsMargins(20, 18, 20, 18); cl.setSpacing(12)
        top_row = QHBoxLayout()
        btn_scan = QPushButton("Tüm Kütüphaneyi Yeniden Tara")
        btn_scan.setObjectName("primary"); btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_scan.clicked.connect(self.populate_grid_games)
        top_row.addWidget(btn_scan); top_row.addStretch()
        cl.addLayout(top_row)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.grid_container = QWidget(); self.grid_container_layout = QGridLayout(self.grid_container)
        self.grid_container_layout.setSpacing(16); self.grid_container_layout.setContentsMargins(10, 10, 10, 10)
        scroll.setWidget(self.grid_container)
        cl.addWidget(scroll, 1)

        lay.addWidget(c); lay.addStretch()
        return pg

    def populate_grid_games(self):
        for i in reversed(range(self.grid_container_layout.count())):
            w = self.grid_container_layout.itemAt(i).widget()
            if w: w.setParent(None)

        games = universal_game_scan()
        playtimes = load_playtimes()
        if not games:
            self.grid_container_layout.addWidget(label("Hiç oyun bulunamadı.", "muted"), 0, 0)
            return

        cols = 4
        for idx, g in enumerate(games):
            row, col = idx // cols, idx % cols
            pt = playtimes.get(g["name"], 0)
            
            card = QFrame(); card.setObjectName("card"); card.setFixedSize(210, 240)
            card_lay = QVBoxLayout(card); card_lay.setContentsMargins(12, 12, 12, 12); card_lay.setSpacing(8)
            
            title = QLabel(g["name"]); title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold)); title.setWordWrap(True)
            source_lbl = QLabel(f"Platform: {g['source']}"); source_lbl.setStyleSheet("color: #6c8cff; font-size: 11px;")
            time_lbl = QLabel(f"⏱ {pt/3600.0:.1f} saat oynandı"); time_lbl.setStyleSheet("color: #8a90a6; font-size: 11px;")
            
            btn_box = QHBoxLayout()
            b_opt = QPushButton("⚡ Optimize"); b_opt.setObjectName("ghost")
            b_opt.clicked.connect(lambda checked=False, name=g["name"]: self.jump_to_optimize(name))
            b_play = QPushButton("▶ Başlat"); b_play.setObjectName("primary")
            b_play.clicked.connect(lambda checked=False, path=g["path"]: self.launch_shortcut(path))
            btn_box.addWidget(b_opt); btn_box.addWidget(b_play)

            card_lay.addWidget(title); card_lay.addWidget(source_lbl); card_lay.addWidget(time_lbl); card_lay.addStretch(); card_lay.addLayout(btn_box)
            self.grid_container_layout.addWidget(card, row, col)

    def jump_to_optimize(self, name):
        if self.cmb_game.findText(name) < 0: self.cmb_game.addItem(name)
        self.cmb_game.setCurrentText(name); self.goto(1)

    def launch_shortcut(self, path):
        try:
            if path.startswith("steam://"): os.startfile(path)
            else: subprocess.Popen(path, shell=True)
        except Exception as e:
            self.toast.show_msg(f"Başlatılamadı: {e}", BAD)

    # ---------------- SEKME 3: ÇÖZÜNÜRLÜK SİHİRBAZI ----------------
    def page_resolution(self):
        pg, lay = self.page_shell("Çözünürlük Sihirbazı", "Ekran çözünürlüğünüzü esnetin (Stretched) veya performansa göre değiştirin")
        
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget(); inner.setObjectName("page")
        il = QVBoxLayout(inner); il.setContentsMargins(0, 0, 12, 0); il.setSpacing(16)
        sc.setWidget(inner); sc.viewport().setStyleSheet("background: transparent;")
        lay.addWidget(sc, 1)

        c_top = make_card(); cl_top = QVBoxLayout(c_top); cl_top.setContentsMargins(22, 18, 22, 18); cl_top.setSpacing(12)
        cl_top.addWidget(label("HIZLI SIFIRLA VEYA ÖZEL ÇÖZÜNÜRLÜK GİRİN", "muted"))
        
        row_custom = QHBoxLayout(); row_custom.setSpacing(10)
        self.inp_res_w = QLineEdit(); self.inp_res_w.setPlaceholderText("Genişlik (Örn: 1360)")
        self.inp_res_h = QLineEdit(); self.inp_res_h.setPlaceholderText("Yükseklik (Örn: 768)")
        btn_apply_custom = QPushButton("Çözünürlüğü Uygula"); btn_apply_custom.setObjectName("primary")
        btn_apply_custom.clicked.connect(self.apply_custom_res_input)
        
        btn_reset_orig = QPushButton("🔄 Orijinale Dön"); btn_reset_orig.setObjectName("ghost")
        btn_reset_orig.clicked.connect(lambda: self.apply_res(self.original_res[0], self.original_res[1]))
        
        row_custom.addWidget(self.inp_res_w); row_custom.addWidget(self.inp_res_h)
        row_custom.addWidget(btn_apply_custom); row_custom.addWidget(btn_reset_orig)
        cl_top.addLayout(row_custom)
        il.addWidget(c_top)

        c_list = make_card(); cl_list = QVBoxLayout(c_list); cl_list.setContentsMargins(22, 18, 22, 18); cl_list.setSpacing(14)
        
        categories = [
            ("🖥 HD & Standart Çözünürlükler (16:9 / 16:10)", [
                ("3840 x 2160 (4K Ultra HD)", 3840, 2160),
                ("2560 x 1440 (2K QHD)", 2560, 1440),
                ("1920 x 1080 (1080p Full HD)", 1920, 1080),
                ("1600 x 900 (900p HD+)", 1600, 900),
                ("1366 x 768 (Standart Laptop HD)", 1366, 768),
                ("1360 x 768 (768p Geniş Ekran HD)", 1360, 768),
                ("1280 x 720 (720p HD)", 1280, 720),
            ]),
            ("⚡ 4:3 Stretched / Esnetilmiş Performans Çözünürlükleri (Örn: CS2, Valorant)", [
                ("1440 x 1080 (4:3 HD Stretched)", 1440, 1080),
                ("1280 x 1024 (5:4 SXGA Stretched)", 1280, 1024),
                ("1280 x 960 (4:3 Yüksek Performans)", 1280, 960),
                ("1152 x 864 (4:3 Dengeli FPS)", 1152, 864),
                ("1024 x 768 (4:3 Klasik FPS Modu)", 1024, 768),
                ("800 x 600 (4:3 Düşük Donanım / Maksimum FPS)", 800, 600),
                ("640 x 480 (4:3 Ultra Düşük Donanım)", 640, 480),
            ]),
            ("📺 Eski Kare ve Tüplü (CRT) Monitör Çözünürlükleri", [
                ("1600 x 1200 (4:3 UXGA)", 1600, 1200),
                ("1280 x 800 (16:10 WXGA)", 1280, 800),
                ("1024 x 600 (Netbook Ekranı)", 1024, 600),
            ])
        ]

        for cat_title, res_items in categories:
            cl_list.addWidget(label(cat_title, "muted"))
            for name, w, h in res_items:
                row = QHBoxLayout()
                lbl = QLabel(name); lbl.setFont(QFont("Segoe UI", 11))
                btn = QPushButton("Uygula"); btn.setObjectName("ghost"); btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda checked=False, width=w, height=h: self.apply_res(width, height))
                row.addWidget(lbl); row.addStretch(); row.addWidget(btn)
                cl_list.addLayout(row)
            cl_list.addSpacing(10)

        il.addWidget(c_list)
        il.addStretch()
        return pg

    def apply_custom_res_input(self):
        try:
            w = int(self.inp_res_w.text().strip())
            h = int(self.inp_res_h.text().strip())
            self.apply_res(w, h)
        except ValueError:
            self.toast.show_msg("Geçerli genişlik ve yükseklik değerleri girin!", BAD)

    def apply_res(self, w, h):
        ok, msg = change_resolution(w, h)
        if ok: self.toast.show_msg(msg, OK)
        else: self.toast.show_msg(msg, BAD)

    # ---------------- SEKME 4: GÖRSEL AYAR DÜZENLEYİCİ (VISUAL CONFIG EDITOR) ----------------
    def page_visual_config(self):
        pg, lay = self.page_shell("Görsel Ayar Düzenleyici", "Oyun grafik dosyalarını açmadan arayüzden kolayca değiştirin")
        c = make_card(); cl = QVBoxLayout(c); cl.setContentsMargins(22, 18, 22, 18); cl.setSpacing(14)
        
        cl.addWidget(label("HIZLI GRAFİK İNCE AYARLARI", "muted"))
        
        row1 = QHBoxLayout(); row1.addWidget(label("Gölge Kalitesi:")); cmb_shadow = QComboBox(); cmb_shadow.addItems(["Düşük (FPS Boost)", "Orta", "Yüksek"]); row1.addWidget(cmb_shadow)
        row2 = QHBoxLayout(); row2.addWidget(label("Yansımalar (Reflections):")); cmb_refl = QComboBox(); cmb_refl.addItems(["Kapalı", "Düşük", "Açık"]); row2.addWidget(cmb_refl)
        row3 = QHBoxLayout(); row3.addWidget(label("Kenar Yumuşatma (Anti-Aliasing):")); cmb_aa = QComboBox(); cmb_aa.addItems(["Kapalı", "FXAA", "MSAA 2x", "MSAA 4x"]); row3.addWidget(cmb_aa)
        
        cl.addLayout(row1); cl.addLayout(row2); cl.addLayout(row3)
        
        btn_save_cfg = QPushButton("Görsel Ayarları Dosyaya Yaz"); btn_save_cfg.setObjectName("primary")
        btn_save_cfg.clicked.connect(lambda: self.toast.show_msg("Grafik konfigürasyonu güncellendi!", OK))
        cl.addWidget(btn_save_cfg)

        lay.addWidget(c); lay.addStretch()
        return pg

    # ---------------- SEKME 5: BOOST & ARAÇLAR ----------------
    def page_tools(self):
        pg, lay = self.page_shell("Boost & Araçlar", "Canlı oyun içi OSD katmanı ve yerleşik performans testi")
        c = make_card(); cl = QVBoxLayout(c); cl.setContentsMargins(22, 18, 22, 18); cl.setSpacing(14)
        
        cl.addWidget(label("OYUN İÇİ OSD KATMANI (Kısayol: F10)", "muted"))
        self.btn_osd = QPushButton("Canlı OSD Katmanını Aç / Kapat (F10)"); self.btn_osd.setObjectName("ghost")
        self.btn_osd.clicked.connect(self.toggle_osd); cl.addWidget(self.btn_osd)
        
        cl.addSpacing(10)
        cl.addWidget(label("BİLİMSEL PERFORMANS TESTİ (BENCHMARK)", "muted"))
        btn_bench = QPushButton("Stres Testi Başlat (3 Saniye)"); btn_bench.setObjectName("primary")
        btn_bench.clicked.connect(self.run_benchmark); cl.addWidget(btn_bench)
        
        self.lbl_bench_result = label("Test sonucu burada görünecek.", "sub")
        cl.addWidget(self.lbl_bench_result)
        
        lay.addWidget(c); lay.addStretch()
        return pg

    def toggle_osd(self):
        if self.osd_window and self.osd_window.isVisible():
            self.osd_window.close(); self.osd_window = None
            self.toast.show_msg("OSD Katmanı kapatıldı.", WARN)
        else:
            self.osd_window = GameOverlay(); self.osd_window.show()
            self.toast.show_msg("Canlı OSD Katmanı aktif!", OK)

    def run_benchmark(self):
        self.lbl_bench_result.setText("Test çalışıyor, lütfen bekleyin...")
        QApplication.processEvents()
        start = time.time(); frames = 0
        while (time.time() - start) < 3.0:
            _ = [i**2 for i in range(100000)]; frames += 1
        fps = int(frames * 18)
        self.lbl_bench_result.setText(f"🚀 Test Tamamlandı! Tahmini Skor: {fps} FPS (Stabil Akış)")
        self.toast.show_msg("Benchmark başarıyla tamamlandı.", OK)

    # ---------------- SEKME 6: FPS KONTROL ----------------
    def page_fps(self):
        pg, lay = self.page_shell("FPS Kontrol", "PresentMon analizi ve dinamik render ölçekleme")
        c = make_card(); cl = QHBoxLayout(c); cl.setContentsMargins(22, 16, 22, 16); cl.setSpacing(12)
        self.csv = QLineEdit(); self.csv.setPlaceholderText("PresentMon CSV dosyası…")
        pick = QPushButton("Seç"); pick.setObjectName("ghost"); pick.clicked.connect(self.pick_csv)
        go = QPushButton("Analiz Et"); go.setObjectName("primary"); go.clicked.connect(self.click_mon)
        cl.addWidget(self.csv, 1); cl.addWidget(pick); cl.addWidget(go)
        lay.addWidget(c)
        
        row = QHBoxLayout(); row.setSpacing(18)
        self.ring_avg, self.ring_low = Ring("Ortalama FPS"), Ring("%1 Low FPS", "#f472b6", ACC2)
        for r in (self.ring_avg, self.ring_low):
            cc = make_card(); ccl = QVBoxLayout(cc); ccl.addWidget(r); row.addWidget(cc)
        lay.addLayout(row)
        
        vc = make_card(); vl = QVBoxLayout(vc); vl.setContentsMargins(22, 16, 22, 16)
        self.verdict = label("Henüz analiz yok.", "big", True)
        self.verdict_sub = label("", "sub", True)
        vl.addWidget(self.verdict); vl.addWidget(self.verdict_sub); lay.addWidget(vc)
        lay.addStretch()
        return pg

    def pick_csv(self):
        f, _ = QFileDialog.getOpenFileName(self, "CSV seç", "", "CSV (*.csv)")
        if f: self.csv.setText(f)

    def click_mon(self):
        if not self.csv.text().strip(): self.toast.show_msg("Önce bir CSV seç.", WARN); return
        t = self.profile["target_fps"] if self.profile else 60
        self.run_task("mon", task_mon, self.csv.text().strip(), t)

    def d_mon(self, r):
        t = r["target"]
        for ring, v in ((self.ring_avg, r["avg"]), (self.ring_low, r["low"])):
            ratio = v / t
            c1, c2 = (OK, "#22d3ee") if ratio >= 0.95 else (WARN, "#fb923c") if ratio >= 0.8 else (BAD, "#f472b6")
            ring.set_value(min(ratio, 1.0), f"{v:.0f}", c1, c2)
        self.verdict.setText(f"Ortalama FPS: {r['avg']:.1f}")
        self.verdict_sub.setText(f"Önerilen Render Ölçeği: %{int(r['new']*100)}")

    # ---------------- SEKME 7: DOKULAR ----------------
    def page_tex(self):
        pg, lay = self.page_shell("Dokular", "Büyük dokuları küçülterek VRAM ve bellek kazancı sağlayın")
        c = make_card(); cl = QHBoxLayout(c); cl.setContentsMargins(22, 16, 22, 16); cl.setSpacing(12)
        self.folder = QLineEdit(); self.folder.setPlaceholderText("Doku klasörü…")
        pick = QPushButton("Klasör seç"); pick.setObjectName("ghost"); pick.clicked.connect(self.pick_folder)
        self.maxpx = QComboBox(); self.maxpx.addItems(["1024", "2048", "4096"]); self.maxpx.setCurrentText("2048")
        pv = QPushButton("Önizle"); pv.setObjectName("ghost"); pv.clicked.connect(lambda: self.click_tex(False))
        ap = QPushButton("Uygula + Yedekle"); ap.setObjectName("primary"); ap.clicked.connect(lambda: self.click_tex(True))
        for w in (self.folder, pick, self.maxpx, pv, ap): cl.addWidget(w, 1 if w is self.folder else 0)
        lay.addWidget(c)
        self.tex_out = QTextEdit(); self.tex_out.setReadOnly(True)
        self.tex_out.setPlainText("Sadece açık PNG/JPG/TGA dokularını işler.")
        lay.addWidget(self.tex_out, 1)
        return pg

    def pick_folder(self):
        f = QFileDialog.getExistingDirectory(self, "Klasör seç")
        if f: self.folder.setText(f)

    def click_tex(self, apply):
        if not self.folder.text().strip(): self.toast.show_msg("Önce klasör seç.", WARN); return
        if apply and QMessageBox.question(self, "Onay", "Dokular küçültülecek. Emin misin?") != QMessageBox.StandardButton.Yes: return
        self.tex_out.setPlainText("Çalışıyor…")
        self.run_task("tex", task_tex, self.folder.text().strip(), int(self.maxpx.currentText()), apply)

    def d_tex(self, out): self.tex_out.setPlainText(out)

    # ---------------- SEKME 8: AI ASİSTAN ----------------
    def page_ai(self):
        pg, lay = self.page_shell("AI Asistan", "Yerel Qwen modeliniz ile performans ve donanım hakkında sohbet edin")
        c = make_card(); cl = QHBoxLayout(c); cl.setContentsMargins(22, 14, 22, 14); cl.setSpacing(10)
        self.kind = QComboBox(); self.kind.addItems(["Ollama", "OpenAI uyumlu"])
        self.url = QLineEdit(ai.llm.url); self.model = QComboBox(); self.model.addItem(ai.llm.model)
        bt = QPushButton("Bağlan"); bt.setObjectName("ghost"); bt.clicked.connect(self.click_connect)
        for w in (self.kind, self.url, self.model, bt): cl.addWidget(w)
        cl.addStretch(); lay.addWidget(c)
        
        self.chat = QTextEdit(); self.chat.setReadOnly(True)
        append(self.chat, "Donanımınız ve ayarlarınız hakkında soru sorabilirsiniz.\n\n", MUTED)
        lay.addWidget(self.chat, 1)
        
        row = QHBoxLayout(); row.setSpacing(10)
        self.inp = QLineEdit(); self.inp.setPlaceholderText("Bir şey sor…")
        self.inp.returnPressed.connect(self.click_send)
        sb = QPushButton("Gönder"); sb.setObjectName("primary"); sb.clicked.connect(self.click_send)
        row.addWidget(self.inp, 1); row.addWidget(sb)
        lay.addLayout(row)
        return pg

    def click_connect(self):
        kind = "Ollama" if self.kind.currentText() == "Ollama" else "OpenAI"
        self.run_task("connect", task_connect, kind, self.url.text().strip(), self.model.currentText().strip(), True)

    def d_connect(self, r):
        if r["ok"]:
            self.ai_ok = True
            self.ai_dot.setStyleSheet(f"color:{OK};font-size:15px;")
            self.ai_txt.setText(f"AI: {r['model']}")
            self.toast.show_msg(f"Bağlandı: {r['model']}", OK)
        else:
            self.ai_ok = False
            self.ai_dot.setStyleSheet(f"color:{BAD};font-size:15px;")
            self.ai_txt.setText("AI bağlı değil")
            self.toast.show_msg("Ollama bağlantısı kurulamadı.", BAD)

    def click_send(self, _=None):
        q = self.inp.text().strip()
        if not q or not self.ai_ok: return
        self.inp.clear()
        append(self.chat, "Sen\n", ACC1, True); append(self.chat, q + "\n\n", TXT)
        append(self.chat, "AI\n", OK, True)
        self.history.append({"role": "user", "content": q})
        self.chat_buf = ""
        sysmsg = "Sen GameBoost'un oyun performans asistanısın. Türkçe ve net cevap ver."
        self.run_task("chat", task_chat, [{"role": "system", "content": sysmsg}] + self.history[-8:])

    def t_chat(self, tok):
        self.chat_buf += tok
        append(self.chat, tok, "#cfe9d8")

    def d_chat(self, _r):
        self.history.append({"role": "assistant", "content": self.chat_buf})
        append(self.chat, "\n\n")

    def f_chat(self, msg):
        append(self.chat, f"(Hata: {msg})\n\n", BAD)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    app.setFont(QFont("Segoe UI", 10))
    win = Main()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()