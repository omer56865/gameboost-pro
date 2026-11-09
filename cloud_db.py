"""
Bulut oyun profili sistemi.
GitHub'daki games_db.json'ı otomatik günceller, yerel önbellek tutar.
"""
import json, urllib.request, time
from pathlib import Path

HOME = Path(__file__).parent
LOCAL_DB  = HOME / "games_db.json"
CACHE_META = HOME / "db_cache.json"

GITHUB_RAW = (
    "https://raw.githubusercontent.com/"
    "GITHUB_KULLANICI_ADI/gameboost-pro/main/games_db.json"
)
FALLBACK_LOCAL = LOCAL_DB


def _load_local() -> dict:
    if LOCAL_DB.exists():
        try:
            return json.loads(LOCAL_DB.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"_meta": {"version": "0"}, "games": {}}


def _save_local(db: dict) -> None:
    LOCAL_DB.write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")
    CACHE_META.write_text(json.dumps({"fetched_at": time.time()}), encoding="utf-8")


def _needs_refresh() -> bool:
    if not CACHE_META.exists():
        return True
    try:
        meta = json.loads(CACHE_META.read_text())
        return (time.time() - meta.get("fetched_at", 0)) > 3600  # 1 saatte bir güncelle
    except Exception:
        return True


def fetch(force=False) -> dict:
    """
    Yerel veritabanını döndürür. 1 saatten eski ise GitHub'dan günceller.
    Güncelleme başarısız olursa yerel versiyonu kullanır.
    """
    local = _load_local()
    if not force and not _needs_refresh():
        return local
    try:
        req = urllib.request.Request(GITHUB_RAW, headers={"User-Agent": "GameBoost-Pro/1.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            remote = json.loads(r.read())
        # Versiyon karşılaştır
        local_v = local.get("_meta", {}).get("version", "0")
        remote_v = remote.get("_meta", {}).get("version", "0")
        if remote_v > local_v or force:
            _save_local(remote)
            return remote
    except Exception:
        pass  # Offline veya repo henüz oluşturulmamış - sorun değil
    return local


def get_game(name: str, db: dict | None = None) -> dict | None:
    """Oyun adından (büyük/küçük harf duyarsız) profil döndürür."""
    if db is None:
        db = fetch()
    return db["games"].get(name.strip().lower())


def all_names(db: dict | None = None) -> list[str]:
    if db is None:
        db = fetch()
    return list(db["games"].keys())
