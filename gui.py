#!/usr/bin/env python3
"""GameBoost arayüzü + yerel Qwen entegrasyonu. Çalıştır: python gui.py"""
import contextlib, io, json, re, threading, urllib.request
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import gameboost as gb
import adapters as ad

BG, PANEL, FG, MUTED, ACCENT = "#12141a", "#1b1e27", "#e6e8ee", "#8b90a0", "#4f8cff"


class LLM:
    """Ollama (varsayılan) veya OpenAI uyumlu sunucu (LM Studio, llama.cpp)."""
    def __init__(self):
        self.kind, self.url, self.model = "Ollama", "http://localhost:11434", "qwen2.5:1.5b"

    def _req(self, path, data=None, timeout=300):
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
                                        "options": {"temperature": 0.3, "num_predict": 220,
                                                    "repeat_penalty": 1.2}})
            for line in r:
                if line.strip():
                    j = json.loads(line)
                    yield j.get("message", {}).get("content", "")
                    if j.get("done"):
                        break
        else:
            r = self._req("/v1/chat/completions", {"model": self.model, "messages": messages,
                                                   "stream": True, "temperature": 0.3})
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


def estimate_demand(game):
    """Veritabanında olmayan oyun için Qwen'den 1-5 ağırlık tahmini (küçük model, yaklaşık!)."""
    out = llm.ask([
        {"role": "system", "content": "Sen oyun donanımı uzmanısın. Sadece 1-5 arası TEK rakam yaz. "
         "1=çok hafif (eski, 2D, e-spor), 3=orta, 5=çok ağır (yeni AAA, ray tracing)."},
        {"role": "user", "content": f"Oyun: {game}. Ağırlık (1-5):"}])
    m = re.search(r"[1-5]", out)
    return int(m.group()) if m else None


def capture(fn, *a):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            fn(*a)
        except SystemExit as e:
            print(e)
        except Exception as e:
            print("Hata:", e)
    return buf.getvalue()


def fmt_hw(hw):
    s = f"İşletim sistemi : {hw['os']}\nİşlemci         : {hw['cpu']}  ({hw['cores']} çekirdek)\nRAM             : {hw['ram_gb']} GB\n\n"
    for g in hw["gpus"] or []:
        s += f"GPU : {g['name']}\n      VRAM {g['vram_gb']} GB  |  güç sınıfı {g['tier']}/5\n"
    return s if hw["gpus"] else s + "GPU algılanamadı.\n"


def fmt_prof(p):
    s = (f"Oyun            : {p['game']}\nGPU             : {p['gpu']}  (sınıf {p['gpu_tier']}/5)\n"
         f"Oyun ağırlığı   : {p['demand']}/5\n\n── ÖNERİLEN AYARLAR ──\n"
         f"Kalite          : {p['quality_preset']}\nDoku kalitesi   : {p['texture_quality']}\n"
         f"Upscaler        : {p['upscaler']}  ({p['upscaler_mode']})\n"
         f"Render ölçeği   : %{int(p['render_scale']*100)}\n"
         f"Frame generation: {'Açık' if p['frame_generation'] else 'Kapalı'}\n"
         f"Hedef FPS       : {p['target_fps']}\n")
    for n in p["notes"]:
        s += f"\n⚠ {n}"
    return s


