"""Evrensel Oyun Keşif Motoru: Steam, Epic Games, Xbox ve Özel .exe Tarayıcı."""
import json
import os
import winreg
from pathlib import Path

def get_epic_games():
    """Epic Games manifest dosyalarından kurulu oyunları bulur."""
    epic_games = []
    manifest_dir = Path(r"C:\ProgramData\Epic\EpicGamesLauncher\Data\Manifests")
    if not manifest_dir.exists():
        return epic_games
    
    for item in manifest_dir.glob("*.item"):
        try:
            data = json.loads(item.read_text(encoding="utf-8-sig"))
            name = data.get("DisplayName")
            install_path = data.get("InstallLocation")
            launch_executable = data.get("LaunchExecutable")
            if name and install_path:
                exe_path = Path(install_path) / launch_executable if launch_executable else None
                epic_games.append({
                    "name": name,
                    "path": str(exe_path) if exe_path and exe_path.exists() else install_path,
                    "launcher": "Epic Games"
                })
        except Exception:
            continue
    return epic_games

def get_xbox_games():
    """Windows kayıt defterinden ve uygulama dizinlerinden Microsoft Store/Xbox oyunlarını arar."""
    xbox_games = []
    # Xbox oyunları genellikle korumalı klasörlerdedir ancak kayıt defterinde izleri bulunur.
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths") as key:
            # Örnek tarama mantığı
            pass
    except Exception:
        pass
    return xbox_games

def scan_custom_folder(folder_path):
    """Belirtilen özel bir klasördeki tüm .exe dosyalarını oyun olarak tarar."""
    games = []
    root = Path(folder_path)
    if not root.exists():
        return games
    
    for exe in root.rglob("*.exe"):
        # Sistem dosyalarını ve uninstaller'ları ele
        name_lower = exe.name.lower()
        if any(x in name_lower for x in ["unins", "update", "setup", "crash", "unity", "helper", "service"]):
            continue
        # Boyutu 5 MB'tan küçük olanları ele (genelde ufak araçlardır)
        try:
            if exe.stat().st_size < 5 * 1024 * 1024:
                continue
        except Exception:
            continue
            
        games.append({
            "name": exe.stem.replace("_", " ").title(),
            "path": str(exe),
            "launcher": "Özel Klasör"
        })
    return games

def universal_scan(custom_dirs=None):
    """Tüm platformlardaki oyunları tek bir listede toplar."""
    all_games = []
    
    # 1. Steam (Mevcut adapters.py içindeki fonksiyonu çağırabilirsin)
    try:
        import adapters as ad
        for name, appid in ad.steam_games():
            all_games.append({"name": name, "path": f"steam://rungameid/{appid}", "launcher": "Steam"})
    except Exception:
        pass
        
    # 2. Epic Games
    all_games.extend(get_epic_games())
    
    # 3. Özel Taranan Klasörler
    if custom_dirs:
        for d in custom_dirs:
            all_games.extend(scan_custom_folder(d))
            
    return sorted(all_games, key=lambda x: x["name"])