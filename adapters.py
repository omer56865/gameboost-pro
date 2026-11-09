"""Oyun ayar dosyası adaptörleri: önizle -> yedekle -> uygula -> geri al.

Güvenlik kuralları:
  * Sadece dosyada ZATEN VAR OLAN anahtarlar değiştirilir (yeni anahtar eklenmez).
  * Her yazmadan önce orijinal dosya backups/ klasörüne kopyalanır.
  * Oyun açıkken (tespit edilebiliyorsa) yazılmaz.
  * Anti-cheat'li oyunlarda (Valorant) dosyaya hiç dokunulmaz, sadece oyun içi öneri verilir.
"""
import json, os, re, shutil, subprocess, time
from pathlib import Path

BACKUPS = Path(__file__).parent / "backups"

ALIASES = {
    "minecraft": "minecraft",
    "gta v": "gta5", "gta 5": "gta5", "grand theft auto v": "gta5",
    "counter-strike 2": "cs2", "cs2": "cs2", "cs 2": "cs2",
    "counter-strike 1.6": "cs16", "counter-strike": "cs16", "cs 1.6": "cs16", "cs1.6": "cs16",
    "valorant": "valorant",
}


def canon(name):
    return ALIASES.get(name.strip().lower())


# ---------- Konum bulucular ----------
def documents_dir():
    """OneDrive'a taşınmış Belgeler klasörünü de doğru bulur (Windows API)."""
    if os.name == "nt":
        try:
            import ctypes

            class GUID(ctypes.Structure):
                _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort),
                            ("d", ctypes.c_ubyte * 8)]
            g = GUID(0xFDD39AD0, 0x238F, 0x46AF, (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
            buf = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(buf)) == 0:
                return Path(buf.value)
        except Exception:
            pass
    return Path.home() / "Documents"


def steam_path():
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                p = Path(winreg.QueryValueEx(k, "SteamPath")[0])
                if p.exists():
                    return p
        except OSError:
            pass
    for c in (r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam", str(Path.home() / ".steam/steam")):
        if Path(c).exists():
            return Path(c)
    return None


def steam_games(sp=None):
    """Kurulu Steam oyunları: [(ad, appid)]"""
    sp = sp or steam_path()
    if not sp:
        return []
    libs = [sp]
    vdf = sp / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(errors="ignore")):
            p = Path(m.group(1).replace("\\\\", "\\"))
            if p not in libs:
                libs.append(p)
    games = []
    for lib in libs:
        for acf in (lib / "steamapps").glob("appmanifest_*.acf"):
            t = acf.read_text(errors="ignore")
            n, a = re.search(r'"name"\s+"([^"]+)"', t), re.search(r'"appid"\s+"(\d+)"', t)
            if n and a:
                games.append((n.group(1), a.group(1)))
    return sorted(set(games))


def cs2_video_file(sp=None):
    sp = sp or steam_path()
    if not sp:
        return None
    files = list((sp / "userdata").glob("*/730/local/cfg/cs2_video.txt"))
    return max(files, key=lambda f: f.stat().st_mtime) if files else None


# ---------- Düzenleme motoru ----------
PATTERNS = {
    "colon": lambda k: re.compile(r"^(%s:)([^\r\n]*)()" % re.escape(k), re.M),
    "vdf": lambda k: re.compile(r'("%s"\s+")([^"]*)(")' % re.escape(k)),
    "xml": lambda k: re.compile(r'(<%s\s+value=")([^"]*)(")' % re.escape(k)),
}


def read_text(p):
    b = Path(p).read_bytes()
    bom = b.startswith(b"\xef\xbb\xbf")
    return b[3:].decode("utf-8", "surrogateescape") if bom else b.decode("utf-8", "surrogateescape"), bom


def write_text(p, text, bom):
    data = text.encode("utf-8", "surrogateescape")
    Path(p).write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)


def edit_text(text, kind, edits):
    changes, skipped = [], []
    for k, v in edits.items():
        rx = PATTERNS[kind](k)
        m = rx.search(text)
        if not m:
            skipped.append(k)
            continue
        if m.group(2) == str(v):
            continue
        changes.append((k, m.group(2), str(v)))
        text = rx.sub(lambda m, v=v: m.group(1) + str(v) + m.group(3), text, count=1)
    return text, changes, skipped