class App:
    def __init__(self, root):
        self.root = root
        root.title("GameBoost")
        root.geometry("900x640")
        root.configure(bg=BG)
        self.style()
        self.hw, self.profile, self.history = None, None, []
        head = tk.Frame(root, bg=BG)
        head.pack(fill="x", padx=18, pady=(14, 4))
        tk.Label(head, text="GameBoost", font=("Segoe UI", 20, "bold"), bg=BG, fg=FG).pack(side="left")
        tk.Label(head, text="  AI destekli oyun optimizasyonu", bg=BG, fg=MUTED).pack(side="left", pady=(8, 0))
        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True, padx=14, pady=6)
        self.tab_hw(); self.tab_rec(); self.tab_games(); self.tab_mon(); self.tab_tex(); self.tab_ai()
        self.status = tk.Label(root, text="● AI: kontrol ediliyor…", anchor="w", bg=BG, fg=MUTED)
        self.status.pack(fill="x", padx=18, pady=(0, 8))
        self.bg(self.refresh_hw)
        self.bg(self.connect_ai)

    # ---------- yardımcılar ----------
    def style(self):
        s = ttk.Style(); s.theme_use("clam")
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(16, 8), borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", "white")])
        s.configure("TFrame", background=PANEL)
        s.configure("TLabel", background=PANEL, foreground=FG)
        s.configure("TButton", background=ACCENT, foreground="white", padding=(14, 6), borderwidth=0)
        s.map("TButton", background=[("active", "#6ba0ff")])
        s.configure("TCheckbutton", background=PANEL, foreground=FG)

    def bg(self, fn, *a):
        threading.Thread(target=fn, args=a, daemon=True).start()

    def ui(self, fn, *a, **kw):
        self.root.after(0, lambda: fn(*a, **kw))

    def textbox(self, parent):
        t = tk.Text(parent, bg="#0e1015", fg=FG, insertbackground=FG, relief="flat", wrap="word",
                    font=("Consolas", 10), padx=12, pady=10, state="disabled")
        t.tag_config("me", foreground=ACCENT, font=("Consolas", 10, "bold"))
        t.tag_config("ai", foreground="#7ee0a0")
        return t

    def put(self, t, text, tag=None, clear=False):
        t.config(state="normal")
        if clear:
            t.delete("1.0", "end")
        t.insert("end", text, tag)
        t.see("end"); t.config(state="disabled")

    def frame(self, title):
        f = ttk.Frame(self.nb, padding=14)
        self.nb.add(f, text=title)
        return f

    # ---------- Donanım ----------
    def tab_hw(self):
        f = self.frame("Donanım")
        ttk.Button(f, text="Yenile", command=lambda: self.bg(self.refresh_hw)).pack(anchor="w")
        self.hw_t = self.textbox(f); self.hw_t.pack(fill="both", expand=True, pady=(10, 0))

    def refresh_hw(self):
        self.hw = gb.detect()
        self.ui(self.put, self.hw_t, fmt_hw(self.hw), None, True)

    # ---------- Öneri ----------
    def tab_rec(self):
        f = self.frame("Öneri")
        row = ttk.Frame(f); row.pack(fill="x")
        ttk.Label(row, text="Oyun:").pack(side="left")
        self.game = ttk.Combobox(row, values=["Minecraft", "GTA V", "Counter-Strike 2", "Counter-Strike 1.6", "Valorant"] + [g.title() for g in gb.GAMES if ad.canon(g) is None], width=30)
        self.game.pack(side="left", padx=8); self.game.set("Minecraft")
        ttk.Label(row, text="Hedef FPS:").pack(side="left", padx=(10, 0))
        self.target = tk.Spinbox(row, from_=30, to=240, width=5, increment=10)
        self.target.delete(0, "end"); self.target.insert(0, "60"); self.target.pack(side="left", padx=8)
        ttk.Button(row, text="Öneri Al", command=lambda: self.bg(self.do_rec)).pack(side="left", padx=4)
        ttk.Button(row, text="Ayarları Uygula", command=lambda: self.bg(self.do_apply)).pack(side="left", padx=4)
        ttk.Button(row, text="Geri Al", command=lambda: self.bg(self.do_restore)).pack(side="left", padx=4)
        self.rec_t = self.textbox(f); self.rec_t.pack(fill="both", expand=True, pady=(10, 0))

    def do_rec(self):
        game, target = self.game.get().strip(), int(self.target.get())
        if not game:
            return
        extra = []
        if game.lower() not in gb.GAMES:
            self.ui(self.put, self.rec_t, "Oyun veritabanında yok, Qwen'e soruluyor…\n", None, True)
            try:
                d = estimate_demand(game)
            except Exception:
                d = None
            if d:
                gb.GAMES[game.lower()] = {"demand": d, "anticheat": False}
                extra.append("Oyun ağırlığı yerel AI tarafından tahmin edildi (yaklaşık). Online/anti-cheat'li bir oyunsa dışarıdan müdahaleyi kontrol et.")
        try:
            p = gb.recommend(game, target)
        except SystemExit as e:
            self.ui(self.put, self.rec_t, f"{e}\n", None, True); return
        p["notes"] += extra
        self.profile = p
        self.ui(self.put, self.rec_t, fmt_prof(p) + "\n", None, True)
        if self.status.cget("fg") == "#7ee0a0":
            self.ui(self.put, self.rec_t, "\n── AI AÇIKLAMASI ──\n", "me")
            try:
                for tok in llm.stream([
                    {"role": "system", "content": "Sen oyun grafik ayarları konusunda yardımcı bir asistansın. Türkçe yaz. EN FAZLA 4 cümle yaz, madde listesi yapma, ayarları tek tek sayma. "
                     "Terimler: FSR = AMD FidelityFX Super Resolution (düşük çözünürlükte çizip büyütür), DLSS = NVIDIA'nın yapay zekâ ile büyütme teknolojisi, "
                     "XeSS = Intel'in büyütme teknolojisi, render ölçeği = oyunun gerçekte çizdiği çözünürlük oranı, frame generation = ara kare üretimi. Bilmediğin bir şeyi uydurma."},
                    {"role": "user", "content": (f"GPU: {p['gpu']}. Oyun: {p['game']}. Seçilen: kalite {p['quality_preset']}, "
                     f"{p['upscaler']} {p['upscaler_mode']}, render ölçeği %{int(p['render_scale']*100)}, "
                     f"frame generation {'açık' if p['frame_generation'] else 'kapalı'}. Bu ayarlar neden seçildi ve FPS'e en çok hangisi etki eder?")}]):
                    self.ui(self.put, self.rec_t, tok, "ai")
            except Exception as e:
                self.ui(self.put, self.rec_t, f"(AI açıklaması alınamadı: {e})", "ai")

    # ---------- Oyunlarım ----------
    def tab_games(self):
        f = self.frame("Oyunlarım")
        ttk.Button(f, text="Steam oyunlarını tara", command=lambda: self.bg(self.scan_games)).pack(anchor="w")
        self.glist = tk.Listbox(f, bg="#0e1015", fg=FG, relief="flat", font=("Consolas", 10), selectbackground=ACCENT, activestyle="none")
        self.glist.pack(fill="both", expand=True, pady=(10, 0))
        self.glist.bind("<Double-Button-1>", self.pick_game)
        self.glist.insert("end", "Tara'ya bas. Desteklenen oyuna çift tıklayınca Öneri sekmesine geçer.")

    def scan_games(self):
        games = ad.steam_games()
        def show():
            self.glist.delete(0, "end")
            if not games:
                self.glist.insert("end", "Steam oyunu bulunamadı (Minecraft/GTA V başka launcher'dan olabilir; elle seç).")
            for name, appid in games:
                mark = "✔ " if ad.canon(name) or appid in ("730", "271590", "10") else "  "
                self.glist.insert("end", f"{mark}{name}")
        self.ui(show)

    def pick_game(self, _e):
        sel = self.glist.curselection()
        if sel:
            self.game.set(self.glist.get(sel[0]).strip(" ✔"))
            self.nb.select(1)

    # ---------- Uygula / Geri al ----------
    def do_apply(self):
        game, target = self.game.get().strip(), int(self.target.get())
        try:
            prof = gb.recommend(game, target)
        except SystemExit as e:
            self.ui(self.put, self.rec_t, f"{e}\n", None, True); return
        self.profile = prof
        plan = ad.make_plan(game, prof)
        changes, skipped, err = ad.preview(plan)
        out = fmt_prof(prof) + "\n\n── DOSYA İŞLEMİ ──\n"
        if not plan["writes"]:
            out += "Bu oyunda dosya değiştirmiyorum.\n"
        elif err:
            out += err + "\n"
        else:
            out += f"Dosya: {plan['path']}\n\nDeğişecekler:\n" + "".join(f"  {k}: {a} -> {b}\n" for k, a, b in changes)
            if not changes:
                out += "  (hepsi zaten uygun)\n"
            if skipped:
                out += "\nDosyada bulunamadığı için atlanan: " + ", ".join(skipped) + "\n"
        for n in plan["notes"]:
            out += f"\n⚠ {n}"
        self.ui(self.put, self.rec_t, out + "\n", None, True)
        if plan["writes"] and not err and changes:
            self.ui(self.confirm_apply, plan, len(changes))

    def confirm_apply(self, plan, n):
        if messagebox.askyesno("Onay", f"{n} ayar dosyaya yazılacak. Orijinal yedeklenir, 'Geri Al' ile dönebilirsin.\nOyun kapalı mı? Devam edilsin mi?"):
            self.bg(self.run_apply, plan)

    def run_apply(self, plan):
        self.ui(self.put, self.rec_t, "\n► " + ad.apply(plan) + "\n")

    def do_restore(self):
        msg = ad.restore(self.game.get().strip())
        self.ui(self.put, self.rec_t, "\n► " + msg + "\n")

    # ---------- Canlı monitör ----------
    def tab_mon(self):
        f = self.frame("FPS Kontrol")
        row = ttk.Frame(f); row.pack(fill="x")
        self.csv = tk.StringVar()
        ttk.Button(row, text="CSV Seç (PresentMon)", command=lambda: self.csv.set(filedialog.askopenfilename(filetypes=[("CSV", "*.csv")]) or self.csv.get())).pack(side="left")
        ttk.Label(row, textvariable=self.csv).pack(side="left", padx=10)
        row2 = ttk.Frame(f); row2.pack(fill="x", pady=8)
        self.follow = tk.BooleanVar()
        ttk.Button(row2, text="Analiz Et", command=lambda: self.bg(self.do_mon)).pack(side="left")
        ttk.Checkbutton(row2, text="Her 10 sn otomatik yenile", variable=self.follow, command=self.loop_mon).pack(side="left", padx=14)
        self.mon_t = self.textbox(f); self.mon_t.pack(fill="both", expand=True)

    def do_mon(self):
        if not self.csv.get():
            self.ui(self.put, self.mon_t, "Önce CSV seç.\n"); return
        target = self.profile["target_fps"] if self.profile else 60
        out = capture(gb.monitor, self.csv.get(), target, False)
        self.ui(self.put, self.mon_t, out)

    def loop_mon(self):
        if self.follow.get():
            self.bg(self.do_mon)
            self.root.after(10000, self.loop_mon)

    # ---------- Dokular ----------
    def tab_tex(self):
        f = self.frame("Dokular")
        row = ttk.Frame(f); row.pack(fill="x")
        self.folder = tk.StringVar()
        ttk.Button(row, text="Klasör Seç", command=lambda: self.folder.set(filedialog.askdirectory() or self.folder.get())).pack(side="left")
        ttk.Label(row, textvariable=self.folder).pack(side="left", padx=10)
        row2 = ttk.Frame(f); row2.pack(fill="x", pady=8)
        ttk.Label(row2, text="En büyük kenar (px):").pack(side="left")
        self.maxpx = ttk.Combobox(row2, values=[1024, 2048, 4096], width=6); self.maxpx.set(2048); self.maxpx.pack(side="left", padx=8)
        ttk.Button(row2, text="Önizle (güvenli)", command=lambda: self.bg(self.do_tex, False)).pack(side="left", padx=4)
        ttk.Button(row2, text="Uygula + Yedekle", command=self.apply_tex).pack(side="left", padx=4)
        self.tex_t = self.textbox(f); self.tex_t.pack(fill="both", expand=True)
        self.put(self.tex_t, "Sadece açık PNG/JPG/TGA/BMP dokularını işler. Online oyun klasörlerinde kullanma.\n")

    def apply_tex(self):
        if messagebox.askyesno("Onay", "Dokular küçültülecek (orijinaller yedeklenir). Online oyun klasörü değil, emin misin?"):
            self.bg(self.do_tex, True)

    def do_tex(self, apply):
        if not self.folder.get():
            self.ui(self.put, self.tex_t, "Önce klasör seç.\n"); return
        self.ui(self.put, self.tex_t, "Çalışıyor…\n", None, True)
        out = capture(gb.textures, self.folder.get(), int(self.maxpx.get()), apply)
        self.ui(self.put, self.tex_t, out, None, True)

    # ---------- AI Asistan ----------
    def tab_ai(self):
        f = self.frame("AI Asistan")
        row = ttk.Frame(f); row.pack(fill="x")
        self.kind = ttk.Combobox(row, values=["Ollama", "OpenAI uyumlu"], width=14, state="readonly"); self.kind.set("Ollama"); self.kind.pack(side="left")
        self.url = tk.Entry(row, width=26, bg="#0e1015", fg=FG, insertbackground=FG, relief="flat"); self.url.insert(0, llm.url); self.url.pack(side="left", padx=6)
        self.model = ttk.Combobox(row, values=[llm.model], width=22); self.model.set(llm.model); self.model.pack(side="left")
        ttk.Button(row, text="Bağlan", command=lambda: self.bg(self.connect_ai, True)).pack(side="left", padx=6)
        self.chat_t = self.textbox(f); self.chat_t.pack(fill="both", expand=True, pady=8)
        row2 = ttk.Frame(f); row2.pack(fill="x")
        self.inp = tk.Entry(row2, bg="#0e1015", fg=FG, insertbackground=FG, relief="flat", font=("Segoe UI", 11))
        self.inp.pack(side="left", fill="x", expand=True, ipady=6)
        self.inp.bind("<Return>", lambda e: self.send())
        ttk.Button(row2, text="Gönder", command=self.send).pack(side="left", padx=6)
        self.put(self.chat_t, "Donanımın ve son önerin hakkında soru sorabilirsin. (1.5B model küçüktür; sayısal kararları kural motoru verir.)\n\n")

    def connect_ai(self, from_ui=False):
        if from_ui:
            llm.kind = "Ollama" if self.kind.get() == "Ollama" else "OpenAI"
            if llm.kind == "OpenAI" and "11434" in self.url.get():
                self.ui(self.url.delete, 0, "end"); self.ui(self.url.insert, 0, "http://localhost:1234")
            llm.url, llm.model = self.url.get(), self.model.get()
        try:
            names = llm.models()
            low = lambda n: n.lower()
            pick = (next((n for n in names if "qwen2.5" in low(n) and "1.5" in n and "coder" not in low(n)), None)
                    or next((n for n in names if "qwen" in low(n) and "coder" not in low(n)), None)
                    or next((n for n in names if "qwen" in low(n)), names[0] if names else llm.model))
            if not from_ui or llm.model not in names:
                llm.model = pick
            self.ui(self.model.config, values=names); self.ui(self.model.set, llm.model)
            self.ui(self.status.config, text=f"● AI bağlı: {llm.model}", fg="#7ee0a0")
        except Exception:
            self.ui(self.status.config, text="● AI bağlı değil (Ollama çalışıyor mu? 'ollama serve')", fg="#ff7b7b")

    def send(self):
        q = self.inp.get().strip()
        if not q:
            return
        self.inp.delete(0, "end")
        self.put(self.chat_t, "Sen: ", "me"); self.put(self.chat_t, q + "\n")
        self.history.append({"role": "user", "content": q})
        self.bg(self.reply)

    def reply(self):
        sysmsg = ("Sen GameBoost'un oyun performans asistanısın. Türkçe, kısa ve net cevap ver. "
                  "Bilmediğin şeyi uydurma. Kullanıcının donanımı: " + json.dumps(self.hw, ensure_ascii=False) +
                  " Son öneri: " + json.dumps(self.profile, ensure_ascii=False))
        self.ui(self.put, self.chat_t, "AI: ", "me")
        text = ""
        try:
            for tok in llm.stream([{"role": "system", "content": sysmsg}] + self.history[-8:]):
                text += tok; self.ui(self.put, self.chat_t, tok, "ai")
        except Exception as e:
            self.ui(self.put, self.chat_t, f"(Bağlantı hatası: {e})", "ai")
        self.history.append({"role": "assistant", "content": text})
        self.ui(self.put, self.chat_t, "\n\n")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
