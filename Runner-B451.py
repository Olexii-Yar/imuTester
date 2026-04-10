import tkinter as tk
from tkinter import ttk, font as tkfont
import serial
import serial.tools.list_ports
import threading
from datetime import datetime
import time
import gc

### команда для запаковки в exe =
### python -m nuitka --onefile --enable-plugin=tk-inter --windows-console-mode=disable --include-package=serial --include-package=serial.tools --include-package=serial.tools.list_ports --include-package=serial.tools.list_ports_common --include-package=serial.tools.list_ports_windows --windows-icon-from-ico=hazard.ico --output-filename=Reader_5-3.exe runner22.py

# ─────────────────────────────────────────────────────────────────────────────
# ЕТАЛОННА КОНФІГУРАЦІЯ — замініть на свій пресет
# ─────────────────────────────────────────────────────────────────────────────
REFERENCE_CONFIG = """dump all

# version
# Betaflight / STM32F405 (S405) 4.5.1 # config rev: e0af134

# start the command batch
batch start

***
JUST TEST DUMP IN IT
FOR EXAMPLE OF CONTENT
///

# led
led 0 0,0::C:0
led 1 0,0::C:0
led 2 0,0::C:0
led 3 0,0::C:0
led 4 0,0::C:0

# rxrange
rxrange 0 1000 2000
rxrange 1 1000 2000

set gyro_1_spibus = 1

set horizon_delay_ms = 500
set abs_control_gain = 0

set dyn_idle_start_increase = 50
set level_race_mode = OFF

rateprofile 0

# save configuration
save
# 
""".strip()


# ─────────────────────────────────────────────────────────────────────────────
# ПАЛІТРА КОЛЬОРІВ
# ─────────────────────────────────────────────────────────────────────────────
C = {
    "bg":           "#2c3550",
    "bg2":          "#36415A",
    "bg3":          "#373a41",
    "panel":        "#12151f",
    "border":       "#2a3045",
    "accent":       "#3d8ef0",
    "accent_dim":   "#1e4a8c",
    "green":        "#2ecc71",
    "red":          "#e74c3c",
    "yellow":       "#f0a500",
    "text":         "#cdd6f4",
    "text_dim":     "#6272a4",
    "text_bright":  "#ffffff",
    # поля порівняння (світла тема)
    "editor_bg":    "#f8f9fc",
    "editor_fg":    "#1a1d2e",
    "line_match":   "#d5f5e3",
    "line_match_fg":"#1a6b35",
    "line_diff":    "#ffeaea",
    "line_diff_fg": "#c0392b",
    "line_added":   "#fff9db",
    "line_added_fg":"#7d6608",
    "gutter_bg":    "#e8ecf5",
    "gutter_fg":    "#8899bb",
}


