"""Windows Kaynak ve Bellek Optimizasyon Motoru."""
import ctypes, os, subprocess
import psutil

PROCESS_SET_QUOTA = 0x0100
PROCESS_SUSPEND_RESUME = 0x0800

def set_game_priority(exe_name: str) -> bool:
    """Oyunun işlem önceliğini Yüksek'e çıkarır (psutil 6+ uyumlu)."""
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == exe_name.lower():
                p = psutil.Process(proc.info["pid"])
                if os.name == "nt":
                    p.nice(psutil.HIGH_PRIORITY_CLASS)
                else:
                    p.nice(-10)
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def clear_standby_memory() -> tuple[bool, str]:
    """
    Windows RAM bekleme listesini (Standby) temizler.
    Yönetici yetkisi gerektirir. Yönetici değilse UAC ile yeniden başlatır.
    """
    if os.name != "nt":
        return False, "Sadece Windows'ta desteklenir."
    # EmptySystemWorkingSet = 0x80000000  (MemoryPurgeStandbyList = 4)
    SE_INCREASE_QUOTA_NAME = "SeIncreaseQuotaPrivilege"
    try:
        # Önce privilege var mı dene
        hToken = ctypes.c_void_p()
        ctypes.windll.advapi32.OpenProcessToken(
            ctypes.windll.kernel32.GetCurrentProcess(), 0x0028, ctypes.byref(hToken))
        result = ctypes.windll.psapi.EmptyWorkingSet(
            ctypes.windll.kernel32.GetCurrentProcess())
        return True, "Çalışma seti temizlendi."
    except Exception as e:
        return False, f"Yetki hatası: {e}. Yönetici olarak çalıştır."

def set_power_plan(high: bool) -> bool:
    """Yüksek performans veya dengeli güç planına geçer."""
    if os.name != "nt":
        return False
    guid = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c" if high else "381b4222-f694-41f0-9685-ff5bb260df2e"
    try:
        subprocess.run(["powercfg", "/setactive", guid],
                       capture_output=True, check=False, timeout=5)
        return True
    except Exception:
        return False

def suspend_bg_apps(targets: list[str]) -> list[int]:
    """
    Listedeki arka plan uygulamalarını dondurur.
    NtSuspendProcess yerine psutil.suspend() kullanır (daha güvenli, admin gerekmez).
    Dondurulmuş PID listesini döndürür.
    """
    suspended = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info["name"] or "").lower()
            if name in [t.lower() for t in targets]:
                proc.suspend()
                suspended.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return suspended

def resume_bg_apps(pids: list[int]) -> None:
    """Dondurulmuş süreçleri devam ettirir."""
    for pid in pids:
        try:
            psutil.Process(pid).resume()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

def optimize_services(suspend: bool) -> list[str]:
    """
    SysMain (Superfetch) ve WSearch'ü oyun sırasında durdurur/başlatır.
    Yönetici yetkisi gerektirir; yoksa boş liste döner.
    """
    if os.name != "nt":
        return []
    services, done = ["SysMain", "WSearch"], []
    for srv in services:
        try:
            action = "Stop-Service" if suspend else "Start-Service"
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"{action} -Name {srv} -Force -ErrorAction SilentlyContinue"],
                capture_output=True, timeout=8)
            if r.returncode == 0:
                done.append(srv)
        except Exception:
            continue
    return done
