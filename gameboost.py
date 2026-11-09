#!/usr/bin/env python3
"""GameBoost - AI destekli oyun optimizasyon aracı (Adım 1-4).

  detect                       Donanımı algılar                      (Adım 1)
  recommend "Oyun" [--target]  Ayar + upscaler/frame-gen önerir      (Adım 1)
  monitor frames.csv [--follow] FPS'e göre render ölçeğini ayarlar   (Adım 2)
  textures KLASÖR [--apply]    Dokuları yedekleyip küçültür          (Adım 3)
  train / predict              Kendi verinden FPS tahmin modeli      (Adım 4)

Gereken: Python 3.9+. İsteğe bağlı: pip install pillow scikit-learn joblib psutil
"""
import argparse, csv, json, os, platform, re, shutil, subprocess, sys, time
from pathlib import Path

HOME = Path(__file__).parent
PROFILE, HISTORY, MODEL = HOME / "profile.json", HOME / "history.csv", HOME / "fps_model.joblib"
FIELDS = ["gpu_tier", "vram_gb", "ram_gb", "cores", "demand", "render_scale", "fg", "avg_fps"]

# Düzenlenebilir oyun veritabanı: demand 1 (hafif) - 5 (çok ağır)
GAMES = {
    "cyberpunk 2077": {"demand": 5, "anticheat": False},
    "elden ring": {"demand": 3, "anticheat": False},
    "counter-strike 2": {"demand": 2, "anticheat": True},
    "fortnite": {"demand": 4, "anticheat": True},
    "minecraft": {"demand": 2, "anticheat": False},
    "gta v": {"demand": 3, "anticheat": False},
    "valorant": {"demand": 2, "anticheat": True},
    "the witcher 3": {"demand": 3, "anticheat": False},
    "counter-strike 1.6": {"demand": 1, "anticheat": False},
    "gta 5": {"demand": 3, "anticheat": False},
    "counter-strike": {"demand": 1, "anticheat": False},
    "grand theft auto v": {"demand": 3, "anticheat": False},
}
# (regex, tier) - sırayla denenir, ilk eşleşen kazanır
TIERS = [
    (r"rtx\s*(40[789]0|30[89]0|3070)|rx\s*(7[89]00|69[05]0|68\d0)", 5),
    (r"rtx\s*(40[56]0|3060|2070|2080)|rx\s*(76\d0|66\d0|67\d0|6800)", 4),
    (r"rtx\s*(3050|2060)|gtx\s*(1660|1070|1080|1060)|rx\s*(580|590|5[5-7]00|6[45]00)|arc\s*a[57]", 3),
    (r"gtx\s*(1650|1050|960|970|750)|rx\s*(550|560|570)|arc\s*a3", 2),
    (r"uhd|iris|vega|radeon\(tm\)\s*graphics|gt\s*(710|1030)|mx\d+|intel\(r\)\s*hd", 1),
]
VRAM_BY_TIER = {1: 2, 2: 4, 3: 6, 4: 8, 5: 12}


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def gpu_tier(name):
    n = name.lower()
    for rx, t in TIERS:
        if re.search(rx, n):
            return t
    return 3  # bilinmiyorsa orta varsay


