"""GitHub Otomatik Sürüm Kontrolcüsü."""
import json, urllib.request

CURRENT_VERSION = "1.0.0"
# Gerçek repo adresi - GitHub'a yükledikten sonra burası otomatik doğru olacak
GITHUB_API = "https://api.github.com/repos/GITHUB_KULLANICI_ADI/gameboost-pro/releases/latest"
GITHUB_REPO = "https://github.com/GITHUB_KULLANICI_ADI/gameboost-pro"

def check_for_updates() -> dict:
    try:
        req = urllib.request.Request(GITHUB_API, headers={"User-Agent": "GameBoost-Pro/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            latest = data.get("tag_name", "").lstrip("v")
            url = data.get("html_url", GITHUB_REPO)
            if latest and latest != CURRENT_VERSION:
                return {"update_available": True, "version": latest, "url": url,
                        "notes": data.get("body", "")[:400]}
    except Exception:
        pass
    return {"update_available": False, "version": CURRENT_VERSION}