class BetaflightDiffTool:
    def __init__(self, root):
        self.root = root
        self.root.title("TechEx Checker-Beta Tool")
        self.root.configure(bg=C["bg"])
        self.root.geometry("960x640")
        self.root.minsize(960, 640)

        self._scroll_sync_active = False
        self._highlight_job = None
        self.downloaded_text = ""

        self._build_fonts()
        self._build_layout()
        self._load_reference()

    # ── FONTS ──────────────────────────────────────────────────────────────
    def _build_fonts(self):
        self.f_mono   = tkfont.Font(family="Consolas",      size=9)
        self.f_mono_b = tkfont.Font(family="Consolas",      size=9,  weight="bold")
        self.f_ui     = tkfont.Font(family="Segoe UI",       size=9)
        self.f_ui_b   = tkfont.Font(family="Segoe UI",       size=9,  weight="bold")
        self.f_title  = tkfont.Font(family="Segoe UI",       size=10, weight="bold")
        self.f_log    = tkfont.Font(family="Consolas",       size=8)
        self.f_label  = tkfont.Font(family="Segoe UI",       size=8,  weight="bold")

    # ── LAYOUT ─────────────────────────────────────────────────────────────
    def _build_layout(self):
        self.root.grid_rowconfigure(0, weight=0)  # header
        self.root.grid_rowconfigure(1, weight=0)  # logger
        self.root.grid_rowconfigure(2, weight=1)  # comparison
        self.root.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_logger()
        self._build_comparison()
        self._build_statusbar()

    # ── HEADER ─────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self.root, bg=C["bg2"], pady=0)
        hdr.grid(row=0, column=0, sticky="ew")

        # left: logo + port controls
        left = tk.Frame(hdr, bg=C["bg2"])
        left.pack(side=tk.LEFT, padx=12, pady=8)

        logo = tk.Label(left, text="Виберіть порт:", bg=C["bg2"],
                        fg=C["accent"], font=self.f_title)
        logo.pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(left, text="⚡", bg=C["bg2"],
                 fg=C["accent"], font=self.f_label).pack(side=tk.LEFT, padx=(0, 4))

        self.port_combo = ttk.Combobox(left, values=self._get_ports(),
                                       width=32, font=self.f_ui, state="readonly")
        self.port_combo.pack(side=tk.LEFT, padx=(0, 6))
        if self.port_combo['values']:
            self.port_combo.current(0)

        self.refresh_btn = tk.Button(
            left, text="⏪ refresh", width=11, font=self.f_ui_b,
            bg=C["bg3"], fg=C["text"], relief=tk.FLAT,
            activebackground=C["border"], activeforeground=C["text_bright"],
            cursor="hand2", command=self._update_ports
        )
        self.refresh_btn.pack(side=tk.LEFT, padx=(0, 16))

        # right: action button
        right = tk.Frame(hdr, bg=C["bg2"])
        right.pack(side=tk.RIGHT, padx=12, pady=8)

        self.start_btn = tk.Button(
            right, text="▶  CONNECT & COMPARE",
            font=self.f_ui_b, bg=C["accent"], fg=C["text_bright"],
            relief=tk.FLAT, padx=18, pady=6,
            activebackground=C["accent_dim"], activeforeground=C["text_bright"],
            cursor="hand2", command=self._start_thread
        )
        self.start_btn.pack(side=tk.RIGHT)

        # separator
        sep = tk.Frame(self.root, bg=C["border"], height=1)
        sep.grid(row=0, column=0, sticky="sew")

    # ── LOGGER ─────────────────────────────────────────────────────────────
    def _build_logger(self):
        wrap = tk.Frame(self.root, bg=C["bg2"])
        wrap.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        wrap.grid_columnconfigure(0, weight=1)

        tk.Label(wrap, text="SYSTEM LOG", bg=C["bg2"],
                 fg=C["text_dim"], font=self.f_label,
                 anchor="w", padx=12).grid(row=0, column=0, sticky="ew")

        log_frame = tk.Frame(wrap, bg=C["bg2"])
        log_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        log_frame.grid_columnconfigure(0, weight=1)

        self.log_area = tk.Text(
            log_frame, bg=C["panel"], fg=C["green"],
            font=self.f_log, height=5, relief=tk.FLAT,
            state=tk.DISABLED, wrap=tk.WORD,
            insertbackground=C["green"], bd=0,
            highlightthickness=1, highlightbackground=C["border"],
            selectbackground=C["accent_dim"]
        )
        self.log_area.grid(row=0, column=0, sticky="ew")

        log_sb = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_area.yview)
        log_sb.grid(row=0, column=1, sticky="ns")
        self.log_area.configure(yscrollcommand=log_sb.set)

        # log tag colors
        self.log_area.tag_configure("info",    foreground=C["text_dim"])
        self.log_area.tag_configure("ok",      foreground=C["green"])
        self.log_area.tag_configure("warn",    foreground=C["yellow"])
        self.log_area.tag_configure("err",     foreground=C["red"])

        sep2 = tk.Frame(self.root, bg=C["border"], height=1)
        sep2.grid(row=1, column=0, sticky="sew")

    # ── COMPARISON AREA ────────────────────────────────────────────────────
    def _build_comparison(self):
        area = tk.Frame(self.root, bg=C["bg"])
        area.grid(row=2, column=0, sticky="nsew", padx=10, pady=8)
        area.grid_rowconfigure(1, weight=1)
        area.grid_columnconfigure(0, weight=1)
        area.grid_columnconfigure(1, weight=0)  # divider
        area.grid_columnconfigure(2, weight=1)

        # ── Labels ──
        lbl_orig = tk.Frame(area, bg=C["bg"])
        lbl_orig.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        tk.Label(lbl_orig, text="⬤  Original / Reference",
                 bg=C["bg"], fg=C["text"], font=self.f_ui_b).pack(side=tk.LEFT)
        self.orig_lines_lbl = tk.Label(lbl_orig, text="0 lines",
                 bg=C["bg"], fg=C["text_dim"], font=self.f_label)
        self.orig_lines_lbl.pack(side=tk.RIGHT)

        lbl_dl = tk.Frame(area, bg=C["bg"])
        lbl_dl.grid(row=0, column=2, sticky="ew", pady=(0, 4))
        tk.Label(lbl_dl, text="⬤  Downloaded (DUMP ALL)",
                 bg=C["bg"], fg=C["accent"], font=self.f_ui_b).pack(side=tk.LEFT)
        self.dl_lines_lbl = tk.Label(lbl_dl, text="0 lines",
                 bg=C["bg"], fg=C["text_dim"], font=self.f_label)
        self.dl_lines_lbl.pack(side=tk.RIGHT)

        # divider
        tk.Frame(area, bg=C["border"], width=1).grid(
            row=0, column=1, rowspan=2, sticky="ns", padx=6)

        # ── Shared scrollbar ──
        self.shared_vsb = ttk.Scrollbar(area, orient=tk.VERTICAL)
        self.shared_vsb.grid(row=1, column=3, sticky="ns")

        # ── Left editor (Original) ──
        self.orig_text = self._make_editor(area)
        self.orig_text.grid(row=1, column=0, sticky="nsew")

        # ── Right editor (Downloaded) ──
        self.dl_text = self._make_editor(area)
        self.dl_text.grid(row=1, column=2, sticky="nsew")

        # ── Horizontal scrollbars ──
        hsb_orig = ttk.Scrollbar(area, orient=tk.HORIZONTAL, command=self.orig_text.xview)
        hsb_orig.grid(row=2, column=0, sticky="ew")
        self.orig_text.configure(xscrollcommand=hsb_orig.set)

        hsb_dl = ttk.Scrollbar(area, orient=tk.HORIZONTAL, command=self.dl_text.xview)
        hsb_dl.grid(row=2, column=2, sticky="ew")
        self.dl_text.configure(xscrollcommand=hsb_dl.set)

        # ── Sync scroll ──
        self.shared_vsb.configure(command=self._on_shared_scroll)
        self.orig_text.configure(yscrollcommand=lambda *a: self._on_yscroll("orig", *a))
        self.dl_text.configure(yscrollcommand=lambda *a: self._on_yscroll("dl", *a))

    def _make_editor(self, parent):
        t = tk.Text(
            parent, bg=C["editor_bg"], fg=C["editor_fg"],
            font=self.f_mono, relief=tk.FLAT, wrap=tk.NONE,
            state=tk.DISABLED,
            highlightthickness=1, highlightbackground=C["border"],
            selectbackground=C["accent_dim"], selectforeground=C["text_bright"],
            padx=6, pady=4, spacing1=1, spacing3=1
        )
        t.tag_configure("match",   background=C["line_match"],   foreground=C["line_match_fg"])
        t.tag_configure("diff",    background=C["line_diff"],     foreground=C["line_diff_fg"])
        t.tag_configure("added",   background=C["line_added"],    foreground=C["line_added_fg"])
        t.tag_configure("empty",   background=C["gutter_bg"],     foreground=C["gutter_fg"])
        return t

    # ── STATUSBAR ──────────────────────────────────────────────────────────
    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="Ready")
        bar = tk.Frame(self.root, bg=C["bg2"], height=22)
        bar.grid(row=3, column=0, sticky="ew")
        bar.grid_propagate(False)
        tk.Label(bar, textvariable=self.status_var,
                 bg=C["bg2"], fg=C["accent"], font=self.f_label,
                 anchor="w", padx=10).pack(side=tk.LEFT, fill=tk.Y)

        self.diff_stat_var = tk.StringVar(value="")
        tk.Label(bar, textvariable=self.diff_stat_var,
                 bg=C["bg2"], fg=C["yellow"], font=self.f_label,
                 anchor="e", padx=10).pack(side=tk.RIGHT, fill=tk.Y)

    # ── SCROLL SYNC ────────────────────────────────────────────────────────
    def _on_shared_scroll(self, *args):
        self.orig_text.yview(*args)
        self.dl_text.yview(*args)

    def _on_yscroll(self, source, first, last):
        self.shared_vsb.set(first, last)
        if self._scroll_sync_active:
            return
        self._scroll_sync_active = True
        try:
            if source == "orig":
                self.dl_text.yview_moveto(float(first))
            else:
                self.orig_text.yview_moveto(float(first))
        finally:
            self._scroll_sync_active = False

    # ── PORTS ──────────────────────────────────────────────────────────────
    def _get_ports(self):
        return [f"{p.device} — {p.description}" for p in serial.tools.list_ports.comports()]

    def _update_ports(self):
        ports = self._get_ports()
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.current(0)
        self._log("Port list refreshed.", "info")

    # ── LOGGING ────────────────────────────────────────────────────────────
    def _log(self, text, tag="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_area.configure(state=tk.NORMAL)
        self.log_area.insert(tk.END, f"[{ts}] {text}\n", tag)
        self.log_area.see(tk.END)
        self.log_area.configure(state=tk.DISABLED)

    def _set_status(self, text, color=None):
        self.status_var.set(text)
        if color:
            # find the label widget
            for w in self.root.winfo_children():
                if isinstance(w, tk.Frame) and w.cget("bg") == C["bg3"]:
                    for lbl in w.winfo_children():
                        if isinstance(lbl, tk.Label) and lbl.cget("textvariable") == str(self.status_var):
                            lbl.configure(fg=color)

    # ── REFERENCE LOAD ─────────────────────────────────────────────────────
    def _load_reference(self):
        self._set_editor_text(self.orig_text, REFERENCE_CONFIG)
        lines = len(REFERENCE_CONFIG.splitlines())
        self.orig_lines_lbl.configure(text=f"{lines} lines")
        self._log(f"Reference config loaded ({lines} lines).", "ok")

    # ── EDITOR HELPERS ─────────────────────────────────────────────────────
    def _set_editor_text(self, widget, text):
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.configure(state=tk.DISABLED)

    def _append_editor(self, widget, text):
        widget.configure(state=tk.NORMAL)
        widget.insert(tk.END, text)
        widget.see(tk.END)
        widget.configure(state=tk.DISABLED)

    # ── HIGHLIGHT DIFF ─────────────────────────────────────────────────────
    @staticmethod
    def _first_two_words(line):
        """Повертає перші два слова рядка (напр. 'set acc_hardware')."""
        parts = line.strip().split(None, 2)
        return " ".join(parts[:2]) if len(parts) >= 2 else line.strip()

    def _highlight_diff(self):
        """Порівнює кожен рядок з усіма рядками протилежної сторони (set-based)."""
        orig_lines = self.orig_text.get("1.0", tk.END).splitlines()
        dl_lines   = self.dl_text.get("1.0", tk.END).splitlines()

        # множини повних stripped-рядків
        orig_set = set(line.strip() for line in orig_lines)
        dl_set   = set(line.strip() for line in dl_lines)

        # множини перших двох слів (для часткового збігу)
        orig_two = set(self._first_two_words(line) for line in orig_lines if line.strip())
        dl_two   = set(self._first_two_words(line) for line in dl_lines   if line.strip())

        # множини перших слів (для не-set команд)
        orig_w1 = set(line.strip().split(None, 1)[0] for line in orig_lines if line.strip())
        dl_w1   = set(line.strip().split(None, 1)[0] for line in dl_lines   if line.strip())

        # enable both for tagging
        self.orig_text.configure(state=tk.NORMAL)
        self.dl_text.configure(state=tk.NORMAL)

        # clear old tags
        for tag in ("match", "diff", "added", "empty"):
            self.orig_text.tag_remove(tag, "1.0", tk.END)
            self.dl_text.tag_remove(tag, "1.0", tk.END)

        diff_count = 0

        def tag_line(widget, lineno, tag):
            start = f"{lineno}.0"
            end   = f"{lineno}.end"
            widget.tag_add(tag, start, end)

        def classify(stripped, full_set, two_set, w1_set):
            """match / added (жовтий) / diff (червоний)."""
            if stripped in full_set:
                return "match"
            # перші 2 слова збігаються → жовтий
            if self._first_two_words(stripped) in two_set:
                return "added"
            # перше слово збігається і воно НЕ 'set' → жовтий
            first = stripped.split(None, 1)[0] if stripped else ""
            if first.lower() != "set" and first in w1_set:
                return "added"
            return "diff"

        # --- оригінал: кожен рядок шукаємо у dl ---
        CHUNK = 200
        for i in range(0, len(orig_lines), CHUNK):
            for j in range(i, min(i + CHUNK, len(orig_lines))):
                lineno = j + 1
                stripped = orig_lines[j].strip()
                if stripped == "":
                    continue
                result = classify(stripped, dl_set, dl_two, dl_w1)
                tag_line(self.orig_text, lineno, result)
                if result != "match":
                    diff_count += 1
            self.root.update_idletasks()

        # --- завантажене: кожен рядок шукаємо у orig ---
        for i in range(0, len(dl_lines), CHUNK):
            for j in range(i, min(i + CHUNK, len(dl_lines))):
                lineno = j + 1
                stripped = dl_lines[j].strip()
                if stripped == "":
                    continue
                result = classify(stripped, orig_set, orig_two, orig_w1)
                tag_line(self.dl_text, lineno, result)
                if result != "match":
                    diff_count += 1
            self.root.update_idletasks()

        self.orig_text.configure(state=tk.DISABLED)
        self.dl_text.configure(state=tk.DISABLED)

        if diff_count == 0:
            self.diff_stat_var.set("✅ Configs match perfectly")
        else:
            self.diff_stat_var.set(f"⚠  {diff_count} differing line(s) found")
        self._log(f"Diff complete: {diff_count} difference(s).",
                  "ok" if diff_count == 0 else "warn")

    # ── THREAD START ───────────────────────────────────────────────────────
    def _start_thread(self):
        raw = self.port_combo.get()
        if not raw:
            self._log("No COM port selected!", "err")
            return
        port = raw.split(" — ")[0].strip()

        # clear downloaded panel
        self._set_editor_text(self.dl_text, "")
        self.downloaded_text = ""
        self.dl_lines_lbl.configure(text="0 lines")
        self.diff_stat_var.set("")

        self.start_btn.configure(state=tk.DISABLED, text="⏳  Working...")
        self._set_status("Connecting...")
        self._log(f"Connecting to {port} @ 115200...", "info")

        t = threading.Thread(target=self._run_backup, args=(port,), daemon=True)
        t.start()

    # ── BACKUP WORKER ──────────────────────────────────────────────────────
    def _run_backup(self, port):
        ser = None
        try:
            ser = serial.Serial()
            ser.port     = port
            ser.baudrate = 115200
            ser.timeout  = 1
            ser.dtr      = False
            ser.rts      = False
            ser.open()

            self.root.after(0, lambda: self._log(f"Connected to {port}.", "ok"))
            self.root.after(0, lambda: self._set_status(f"Connected · {port}"))
            
            ##Відправити # або $ (щоб вийти з режиму MSP, якщо він активний).
            ser.write(b'#\n')
            time.sleep(0.5)
            ser.reset_input_buffer()

            ser.write(b'dump all\n')
            self.root.after(0, lambda: self._log("Sent 'dump all'. Waiting for data...", "info"))
            self.root.after(0, lambda: self._set_status("Reading dump..."))

            start_time = time.time()
            buffer = ""

            while True:
                if ser.in_waiting > 0:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
                    buffer += chunk
                    # stream to right panel
                    self.root.after(0, lambda c=chunk: self._append_editor(self.dl_text, c))

                    if "save" in chunk.lower() or chunk.strip().endswith("#"):
                        break

                if time.time() - start_time > 25:
                    self.root.after(0, lambda: self._log("Timeout after 25s.", "warn"))
                    break

                time.sleep(0.05)

            self.downloaded_text = buffer
            lines = len(buffer.splitlines())
            self.root.after(0, lambda: self.dl_lines_lbl.configure(text=f"{lines} lines"))

            if len(buffer) > 100:
                # from datetime import datetime as _dt
                # fname = f"bf_backup_{_dt.now().strftime('%Y%m%d_%H%M%S')}.txt"
                # with open(fname, "w", encoding="utf-8") as f:
                #     f.write(buffer)
                # self.root.after(0, lambda: self._log(f"Saved to {fname}", "ok"))
                # self.root.after(0, lambda: self._set_status(f"Done · saved {fname}"))
                self.root.after(0, lambda: self._set_status("Done"))
                # run diff after a short delay (UI needs to render text first)
                self.root.after(300, self._highlight_diff)
            else:
                self.root.after(0, lambda: self._log("No data received.", "err"))
                self.root.after(0, lambda: self._set_status("Error: no data"))

        except Exception as e:
            msg = str(e)
            self.root.after(0, lambda: self._log(f"Error: {msg}", "err"))
            self.root.after(0, lambda: self._set_status("Connection failed"))

        finally:
            self._release_port(ser, port)
            self.root.after(0, self._reset_ui)

    def _release_port(self, ser, port):
        if ser is None:
            return
        for fn in (
            lambda: ser.reset_input_buffer(),
            lambda: ser.reset_output_buffer(),
            lambda: setattr(ser, "dtr", False),
            lambda: setattr(ser, "rts", False),
            lambda: time.sleep(0.1),
            lambda: ser.flush(),
            lambda: ser.close(),
        ):
            try:
                fn()
            except Exception:
                pass
        del ser
        gc.collect()
        time.sleep(0.5)
        self.root.after(0, lambda: self._log(f"Port {port} released. УВАГА: Вам потрібно від'єднати дріт.", "info"))

    def _reset_ui(self):
        self.start_btn.configure(state=tk.NORMAL, text="▶  START BACKUP / COMPARE")
        self.port_combo.set("")
        self.port_combo["values"] = self._get_ports()


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TCombobox",
                    fieldbackground=C["bg3"], background=C["bg3"],
                    foreground=C["text"], selectbackground=C["accent_dim"],
                    arrowcolor=C["text_dim"], bordercolor=C["border"],
                    lightcolor=C["border"], darkcolor=C["border"])
    style.map("TCombobox", fieldbackground=[("readonly", C["bg3"])])
    style.configure("TScrollbar",
                    background=C["bg3"], troughcolor=C["bg2"],
                    arrowcolor=C["text_dim"], bordercolor=C["border"],
                    lightcolor=C["border"], darkcolor=C["border"])

    app = BetaflightDiffTool(root)
    root.mainloop()