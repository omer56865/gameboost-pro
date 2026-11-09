"""
GameBoost Pro - FPS Overlay Python Sarmalayıcı.

DLL varsa DirectX present hook'u kullanır (gerçek oyun FPS'i).
DLL yoksa psutil ile yaklaşık sistem yükünü gösterir (her oyunda çalışır).

DLL derlemek için (MSVC gerekir):
  cl /O2 /LD fps_overlay.cpp /link d3d11.lib dxgi.lib user32.lib /out:fps_overlay.dll
"""
import ctypes
import os
import threading
import time
from pathlib import Path

DLL_PATH = Path(__file__).parent / "fps_overlay.dll"


class _DllOverlay:
    """DirectX present hook - gerçek FPS, sadece DLL derlendiğinde kullanılır."""

    def __init__(self):
        self._dll = ctypes.WinDLL(str(DLL_PATH))
        self._dll.GB_Init.restype = ctypes.c_int
        self._dll.GB_GetStats.argtypes = [
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float),
        ]
        rc = self._dll.GB_Init()
        if rc != 0 and rc != 1:
            raise RuntimeError(f"GB_Init failed: {rc}")

    def stats(self) -> dict:
        fps = ctypes.c_float()
        low1 = ctypes.c_float()
        ms = ctypes.c_float()
        self._dll.GB_GetStats(
            ctypes.byref(fps), ctypes.byref(low1), ctypes.byref(ms)
        )
        return {
            "fps": round(fps.value, 1),
            "low1": round(low1.value, 1),
            "frame_ms": round(ms.value, 2),
            "source": "directx_hook",
        }

    def shutdown(self):
        try:
            self._dll.GB_Shutdown()
        except Exception:
            pass


class _SoftwareOverlay:
    """
    DLL olmadığında devreye girer.
    GPU saymacını nvidia-smi üzerinden, CPU'yu psutil üzerinden okur.
    Oyun içi gerçek FPS'i ölçemez ama sistem yükünü gösterir.
    """

    def __init__(self):
        self._nv = self._check_nv()
        self._frame_times: list[float] = []
        self._last_t = time.perf_counter()
        self._lock = threading.Lock()

    @staticmethod
    def _check_nv() -> bool:
        import subprocess
        try:
            subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                           capture_output=True, timeout=3)
            return True
        except Exception:
            return False

    def tick(self):
        """Her kare render edildiğinde çağır (opsiyonel, software tahmin için)."""
        now = time.perf_counter()
        with self._lock:
            dt = (now - self._last_t) * 1000.0
            self._last_t = now
            self._frame_times.append(dt)
            if len(self._frame_times) > 256:
                self._frame_times.pop(0)

    def stats(self) -> dict:
        import subprocess

        result: dict = {"fps": 0.0, "low1": 0.0, "frame_ms": 0.0,
                        "cpu": 0.0, "gpu": None, "source": "software"}

        # CPU
        try:
            import psutil
            result["cpu"] = psutil.cpu_percent(None)
        except ImportError:
            pass

        # GPU (nvidia-smi)
        if self._nv:
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=2
                ).stdout.strip()
                parts = out.split(",")
                result["gpu"] = {
                    "util": float(parts[0].strip()),
                    "temp": float(parts[1].strip()),
                }
            except Exception:
                pass

        # Kare süresi tahmini (tick() çağrıldıysa)
        with self._lock:
            ft = list(self._frame_times)
        if ft:
            avg_ms = sum(ft) / len(ft)
            result["fps"] = round(1000.0 / avg_ms, 1) if avg_ms else 0.0
            result["frame_ms"] = round(avg_ms, 2)
            if len(ft) >= 10:
                p1 = max(1, len(ft) // 100)
                worst = sorted(ft, reverse=True)[:p1]
                worst_avg = sum(worst) / len(worst)
                result["low1"] = round(1000.0 / worst_avg, 1) if worst_avg else 0.0

        return result

    def shutdown(self):
        pass


class FPSOverlay:
    """
    Birleşik arayüz: DLL varsa hook, yoksa software.
    Thread-safe, PySide6 Signal ile kolayca entegre edilir.
    """

    def __init__(self):
        self._backend = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._last: dict = {}
        self._callbacks: list = []
        self.mode = "none"

    def start(self, interval_ms: int = 500) -> str:
        """Overlay'i başlatır. Kullanılan backend adını döndürür."""
        if self._running:
            return self.mode

        if os.name == "nt" and DLL_PATH.exists():
            try:
                self._backend = _DllOverlay()
                self.mode = "directx_hook"
            except Exception as e:
                print(f"[Overlay] DLL yüklenemedi: {e}, software moduna geçiliyor.")
                self._backend = _SoftwareOverlay()
                self.mode = "software"
        else:
            self._backend = _SoftwareOverlay()
            self.mode = "software"

        self._running = True
        self._thread = threading.Thread(target=self._loop, args=(interval_ms,), daemon=True)
        self._thread.start()
        return self.mode

    def _loop(self, interval_ms: int):
        while self._running:
            try:
                self._last = self._backend.stats()
                for cb in list(self._callbacks):
                    try:
                        cb(self._last)
                    except Exception:
                        pass
            except Exception:
                pass
            time.sleep(interval_ms / 1000.0)

    def add_callback(self, fn):
        """fn(stats: dict) şeklinde çağrılır."""
        self._callbacks.append(fn)

    def remove_callback(self, fn):
        try:
            self._callbacks.remove(fn)
        except ValueError:
            pass

    def stats(self) -> dict:
        return dict(self._last)

    def tick(self):
        """Software modunda her çerçeve çağrılabilir (isteğe bağlı)."""
        if isinstance(self._backend, _SoftwareOverlay):
            self._backend.tick()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._backend:
            self._backend.shutdown()
        self.mode = "none"


# Singleton
overlay = FPSOverlay()
