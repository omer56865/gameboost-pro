"""
GameBoost Pro - Özel Çözünürlük ve Render Ölçekleyici (Custom Res Wizard)
"""
import ctypes
from ctypes import wintypes
import winreg

# Windows Display API Yapıları
class DEVMODEW(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmOrientation", ctypes.c_short),
        ("dmPaperSize", ctypes.c_short),
        ("dmPaperLength", ctypes.c_short),
        ("dmPaperWidth", ctypes.c_short),
        ("dmScale", ctypes.c_short),
        ("dmCopies", ctypes.c_short),
        ("dmDefaultSource", ctypes.c_short),
        ("dmPrintQuality", ctypes.c_short),
        ("dmColor", ctypes.c_short),
        ("dmDuplex", ctypes.c_short),
        ("dmYResolution", ctypes.c_short),
        ("dmTTOption", ctypes.c_short),
        ("dmCollate", ctypes.c_short),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]

DM_PELSWIDTH = 0x00080000
DM_PELSHEIGHT = 0x00100000
CDS_UPDATEREGISTRY = 0x01
CDS_TEST = 0x02

PRESET_RESOLUTIONS = [
    {"name": "1024 x 768 (4:3 Stretched - Yüksek FPS)", "w": 1024, "h": 768},
    {"name": "1280 x 720 (16:9 HD - Dengeli)", "w": 1280, "h": 720},
    {"name": "800 x 600 (4:3 Ultra Performans)", "w": 800, "h": 600},
    {"name": "1152 x 864 (4:3 Performans)", "w": 1152, "h": 864},
]

def change_resolution(width: int, height: int) -> tuple[bool, str]:
    """Windows ekran çözünürlüğünü dinamik olarak değiştirir."""
    user32 = ctypes.windll.user32
    devmode = DEVMODEW()
    devmode.dmSize = ctypes.sizeof(DEVMODEW)
    
    # Mevcut ayarları al
    if not user32.EnumDisplaySettingsW(None, -1, ctypes.byref(devmode)):
        return False, "Ekran ayarları okunamadı."
    
    devmode.dmPelsWidth = width
    devmode.dmPelsHeight = height
    devmode.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT
    
    # Test et
    test_res = user32.ChangeDisplaySettingsExW(None, ctypes.byref(devmode), None, CDS_TEST, None)
    if test_res != 0:
        return False, f"Çözünürlük monitör tarafından desteklenmiyor (Hata Kodu: {test_res})."
    
    # Uygula ve Registry'ye yaz
    apply_res = user32.ChangeDisplaySettingsExW(None, ctypes.byref(devmode), None, CDS_UPDATEREGISTRY, None)
    if apply_res == 0:
        return True, f"Çözünürlük başarıyla {width}x{height} yapıldı."
    return False, f"Çözünürlük değiştirilemedi (Hata Kodu: {apply_res})."

def get_current_resolution() -> tuple[int, int]:
    """Mevcut ekran çözünürlüğünü döndürür."""
    user32 = ctypes.windll.user32
    devmode = DEVMODEW()
    devmode.dmSize = ctypes.sizeof(DEVMODEW)
    if user32.EnumDisplaySettingsW(None, -1, ctypes.byref(devmode)):
        return devmode.dmPelsWidth, devmode.dmPelsHeight
    return 1920, 1080