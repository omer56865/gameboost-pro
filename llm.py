"""Yerel yapay zekâ (Ollama / OpenAI uyumlu sunucu) istemcisi. Arayüzden bağımsız."""
import json
import re
import urllib.request


class LLM:
    def __init__(self):
        self.kind, self.url, self.model = "Ollama", "http://localhost:11434", "qwen2.5:1.5b"

    def _req(self, path, data=None, timeout=600):
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(self.url.rstrip("/") + path, data=body,
                                     headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=timeout)

    def models(self):
        if self.kind == "Ollama":
            return [m["name"] for m in json.load(self._req("/api/tags", timeout=5))["models"]]
        return [m["id"] for m in json.load(self._req("/v1/models", timeout=5))["data"]]

    def stream(self, messages):
        if self.kind == "Ollama":
            r = self._req("/api/chat", {"model": self.model, "messages": messages, "stream": True,
                                        "options": {
                                            "temperature": 0.3, 
                                            "num_predict": 80,          # Düşük sistemler için yanıt uzunluğu sınırlandı
                                            "num_ctx": 512,             # Bellek tüketimini yarıya indiren bağlam boyutu
                                            "repeat_penalty": 1.2
                                        }}, timeout=600)
            for line in r:
                if line.strip():
                    j = json.loads(line)
                    yield j.get("message", {}).get("content", "")
                    if j.get("done"):
                        break
        else:
            r = self._req("/v1/chat/completions", {"model": self.model, "messages": messages,
                                                   "stream": True, "temperature": 0.3, "max_tokens": 80}, timeout=600)
            for line in r:
                line = line.decode().strip()
                if line.startswith("data:"):
                    p = line[5:].strip()
                    if p == "[DONE]":
                        break
                    yield json.loads(p)["choices"][0]["delta"].get("content") or ""

    def ask(self, messages):
        return "".join(self.stream(messages))


llm = LLM()


def pick_model(names, fallback):
    low = lambda n: n.lower()
    return (next((n for n in names if "qwen2.5" in low(n) and "1.5" in n and "coder" not in low(n)), None)
            or next((n for n in names if "qwen" in low(n) and "coder" not in low(n)), None)
            or next((n for n in names if "qwen" in low(n)), None)
            or (names[0] if names else fallback))


def connect(kind=None, url=None, model=None, manual=False):
    """Sunucuya bağlanır, modelleri listeler. Arka plan iş parçacığında çağır."""
    if kind:
        llm.kind = kind
    if url:
        llm.url = url
    try:
        names = llm.models()
        llm.model = model if (manual and model in names) else pick_model(names, llm.model)
        return {"ok": True, "names": names, "model": llm.model, "manual": manual}
    except Exception as e:
        return {"ok": False, "names": [], "model": llm.model, "err": str(e), "manual": manual}


def estimate_demand(game):
    """Veritabanında olmayan oyun için 1-5 ağırlık tahmini (küçük model, yaklaşık)."""
    out = llm.ask([
        {"role": "system", "content": "Sen oyun donanımı uzmanısın. Sadece 1-5 arası TEK rakam yaz. "
         "1=çok hafif (eski, 2D, e-spor), 3=orta, 5=çok ağır (yeni AAA, ray tracing)."},
        {"role": "user", "content": f"Oyun: {game}. Ağırlık (1-5):"}])
    m = re.search(r"[1-5]", out)
    return int(m.group()) if m else None


def explain_messages(p):
    return [
        {"role": "system", "content": "Sen oyun grafik ayarları konusunda yardımcı bir asistansın. Türkçe yaz. "
         "EN FAZLA 4 cümle yaz, madde listesi yapma, ayarları tek tek sayma. "
         "Terimler: FSR = AMD FidelityFX Super Resolution (düşük çözünürlükte çizip büyütür), "
         "DLSS = NVIDIA'nın yapay zekâ ile büyütme teknolojisi, XeSS = Intel'in büyütme teknolojisi, "
         "render ölçeği = oyunun gerçekte çizdiği çözünürlük oranı, frame generation = ara kare üretimi. "
         "Bilmediğin bir şeyi uydurma."},
        {"role": "user", "content": (
            f"GPU: {p['gpu']}. Oyun: {p['game']}. Seçilen: kalite {p['quality_preset']}, "
            f"{p['upscaler']} {p['upscaler_mode']}, render ölçeği %{int(p['render_scale'] * 100)}, "
            f"frame generation {'açık' if p['frame_generation'] else 'kapalı'}. "
            "Bu ayarlar neden seçildi ve FPS'e en çok hangi etki eder?")}]