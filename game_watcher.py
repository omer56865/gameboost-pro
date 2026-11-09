"""
GameBoost Pro - Otomatik Oyun Modu ve Süreç Yöneticisi.

Güvenlik notu: NtSuspendProcess yerine psutil.suspend/resume kullanıyoruz.
Bu hem admin gerektirmez hem de anti-cheat açısından daha güvenlidir.
"""
import time
from PySide6.QtCore import QThread, Signal
import psutil
from optimizer import (set_power_plan, suspend_bg_apps, resume_bg_apps,
                       optimize_services, set_game_priority)

DEFAULT_TARGETS = [
    "gta5.exe", "cs2.exe", "javaw.exe",
    "minecraft.exe", "valorant-win64-shipping.exe",
]

BG_SUSPEND = [
    "chrome.exe", "msedge.exe", "firefox.exe",
    "opera.exe", "discord.exe", "spotify.exe",
]


class GameWatcherThread(QThread):
    game_started = Signal(str)
    game_stopped = Signal(str, float)   # ad, saniye
    log = Signal(str)

    def __init__(self, target_games=None, parent=None):
        super().__init__(parent)
        self.targets = [g.lower() for g in (target_games or DEFAULT_TARGETS)]
        self.running = True
        self._suspended = []
        self._active = None
        self._t0 = 0.0

    def run(self):
        while self.running:
            found = None
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    n = (proc.info["name"] or "").lower()
                    if n in self.targets:
                        found = proc.info["name"]
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if found and not self._active:
                self._active, self._t0 = found, time.time()
                self.game_started.emit(found)
                self._on_start(found)

            elif not found and self._active:
                dur = time.time() - self._t0
                name = self._active
                self._active = None
                self._on_stop()
                self.game_stopped.emit(name, dur)

            self.msleep(2000)

    def _on_start(self, exe):
        set_power_plan(True)
        self._suspended = suspend_bg_apps(BG_SUSPEND)
        stopped = optimize_services(True)
        set_game_priority(exe)
        self.log.emit(
            f"{exe} algılandı. Güç planı: Yüksek Performans. "
            f"{len(self._suspended)} uygulama donduruldu. "
            f"Durdurulan servisler: {stopped or 'yok (yönetici gerekli)'}")

    def _on_stop(self):
        resume_bg_apps(self._suspended)
        self._suspended.clear()
        optimize_services(False)
        set_power_plan(False)
        self.log.emit("Oyun kapandı. Ayarlar eski haline döndürüldü.")

    def stop(self):
        self.running = False
        if self._active:
            self._on_stop()
        self.wait(3000)
