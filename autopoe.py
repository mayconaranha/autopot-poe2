#!/usr/bin/env python3
"""
AutoPoE — Path of Exile 2
Lê a vida (e mana) pelo OCR dos números do globo e aperta o flask quando cai
abaixo do limite. Hotkey: F6 para ligar/desligar.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime

import keyboard as kb
import pydirectinput

import detect

# pydirectinput pausa 0.1s depois de cada tecla por padrão, o que limitaria os
# intervalos curtos (ex.: 0.1s). Reduzimos pra deixar as teclas rápidas responsivas.
pydirectinput.PAUSE = 0.02

# ─── Constantes ──────────────────────────────────────────────────────────────

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
PID_FILE    = os.path.join(BASE_DIR, "autopoe.pid")

HP_THRESHOLD  = 50
POT_COOLDOWN  = 1.0      # segundos entre poções do mesmo tipo
SCAN_INTERVAL = 0.1      # ritmo do loop
OCR_INTERVAL  = 0.15     # não vale a pena rodar o OCR mais rápido que isso
HOTKEY        = "f6"

# ─── Paleta de cores ─────────────────────────────────────────────────────────

C_BG     = "#1e2535"
C_CARD   = "#28334d"
C_BORDER = "#3e4f6a"
C_FG     = "#dce8f5"
C_DIM    = "#8899b8"
C_GREEN  = "#39d353"
C_RED    = "#f85149"
C_ORANGE = "#f0883e"
C_BLUE   = "#58a6ff"
C_YELLOW = "#d29922"
C_LOG    = "#18202e"


# ─── Calibração ──────────────────────────────────────────────────────────────

class Calibrator:
    """Overlay fullscreen para o usuário marcar uma região na tela."""

    def __init__(self, parent, on_done, label="Vida"):
        self.on_done = on_done
        self.start_x = self.start_y = 0
        self.rect_id = None

        self.win = tk.Toplevel(parent)
        self.win.attributes("-fullscreen", True)
        self.win.attributes("-alpha", 0.35)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="black")
        self.win.title("Calibrar")

        self.canvas = tk.Canvas(self.win, bg="black", cursor="crosshair", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.win.update_idletasks()
        cx = self.win.winfo_screenwidth() // 2
        self.canvas.create_text(
            cx, 40,
            text=f"Arraste por cima dos NÚMEROS de {label}  |  ESC para cancelar",
            fill="white", font=("Arial", 14)
        )

        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.win.bind("<Escape>", lambda _: self.win.destroy())
        self.win.grab_set()
        parent.wait_window(self.win)

    def _press(self, e):
        self.start_x, self.start_y = e.x, e.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)

    def _drag(self, e):
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, e.x, e.y,
            outline="#ff4444", width=2, fill="#ff4444", stipple="gray25"
        )

    def _release(self, e):
        x1, x2 = sorted([self.start_x, e.x])
        y1, y2 = sorted([self.start_y, e.y])
        self.win.destroy()
        if x2 - x1 > 5 and y2 - y1 > 2:
            self.on_done({"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1})


# ─── Config ──────────────────────────────────────────────────────────────────

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(data: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ─── App Principal ───────────────────────────────────────────────────────────

class App:
    def __init__(self):
        self.config = load_config()
        self.region: dict | None      = self.config.get("life_region")
        self.mana_region: dict | None = self.config.get("mana_region")
        self.active        = False
        self.current_hp    = 0.0
        self.current_mana  = 0.0
        self.last_pot      = 0.0
        self.last_mana_pot = 0.0
        self._hp_fail      = 0
        self._mana_fail    = 0
        self._running      = True
        self._thread: threading.Thread | None = None
        self._log_queue: queue.Queue = queue.Queue()

        self._hp_threshold   = self.config.get("hp_threshold", HP_THRESHOLD)
        self._mana_threshold = self.config.get("mana_threshold", 30)
        self._life_key       = self.config.get("life_key", "1")
        self._mana_key       = self.config.get("mana_key", "2")
        self._hp_enabled     = self.config.get("hp_enabled", True)
        self._mana_enabled   = self.config.get("mana_enabled", True)

        self._last_ocr = 0.0

        # Teclas automáticas: lista de {key, interval}
        self._keypresses: list[dict] = list(self.config.get("keypresses", []))
        self._keypress_last: dict[int, float] = {}
        self._keypress_widgets: list[dict] = []

        self._build_ui()
        self._register_hotkey()
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._tick_ui()

        self.root.focus_force()
        self.root.bind_all("<Button-1>", self._unfocus_entry, add="+")
        self.root.mainloop()

    # ── Interface ────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title("AutoPoE — PoE2")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=C_BG)

        def sep():
            tk.Frame(self.root, bg=C_BORDER, height=1).pack(fill="x")

        def card(pady=(6, 0), padx=14):
            f = tk.Frame(self.root, bg=C_BG, padx=padx, pady=8)
            f.pack(fill="x", pady=pady)
            return f

        def section_label(parent, text):
            tk.Label(parent, text=text, bg=C_BG, fg=C_DIM,
                     font=("Consolas", 9, "bold")).pack(anchor="w", pady=(0, 5))

        def cfg_row(parent, label):
            row = tk.Frame(parent, bg=C_CARD, padx=10, pady=7)
            row.pack(fill="x", pady=(0, 3))
            tk.Label(row, text=label, bg=C_CARD, fg=C_FG,
                     font=("Consolas", 9), anchor="w", width=19).pack(side="left")
            ctrl = tk.Frame(row, bg=C_CARD)
            ctrl.pack(side="left")
            return ctrl

        def scale(parent, lo, hi, val, cb, color, res=1, length=110):
            s = tk.Scale(parent, from_=lo, to=hi, orient="horizontal", length=length,
                         resolution=res, showvalue=False, command=cb,
                         bg=C_CARD, fg=C_FG, troughcolor=C_BG,
                         activebackground=color, highlightthickness=0,
                         bd=0, sliderrelief="flat", sliderlength=14)
            s.set(val)
            return s

        def val_label(parent, text, color):
            return tk.Label(parent, text=text, bg=C_CARD, fg=color,
                            font=("Consolas", 10), width=5, anchor="w")

        def key_entry(parent, value, on_change):
            e = tk.Entry(parent, width=5, font=("Consolas", 10), justify="center",
                         bg=C_BG, fg=C_FG, insertbackground=C_FG,
                         relief="flat", highlightthickness=1,
                         highlightbackground=C_BORDER, highlightcolor=C_GREEN)
            e.insert(0, value)
            e.bind("<KeyRelease>", lambda _e: on_change(e.get().strip().lower()))
            return e

        # ── Header ───────────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=C_CARD, padx=14, pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="AUTOPOE", bg=C_CARD, fg=C_GREEN,
                 font=("Consolas", 14, "bold")).pack(side="left")
        tk.Label(hdr, text=" // Path of Exile 2", bg=C_CARD, fg=C_DIM,
                 font=("Consolas", 10)).pack(side="left")
        tk.Label(hdr, text=f"{HOTKEY.upper()} = on/off", bg=C_CARD, fg=C_DIM,
                 font=("Consolas", 9)).pack(side="right")

        # ── Status bar ───────────────────────────────────────────────────────
        sep()
        sf = card(pady=(0, 0))
        self.lbl_status = tk.Label(sf, text="● INATIVO", bg=C_BG, fg=C_DIM,
                                   font=("Consolas", 10, "bold"))
        self.lbl_status.pack(side="left")

        # ── HP + Mana ────────────────────────────────────────────────────────
        sep()
        hm = tk.Frame(self.root, bg=C_BG, padx=14, pady=10)
        hm.pack(fill="x")

        def power_btn(parent, on, cmd, on_color):
            return tk.Button(parent, text="ON" if on else "OFF",
                             bg=on_color if on else C_BORDER, fg=C_BG if on else C_DIM,
                             font=("Consolas", 8, "bold"), relief="flat", cursor="hand2",
                             padx=8, pady=1, bd=0, command=cmd)

        hp_card = tk.Frame(hm, bg=C_CARD, padx=12, pady=10)
        hp_card.pack(side="left", expand=True, fill="both", padx=(0, 5))
        hp_head = tk.Frame(hp_card, bg=C_CARD)
        hp_head.pack(fill="x")
        tk.Label(hp_head, text="VIDA", bg=C_CARD, fg=C_DIM,
                 font=("Consolas", 9, "bold")).pack(side="left")
        self.btn_hp_power = power_btn(hp_head, self._hp_enabled, self._toggle_hp, C_GREEN)
        self.btn_hp_power.pack(side="right")
        self.lbl_hp = tk.Label(hp_card, text="—", bg=C_CARD, fg=C_GREEN,
                               font=("Consolas", 22, "bold"))
        self.lbl_hp.pack(anchor="w")

        mp_card = tk.Frame(hm, bg=C_CARD, padx=12, pady=10)
        mp_card.pack(side="left", expand=True, fill="both", padx=(5, 0))
        mp_head = tk.Frame(mp_card, bg=C_CARD)
        mp_head.pack(fill="x")
        tk.Label(mp_head, text="MANA", bg=C_CARD, fg=C_DIM,
                 font=("Consolas", 9, "bold")).pack(side="left")
        self.btn_mana_power = power_btn(mp_head, self._mana_enabled, self._toggle_mana, C_BLUE)
        self.btn_mana_power.pack(side="right")
        self.lbl_mana = tk.Label(mp_card, text="—", bg=C_CARD, fg=C_BLUE,
                                 font=("Consolas", 22, "bold"))
        self.lbl_mana.pack(anchor="w")

        # ── Configurações ────────────────────────────────────────────────────
        sep()
        cfg = card()
        section_label(cfg, "CONFIGURAÇÕES")

        hp_ctrl = cfg_row(cfg, "Vida pot abaixo de:")
        self.sl_hp = scale(hp_ctrl, 10, 90, self._hp_threshold, self._on_hp_change, C_RED)
        self.sl_hp.pack(side="left")
        self.lbl_hp_val = val_label(hp_ctrl, f"{self._hp_threshold}%", C_RED)
        self.lbl_hp_val.pack(side="left", padx=(4, 0))

        mp_ctrl = cfg_row(cfg, "Mana pot abaixo de:")
        self.sl_mana = scale(mp_ctrl, 10, 90, self._mana_threshold, self._on_mana_change, C_BLUE)
        self.sl_mana.pack(side="left")
        self.lbl_mana_val = val_label(mp_ctrl, f"{self._mana_threshold}%", C_BLUE)
        self.lbl_mana_val.pack(side="left", padx=(4, 0))

        # Teclas dos flasks
        lk_ctrl = cfg_row(cfg, "Tecla flask vida:")
        self.ent_life_key = key_entry(lk_ctrl, self._life_key, self._on_life_key_change)
        self.ent_life_key.pack(side="left")

        mk_ctrl = cfg_row(cfg, "Tecla flask mana:")
        self.ent_mana_key = key_entry(mk_ctrl, self._mana_key, self._on_mana_key_change)
        self.ent_mana_key.pack(side="left")

        self.lbl_region = tk.Label(cfg, text=self._fmt_region(), bg=C_BG, fg=C_DIM,
                                   font=("Consolas", 8), justify="left")
        self.lbl_region.pack(anchor="w", pady=(6, 0))

        # ── Teclas Automáticas ────────────────────────────────────────────────
        sep()
        kp_sec = card()
        section_label(kp_sec, "TECLAS AUTOMÁTICAS")
        self._kp_container = tk.Frame(kp_sec, bg=C_BG)
        self._kp_container.pack(fill="x")
        self._rebuild_keypress_rows()
        tk.Button(kp_sec, text="+ Adicionar Tecla", bg=C_CARD, fg=C_GREEN,
                  font=("Consolas", 9, "bold"), relief="flat", cursor="hand2",
                  padx=10, pady=5, bd=0, command=self._add_keypress).pack(anchor="w", pady=(6, 0))

        # ── Calibração ───────────────────────────────────────────────────────
        sep()
        cal = card()
        section_label(cal, "CALIBRAÇÃO")
        btn_s = dict(relief="flat", cursor="hand2", font=("Consolas", 9, "bold"),
                     padx=10, pady=6, bd=0)
        bar_row = tk.Frame(cal, bg=C_BG)
        bar_row.pack(fill="x")
        tk.Button(bar_row, text="Números Vida", bg=C_CARD, fg=C_RED,
                  command=self._calibrate, **btn_s).pack(side="left", padx=(0, 5))
        tk.Button(bar_row, text="Números Mana", bg=C_CARD, fg=C_BLUE,
                  command=self._calibrate_mana, **btn_s).pack(side="left", padx=(0, 5))
        tk.Button(bar_row, text="Testar Leitura", bg=C_CARD, fg=C_YELLOW,
                  command=self._test_read, **btn_s).pack(side="right")

        # ── Botão principal ──────────────────────────────────────────────────
        sep()
        tf = tk.Frame(self.root, bg=C_BG, padx=14, pady=12)
        tf.pack(fill="x")
        self.btn_toggle = tk.Button(tf, text="LIGAR", bg=C_GREEN, fg=C_BG,
                                    font=("Consolas", 12, "bold"), relief="flat",
                                    cursor="hand2", pady=9, command=self._toggle)
        self.btn_toggle.pack(fill="x")

        # ── Log ──────────────────────────────────────────────────────────────
        sep()
        self.log = tk.Text(self.root, height=6, state="disabled",
                           font=("Consolas", 9), bg=C_LOG, fg=C_BLUE,
                           relief="flat", padx=12, pady=8,
                           insertbackground=C_FG, wrap="word")
        self.log.pack(fill="x")

    def _fmt_region(self) -> str:
        def fmt(r, nome):
            if r:
                return f"{nome}: x={r['left']} y={r['top']}  {r['width']}×{r['height']}px"
            return f"{nome}: não calibrado"
        return fmt(self.region, "Vida") + "\n" + fmt(self.mana_region, "Mana")

    def _tick_ui(self):
        if self.active:
            self.lbl_status.config(text="● ATIVO", fg=C_GREEN)
            self.btn_toggle.config(text="PAUSAR", bg=C_RED, fg=C_BG)
            if not self._hp_enabled:
                self.lbl_hp.config(text="OFF", fg=C_DIM)
            elif self.region:
                hp = self.current_hp
                color = C_RED if hp < self._hp_threshold else C_GREEN
                self.lbl_hp.config(text=f"{hp:.0f}%", fg=color)
            if not self._mana_enabled:
                self.lbl_mana.config(text="OFF", fg=C_DIM)
            elif self.mana_region:
                mp = self.current_mana
                color = C_RED if mp < self._mana_threshold else C_BLUE
                self.lbl_mana.config(text=f"{mp:.0f}%", fg=color)
        else:
            self.lbl_status.config(text="● INATIVO", fg=C_DIM)
            self.btn_toggle.config(text="LIGAR", bg=C_GREEN, fg=C_BG)

        try:
            while True:
                self._write_log(self._log_queue.get_nowait())
        except queue.Empty:
            pass

        self.root.after(200, self._tick_ui)

    def _unfocus_entry(self, event):
        if not isinstance(event.widget, tk.Entry):
            self.root.focus_set()

    def _write_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.config(state="normal")
        self.log.insert("end", f"{ts}  {msg}\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _log(self, msg: str):
        self._log_queue.put(msg)

    # ── Loop de detecção ─────────────────────────────────────────────────────

    def _start_loop(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while self._running:
            if self.active:
                now = time.time()
                if now - self._last_ocr >= OCR_INTERVAL:
                    self._last_ocr = now
                    if self._hp_enabled and self.region:
                        self._check_life(now)
                    if self._mana_enabled and self.mana_region:
                        self._check_mana(now)
                self._auto_keys(now)
            time.sleep(SCAN_INTERVAL)

    def _check_life(self, now: float):
        pct = detect.read_percent(self.region)
        if pct is None:
            self._hp_fail += 1
            if self._hp_fail == 5:
                self._log("OCR não está lendo a VIDA — confira a calibração.")
            return
        self._hp_fail = 0
        self.current_hp = pct
        if pct < self._hp_threshold and now - self.last_pot >= POT_COOLDOWN:
            key = self._life_key.strip()
            if key:
                pydirectinput.press(key)
                self.last_pot = now
                self._log(f"Flask de vida ('{key}')  —  Vida: {pct:.0f}%")

    def _check_mana(self, now: float):
        pct = detect.read_percent(self.mana_region)
        if pct is None:
            self._mana_fail += 1
            if self._mana_fail == 5:
                self._log("OCR não está lendo a MANA — confira a calibração.")
            return
        self._mana_fail = 0
        self.current_mana = pct
        if pct < self._mana_threshold and now - self.last_mana_pot >= POT_COOLDOWN:
            key = self._mana_key.strip()
            if key:
                pydirectinput.press(key)
                self.last_mana_pot = now
                self._log(f"Flask de mana ('{key}')  —  Mana: {pct:.0f}%")

    def _auto_keys(self, now: float):
        for idx, kp in enumerate(self._keypresses):
            key = kp.get("key", "").strip()
            interval = kp.get("interval", 1.0)
            if not key or interval <= 0:
                continue
            if now - self._keypress_last.get(idx, 0.0) >= interval:
                pydirectinput.press(key)
                self._keypress_last[idx] = now
                self._log(f"Tecla '{key}' pressionada (a cada {interval:.1f}s)")

    # ── Ações ────────────────────────────────────────────────────────────────

    def _toggle(self):
        self.active = not self.active
        if self.active:
            hp_ready   = self._hp_enabled and self.region
            mana_ready = self._mana_enabled and self.mana_region
            if not (hp_ready or mana_ready):
                self._log("Nada pra fazer — habilite e calibre Vida e/ou Mana primeiro.")
                self.active = False
                return
            self._start_loop()
            self._log("Ativado")
        else:
            self._log("Pausado")

    def _toggle_hp(self):
        self._hp_enabled = not self._hp_enabled
        self.config["hp_enabled"] = self._hp_enabled
        save_config(self.config)
        on = self._hp_enabled
        self.btn_hp_power.config(text="ON" if on else "OFF",
                                 bg=C_GREEN if on else C_BORDER,
                                 fg=C_BG if on else C_DIM)
        self._log(f"Pot de vida {'ligada' if on else 'desligada'}.")

    def _toggle_mana(self):
        self._mana_enabled = not self._mana_enabled
        self.config["mana_enabled"] = self._mana_enabled
        save_config(self.config)
        on = self._mana_enabled
        self.btn_mana_power.config(text="ON" if on else "OFF",
                                   bg=C_BLUE if on else C_BORDER,
                                   fg=C_BG if on else C_DIM)
        self._log(f"Pot de mana {'ligada' if on else 'desligada'}.")

    def _on_hp_change(self, val):
        self._hp_threshold = int(float(val))
        self.lbl_hp_val.config(text=f"{self._hp_threshold}%")
        self.config["hp_threshold"] = self._hp_threshold
        save_config(self.config)

    def _on_mana_change(self, val):
        self._mana_threshold = int(float(val))
        self.lbl_mana_val.config(text=f"{self._mana_threshold}%")
        self.config["mana_threshold"] = self._mana_threshold
        save_config(self.config)

    def _on_life_key_change(self, key: str):
        self._life_key = key
        self.config["life_key"] = key
        save_config(self.config)

    def _on_mana_key_change(self, key: str):
        self._mana_key = key
        self.config["mana_key"] = key
        save_config(self.config)

    # ── Teclas Automáticas ────────────────────────────────────────────────────

    def _rebuild_keypress_rows(self):
        for w in self._kp_container.winfo_children():
            w.destroy()
        self._keypress_widgets.clear()
        for idx, kp in enumerate(self._keypresses):
            self._build_keypress_row(idx, kp)

    def _build_keypress_row(self, idx: int, kp: dict):
        row = tk.Frame(self._kp_container, bg=C_CARD, padx=10, pady=6)
        row.pack(fill="x", pady=(0, 3))

        tk.Label(row, text="Tecla:", bg=C_CARD, fg=C_DIM,
                 font=("Consolas", 9)).pack(side="left")
        entry = tk.Entry(row, width=5, font=("Consolas", 10), justify="center",
                         bg=C_BG, fg=C_FG, insertbackground=C_FG,
                         relief="flat", highlightthickness=1,
                         highlightbackground=C_BORDER, highlightcolor=C_GREEN)
        entry.insert(0, kp.get("key", ""))
        entry.pack(side="left", padx=(4, 10))
        entry.bind("<KeyRelease>", lambda _e, i=idx: self._on_kp_key_change(i))

        tk.Label(row, text="Intervalo:", bg=C_CARD, fg=C_DIM,
                 font=("Consolas", 9)).pack(side="left")
        interval_val = kp.get("interval", 1.0)
        sl = tk.Scale(row, from_=0, to=60, orient="horizontal", length=180,
                      resolution=0.1, showvalue=False,
                      command=lambda v, i=idx: self._on_kp_interval_change(i, v),
                      bg=C_CARD, fg=C_FG, troughcolor=C_BG,
                      activebackground=C_ORANGE, highlightthickness=0,
                      bd=0, sliderrelief="flat", sliderlength=14)
        sl.set(interval_val)
        sl.pack(side="left", padx=(4, 4))
        lbl = tk.Label(row, text=f"{interval_val:.1f}s", bg=C_CARD, fg=C_ORANGE,
                       font=("Consolas", 10), width=5, anchor="w")
        lbl.pack(side="left")

        tk.Button(row, text="✕", bg=C_RED, fg=C_BG, font=("Consolas", 9, "bold"),
                  relief="flat", cursor="hand2", padx=6, pady=2, bd=0,
                  command=lambda i=idx: self._remove_keypress(i)).pack(side="right")

        self._keypress_widgets.append({"row": row, "entry": entry, "scale": sl, "label": lbl})

    def _add_keypress(self):
        self._keypresses.append({"key": "", "interval": 1.0})
        self._save_keypresses()
        self._rebuild_keypress_rows()

    def _remove_keypress(self, idx: int):
        if 0 <= idx < len(self._keypresses):
            self._keypresses.pop(idx)
            self._keypress_last.pop(idx, None)
            new_last = {}
            for old_idx, ts in self._keypress_last.items():
                new_idx = old_idx if old_idx < idx else old_idx - 1
                if new_idx >= 0:
                    new_last[new_idx] = ts
            self._keypress_last = new_last
            self._save_keypresses()
            self._rebuild_keypress_rows()

    def _on_kp_key_change(self, idx: int):
        if idx < len(self._keypress_widgets):
            key = self._keypress_widgets[idx]["entry"].get().strip().lower()
            self._keypresses[idx]["key"] = key
            self._save_keypresses()

    def _on_kp_interval_change(self, idx: int, val):
        interval = float(val)
        self._keypresses[idx]["interval"] = interval
        if idx < len(self._keypress_widgets):
            self._keypress_widgets[idx]["label"].config(text=f"{interval:.1f}s")
        self._save_keypresses()

    def _save_keypresses(self):
        self.config["keypresses"] = self._keypresses
        save_config(self.config)

    # ── Calibração ─────────────────────────────────────────────────────────────

    def _calibrate(self):
        Calibrator(self.root, self._on_calibrated, label="Vida")

    def _on_calibrated(self, region: dict):
        self.region = region
        self.config["life_region"] = region
        save_config(self.config)
        self.lbl_region.config(text=self._fmt_region())
        self._log("Números de vida calibrados.")
        self._test_read()

    def _calibrate_mana(self):
        Calibrator(self.root, self._on_mana_calibrated, label="Mana")

    def _on_mana_calibrated(self, region: dict):
        self.mana_region = region
        self.config["mana_region"] = region
        save_config(self.config)
        self.lbl_region.config(text=self._fmt_region())
        self._log("Números de mana calibrados.")
        self._test_read()

    def _test_read(self):
        """Lê as regiões agora e mostra no log — pra conferir a calibração."""
        def work():
            if self.region:
                txt = detect.read_text(self.region)
                pct = detect.read_percent(self.region)
                pct_s = f"{pct:.0f}%" if pct is not None else "falhou"
                self._log(f"Vida → leu '{txt}'  ({pct_s})")
            if self.mana_region:
                txt = detect.read_text(self.mana_region)
                pct = detect.read_percent(self.mana_region)
                pct_s = f"{pct:.0f}%" if pct is not None else "falhou"
                self._log(f"Mana → leu '{txt}'  ({pct_s})")
        threading.Thread(target=work, daemon=True).start()

    def _register_hotkey(self):
        kb.add_hotkey(HOTKEY, lambda: self.root.after(0, self._toggle))

    def _close(self):
        self._running = False
        kb.unhook_all()
        self.root.destroy()


# ─── Entry Point ─────────────────────────────────────────────────────────────

def _kill_existing():
    if not os.path.exists(PID_FILE):
        return
    try:
        with open(PID_FILE) as f:
            old_pid = int(f.read().strip())
        subprocess.run(["taskkill", "/F", "/PID", str(old_pid)], capture_output=True)
        time.sleep(0.6)
    except Exception:
        pass
    try:
        os.remove(PID_FILE)
    except Exception:
        pass


def _selftest():
    """Confere que o OCR funciona neste build (útil pra validar o .exe)."""
    import numpy as np
    import cv2
    img = np.full((40, 160, 3), 30, dtype=np.uint8)
    cv2.putText(img, "1.317/1.513", (4, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (235, 235, 235), 2, cv2.LINE_AA)
    detect._grab = lambda region: img
    region = {"left": 0, "top": 0, "width": 160, "height": 40}
    txt = detect.read_text(region)
    pct = detect.read_percent(region)
    with open(os.path.join(BASE_DIR, "selftest.log"), "w") as f:
        f.write(f"texto={txt!r}\npercent={pct}\nok={pct is not None}\n")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)

    _kill_existing()

    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    try:
        kb.unhook_all()
    except Exception:
        pass

    try:
        App()
    except Exception:
        import traceback
        log_path = os.path.join(BASE_DIR, "error.log")
        with open(log_path, "w") as f:
            traceback.print_exc(file=f)
        raise
    finally:
        try:
            os.remove(PID_FILE)
        except Exception:
            pass