# ---------- Hazır ayar tabloları (yalnızca doğrulanmış anahtar/değer aralıkları) ----------
def level_of(prof):
    return {"Ultra/Yüksek": "high", "Yüksek/Orta": "medium", "Orta/Düşük": "medium", "Düşük": "low"}.get(
        prof.get("quality_preset"), "medium")


def make_plan(game_name, prof):
    g = canon(game_name)
    lv, vram, fps = level_of(prof), prof.get("vram_gb") or 4, int(prof.get("target_fps") or 60)
    plan = {"game": g, "writes": False, "path": None, "kind": None, "edits": {}, "notes": [], "exe": None}
    if g is None:
        plan["notes"].append("Bu oyun için ayar adaptörü yok (Minecraft, GTA V, CS2 destekli).")
        return plan

    if g == "minecraft":
        base = Path(os.environ.get("APPDATA", Path.home())) / ".minecraft" / "options.txt"
        t = {"low": dict(rd=6, sim=5, part=2, shadow="false", mip=0, blend=0, fancy=0),
             "medium": dict(rd=10, sim=8, part=1, shadow="false", mip=2, blend=1, fancy=1),
             "high": dict(rd=16, sim=12, part=0, shadow="true", mip=4, blend=3, fancy=1)}[lv]
        plan.update(writes=True, path=base, kind="colon", edits={
            "renderDistance": t["rd"], "simulationDistance": t["sim"], "particles": t["part"],
            "entityShadows": t["shadow"], "mipmapLevels": t["mip"], "biomeBlendRadius": t["blend"],
            "maxFps": min(max(fps, 30), 260), "graphicsMode": t["fancy"],
            "fancyGraphics": "true" if t["fancy"] else "false"})
        plan["notes"] += ["Minecraft'ı KAPALI tutarak uygula, açıkken çıkışta ayarların üzerine yazar.",
                          "Farklı launcher (Prism, CurseForge) kullanıyorsan options.txt başka klasördedir.",
                          "Oyun hâlâ ağır geliyorsa Sodium (Fabric) modu en büyük farkı yaratır."]
    elif g == "gta5":
        p = documents_dir() / "Rockstar Games" / "GTA V" / "settings.xml"
        t = {"low": dict(tess=0, shadow=0, refl=0, ssao=0, af=0, tex=0),
             "medium": dict(tess=0, shadow=1, refl=1, ssao=0, af=4, tex=1),
             "high": dict(tess=1, shadow=2, refl=2, ssao=1, af=8, tex=2)}[lv]
        if vram < 3:
            t["tex"] = 0
        edits = {"Tessellation": t["tess"], "ShadowQuality": t["shadow"], "ReflectionQuality": t["refl"],
                 "SSAO": t["ssao"], "AnisotropicFiltering": t["af"], "TextureQuality": t["tex"]}
        if lv != "high":
            edits.update({"MSAA": 0, "MSAAFragments": 0, "ReflectionMSAA": 0})
        plan.update(writes=True, path=p, kind="xml", edits=edits, exe="GTA5.exe")
        plan["notes"] += ["Sadece tek kişilik (Story) modda kullanman önerilir. Topluluk bu dosyanın düzenlenmesinin "
                          "güvenli olduğunu söylüyor ama bu Rockstar'ın resmi açıklaması değil; GTA Online'da risk alma.",
                          "Dosya yoksa oyunu bir kez açıp kapat. Ayarlar kaydedilmiyorsa dosya salt-okunur olabilir."]
    elif g == "cs2":
        t = {"low": dict(shadow=0, tex=0, ao=0, part=0, msaa=0, shader=0, filt=0, dyn=0),
             "medium": dict(shadow=2, tex=1, ao=0, part=0, msaa=2, shader=0, filt=3, dyn=1),
             "high": dict(shadow=2, tex=1, ao=2, part=0, msaa=4, shader=1, filt=5, dyn=1)}[lv]
        plan.update(writes=True, path=cs2_video_file(), kind="vdf", exe="cs2.exe", edits={
            "setting.videocfg_shadow_quality": t["shadow"], "setting.videocfg_texture_detail": t["tex"],
            "setting.videocfg_ao_detail": t["ao"], "setting.videocfg_particle_detail": t["part"],
            "setting.msaa_samples": t["msaa"], "setting.shaderquality": t["shader"],
            "setting.r_texturefilteringquality": t["filt"], "setting.videocfg_dynamic_shadows": t["dyn"]})
        plan["notes"] += ["CS2 kapalıyken uygula. Dosya yoksa oyunu açıp video ayarlarını bir kez kaydet.",
                          "Sadece kendi ayar dosyan düzenlenir (VAC açısından oyunun menüsünün yaptığı işin aynısı)."]
    elif g == "cs16":
        plan["notes"] += ["CS 1.6 çok hafif bir oyun; neredeyse her PC'de sorunsuz çalışır, dosya düzenlemeye gerek yok.",
                          "Konsola (F10 / ~) 'fps_max 144' yazarak FPS sınırını ekranının yenileme hızına ayarlayabilirsin.",
                          "Takılma varsa Windows'ta oyun için 'Yüksek performans' GPU seç ve arka plan uygulamalarını kapat."]
    elif g == "valorant":
        plan["notes"] += ["Vanguard anti-cheat nedeniyle Valorant dosyalarına KESİNLİKLE dokunmuyorum.",
                          "Oyun içinden öneri: Multithreaded Rendering AÇIK, VSync KAPALI, Material/Texture/Detail Quality DÜŞÜK, "
                          "Bloom, Distortion ve Cast Shadows KAPALI, Anti-Aliasing MSAA 1x ya da kapalı.",
                          "FPS sınırını 'Always' modunda ekran yenileme hızının biraz üstüne koy."]
    return plan