def detect():
    osn = platform.system()
    info = {"os": osn, "cpu": platform.processor() or platform.machine(),
            "cores": os.cpu_count(), "ram_gb": None, "gpus": []}
    try:
        import psutil
        info["ram_gb"] = round(psutil.virtual_memory().total / 2**30, 1)
    except ImportError:
        if osn == "Linux":
            m = re.search(r"MemTotal:\s+(\d+)", Path("/proc/meminfo").read_text())
            info["ram_gb"] = round(int(m.group(1)) / 2**20, 1)
        elif osn == "Windows":
            v = sh(["powershell", "-NoProfile", "-Command",
                    "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"])
            info["ram_gb"] = round(int(v) / 2**30, 1) if v.isdigit() else None
    out = sh(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
    for line in out.splitlines():
        name, mem = [x.strip() for x in line.split(",")]
        info["gpus"].append({"name": name, "vram_gb": round(float(mem) / 1024, 1)})
    if not info["gpus"]:
        if osn == "Windows":
            out = sh(["powershell", "-NoProfile", "-Command",
                      "(Get-CimInstance Win32_VideoController).Name"])
        elif osn == "Linux":
            out = "\n".join(l.split(": ", 1)[-1] for l in sh(["lspci"]).splitlines() if "VGA" in l or "3D" in l)
        for name in out.splitlines():
            if name.strip():
                info["gpus"].append({"name": name.strip(), "vram_gb": None})
    # en güçlü GPU'yu (ayrık kart) seç
    for g in info["gpus"]:
        g["tier"] = gpu_tier(g["name"])
        g["vram_gb"] = g["vram_gb"] or VRAM_BY_TIER[g["tier"]]
    info["gpus"].sort(key=lambda g: g["tier"], reverse=True)
    return info


def recommend(game, target=60):
    hw = detect()
    if not hw["gpus"]:
        sys.exit("GPU algılanamadı.")
    gpu = hw["gpus"][0]
    g = GAMES.get(game.lower())
    note = []
    if g is None:
        g = {"demand": 3, "anticheat": False}
        note.append("Oyun veritabanında yok, orta ağırlıkta varsayıldı (GAMES sözlüğüne ekleyebilirsin).")
    margin = gpu["tier"] - g["demand"]
    presets = {1: ("Ultra/Yüksek", 1.0, "Kapalı"), 0: ("Yüksek/Orta", 0.67, "Quality"),
               -1: ("Orta/Düşük", 0.58, "Balanced"), -2: ("Düşük", 0.5, "Performance")}
    quality, scale, mode = presets[max(-2, min(1, margin))]
    name = gpu["name"].lower()
    if "rtx" in name:
        upscaler = "DLSS"
    elif "arc" in name:
        upscaler = "XeSS"
    else:
        upscaler = "FSR"
    if mode == "Kapalı":
        upscaler = "Yok (native)"
    tex = "Yüksek" if gpu["vram_gb"] >= 8 and margin >= 0 else "Orta" if gpu["vram_gb"] >= 4 else "Düşük"
    # Frame generation: yeterli taban FPS yoksa gecikme/artefakt yüzünden önerilmez
    fg = margin >= 0 and gpu["tier"] >= 3 and target > 60 and not g["anticheat"]
    if fg:
        note.append("Frame generation yalnızca taban FPS ~45+ ise kullan; gecikmeyi artırır.")
    if g["anticheat"]:
        note.append("Anti-cheat var: dışarıdan müdahale eden araçlar ban riski taşıyabilir; oyunun kendi DLSS/FSR seçeneğini kullan.")
    if (hw["ram_gb"] or 16) < 12:
        note.append("RAM düşük: arka plan uygulamalarını kapat.")
    prof = {"game": game, "gpu": gpu["name"], "gpu_tier": gpu["tier"], "vram_gb": gpu["vram_gb"],
            "ram_gb": hw["ram_gb"], "cores": hw["cores"], "demand": g["demand"],
            "quality_preset": quality, "texture_quality": tex, "upscaler": upscaler,
            "upscaler_mode": mode, "render_scale": scale, "frame_generation": fg,
            "target_fps": target, "notes": note}
    PROFILE.write_text(json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")
    return prof


# ---------- Adım 2: dinamik kontrol ----------
def read_frametimes(path, last=600):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    col = next((c for c in rows[0] if c.lower() in ("msbetweenpresents", "frametime", "frametime_ms")), None)
    if not col:
        sys.exit("CSV'de MsBetweenPresents/FrameTime sütunu yok (PresentMon çıktısı kullan).")
    return [float(r[col]) for r in rows[-last:] if r[col]]


def analyze(ft, target, scale, fg=False):
    ft_sorted = sorted(ft, reverse=True)
    avg = 1000 / (sum(ft) / len(ft))
    low1 = 1000 / ft_sorted[max(0, len(ft) // 100)]
    new = scale
    if low1 < target * 0.85 or avg < target * 0.95:
        new = max(0.5, round(scale - 0.05, 2))
    elif avg > target * 1.2 and low1 > target * 1.0:
        new = min(1.0, round(scale + 0.05, 2))  # fazladan güç varsa kaliteyi geri ver
    return avg, low1, new


def monitor(csv_path, target, follow):
    prof = json.loads(PROFILE.read_text(encoding="utf-8")) if PROFILE.exists() else {}
    scale = prof.get("render_scale", 1.0)
    while True:
        avg, low1, new = analyze(read_frametimes(csv_path), target, scale)
        print(f"Ort FPS {avg:.1f} | %1 low {low1:.1f} | ölçek {scale} -> {new}")
        if prof:
            new_file = not HISTORY.exists()
            with open(HISTORY, "a", newline="") as f:
                w = csv.writer(f)
                if new_file:
                    w.writerow(FIELDS)
                w.writerow([prof["gpu_tier"], prof["vram_gb"], prof["ram_gb"], prof["cores"], prof["demand"],
                            scale, int(prof["frame_generation"]), round(avg, 1)])
            prof["render_scale"] = new
            PROFILE.write_text(json.dumps(prof, indent=2, ensure_ascii=False), encoding="utf-8")
        scale = new
        if not follow:
            break
        time.sleep(10)


# ---------- Adım 3: doku optimizasyonu ----------
def textures(folder, max_px, apply):
    try:
        from PIL import Image
    except ImportError:
        sys.exit("pip install pillow gerekli.")
    root = Path(folder)
    backup = root.parent / (root.name + "_backup")
    saved = n = 0
    for p in root.rglob("*"):
        if p.suffix.lower() not in (".png", ".jpg", ".jpeg", ".tga", ".bmp"):
            continue
        with Image.open(p) as im:
            w, h = im.size
            if max(w, h) <= max_px:
                continue
            k = max_px / max(w, h)
            size = (max(1, int(w * k)), max(1, int(h * k)))
            before = p.stat().st_size
            print(f"{'KÜÇÜLT' if apply else 'DRY-RUN'} {p.relative_to(root)} {w}x{h} -> {size[0]}x{size[1]}")
            n += 1
            if apply:
                dest = backup / p.relative_to(root)
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    shutil.copy2(p, dest)
                im.resize(size, Image.LANCZOS).save(p)
                saved += before - p.stat().st_size
    print(f"{n} dosya." + (f" Kazanılan: {saved/2**20:.1f} MB. Yedek: {backup}" if apply else " Uygulamak için --apply ekle."))


# ---------- Adım 4: kendi modelini eğit ----------
def train():
    try:
        import pandas as pd, joblib
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import cross_val_score
    except ImportError:
        sys.exit("pip install pandas scikit-learn joblib gerekli.")
    df = pd.read_csv(HISTORY)
    if len(df) < 30:
        sys.exit(f"En az 30 ölçüm gerek, şu an {len(df)}. 'monitor' ile veri biriktir.")
    X, y = df[FIELDS[:-1]], df["avg_fps"]
    m = GradientBoostingRegressor(random_state=0)
    r2 = cross_val_score(m, X, y, cv=5, scoring="r2").mean()
    m.fit(X, y)
    joblib.dump(m, MODEL)
    print(f"Model kaydedildi. Çapraz doğrulama R2 = {r2:.2f}")


def predict(args):
    import joblib
    m = joblib.load(MODEL)
    print(f"Tahmini FPS: {m.predict([args])[0]:.1f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("detect")
    r = sp.add_parser("recommend"); r.add_argument("game"); r.add_argument("--target", type=int, default=60)
    m = sp.add_parser("monitor"); m.add_argument("csv"); m.add_argument("--target", type=int, default=60); m.add_argument("--follow", action="store_true")
    t = sp.add_parser("textures"); t.add_argument("folder"); t.add_argument("--max", type=int, default=2048); t.add_argument("--apply", action="store_true")
    sp.add_parser("train")
    p = sp.add_parser("predict"); p.add_argument("values", type=float, nargs=7, metavar=("TIER", "VRAM", "RAM", "CORES", "DEMAND", "SCALE", "FG"))
    a = ap.parse_args()
    if a.cmd == "detect": print(json.dumps(detect(), indent=2, ensure_ascii=False))
    elif a.cmd == "recommend": print(json.dumps(recommend(a.game, a.target), indent=2, ensure_ascii=False))
    elif a.cmd == "monitor": monitor(a.csv, a.target, a.follow)
    elif a.cmd == "textures": textures(a.folder, a.max, a.apply)
    elif a.cmd == "train": train()
    elif a.cmd == "predict": predict(a.values)


if __name__ == "__main__":
    main()