# ---------- Önizle / uygula / geri al ----------
def running(exe):
    if not exe or os.name != "nt":
        return False
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {exe}"], capture_output=True, text=True).stdout
    return exe.lower() in out.lower()


def preview(plan):
    """-> (changes, skipped, error)"""
    p = plan["path"]
    if not plan["writes"]:
        return [], [], None
    if not p or not Path(p).exists():
        return [], [], f"Ayar dosyası bulunamadı: {p or '(yol tespit edilemedi)'}. Oyunu bir kez açıp kapatınca oluşur."
    text, _ = read_text(p)
    _, changes, skipped = edit_text(text, plan["kind"], plan["edits"])
    return changes, skipped, None


def apply(plan):
    changes, skipped, err = preview(plan)
    if err:
        return err
    if running(plan["exe"]):
        return f"{plan['exe']} çalışıyor. Önce oyunu kapat, sonra tekrar dene."
    if not changes:
        return "Zaten uygun: değiştirilecek bir şey yok."
    p = Path(plan["path"])
    d = BACKUPS / plan["game"] / time.strftime("%Y%m%d-%H%M%S")
    d.mkdir(parents=True)
    shutil.copy2(p, d / p.name)
    (d / "origin.json").write_text(json.dumps({"path": str(p)}), encoding="utf-8")
    text, bom = read_text(p)
    new, _, _ = edit_text(text, plan["kind"], plan["edits"])
    write_text(p, new, bom)
    return f"{len(changes)} ayar yazıldı. Yedek: {d}"


def restore(game_name):
    g = canon(game_name)
    runs = sorted((BACKUPS / (g or "_")).glob("*")) if g else []
    if not runs:
        return "Bu oyun için yedek yok."
    d = runs[-1]
    origin = Path(json.loads((d / "origin.json").read_text(encoding="utf-8"))["path"])
    exe = {"gta5": "GTA5.exe", "cs2": "cs2.exe"}.get(g)
    if running(exe):
        return f"{exe} çalışıyor. Önce oyunu kapat."
    shutil.copy2(d / origin.name, origin)
    shutil.rmtree(d)
    return f"Geri alındı: {origin}"
