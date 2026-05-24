"""
note画像生成アプリ（プレミアム版）
================================
画像を note 推奨サイズ（1920×1006）など各種サイズに一括変換する高機能ツール。

【主な機能】
  - ドラッグ&ドロップでファイル/フォルダ追加
  - リアルタイムプレビュー（選択ファイルの変換結果を即時表示）
  - フィルター効果（セピア / モノクロ / 彩度 / 明度 / コントラスト / ぼかし）
  - 複数サイズ同時生成（チェックで一括出力）
  - テキスト追加（タイトル・キャプション、位置調整）
  - 背景色カスタマイズ
  - 出力形式選択（PNG / JPG / WebP）
  - バッチプリセット（複数フォルダ同時処理 + スケジュール実行）
  - プリセット保存/呼び出し（JSON）
  - モダンなフラットデザイン UI
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except Exception:
    DND_AVAILABLE = False
    TkinterDnD = None
    DND_FILES = None

from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageOps, ImageTk
import numpy as np
import os
import sys
import glob
import threading
import json
import time
import datetime
from pathlib import Path

# ============================================================
# 定数
# ============================================================
SIZE_PRESETS = {
    "note標準 (1920×1006)": {"w": 1920, "h": 1006},
    "X/Twitter (1024×512)": {"w": 1024, "h": 512},
    "Instagram (1080×1080)": {"w": 1080, "h": 1080},
    "YouTube (1280×720)": {"w": 1280, "h": 720},
    "Facebook (1200×630)": {"w": 1200, "h": 630},
    "ブログヘッダー (1500×500)": {"w": 1500, "h": 500},
}
FILL_W = 0.58
FILL_H = 0.71
WHITE_THRESH = 240
SUPPORTED_EXT = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
APP_DIR = Path.home() / ".note_image_generator"
APP_DIR.mkdir(exist_ok=True)
PRESET_FILE = APP_DIR / "presets.json"
BATCH_FILE = APP_DIR / "batch_jobs.json"

# ---- フラットデザインのカラーパレット ----
COLOR_BG = "#f7f8fa"
COLOR_CARD = "#ffffff"
COLOR_PRIMARY = "#4f7cff"
COLOR_PRIMARY_HOVER = "#3a65e0"
COLOR_ACCENT = "#06c5a8"
COLOR_TEXT = "#1f2937"
COLOR_SUBTEXT = "#6b7280"
COLOR_BORDER = "#e5e7eb"
COLOR_DANGER = "#ef4444"
COLOR_WARN = "#f59e0b"

FONT_TITLE = ("Yu Gothic UI", 16, "bold")
FONT_HEADING = ("Yu Gothic UI", 11, "bold")
FONT_BODY = ("Yu Gothic UI", 10)
FONT_SMALL = ("Yu Gothic UI", 9)
FONT_MONO = ("Consolas", 9)


# ============================================================
# 画像処理ユーティリティ
# ============================================================
def find_files(folder, recursive=True):
    """フォルダ内のサポート画像ファイルを列挙"""
    files = []
    if recursive:
        for ext in SUPPORTED_EXT:
            files += glob.glob(os.path.join(folder, "**", f"*{ext}"), recursive=True)
            files += glob.glob(os.path.join(folder, "**", f"*{ext.upper()}"), recursive=True)
    else:
        for ext in SUPPORTED_EXT:
            files += glob.glob(os.path.join(folder, f"*{ext}"))
            files += glob.glob(os.path.join(folder, f"*{ext.upper()}"))
    return sorted(set(files))


def apply_filters(img, sepia=False, grayscale=False, saturation=1.0,
                  brightness=1.0, contrast=1.0, blur=0):
    """フィルター効果を適用"""
    if grayscale:
        img = ImageOps.grayscale(img).convert("RGB")
    elif sepia:
        gray = ImageOps.grayscale(img)
        sep = ImageOps.colorize(gray, black="#241500", white="#FFE7B0")
        img = sep.convert("RGB")

    if abs(saturation - 1.0) > 0.01 and not grayscale:
        img = ImageEnhance.Color(img).enhance(saturation)
    if abs(brightness - 1.0) > 0.01:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    if abs(contrast - 1.0) > 0.01:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur))
    return img


def make_image(img_path, width, height, bg_color,
               text_content="", text_size=32, text_pos="bottom",
               filters=None):
    """
    画像を読み込み指定サイズに変換。テキスト・フィルター対応。
    成功時 PIL.Image / 失敗時 None
    """
    filters = filters or {}
    try:
        pil_img = Image.open(img_path)

        if getattr(pil_img, "is_animated", False):
            n = getattr(pil_img, "n_frames", 1)
            pil_img.seek(min(n // 2, n - 1))

        if pil_img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", pil_img.size, bg_color)
            bg.paste(pil_img, mask=pil_img.split()[-1])
            pil_img = bg
        else:
            pil_img = pil_img.convert("RGB")

        # バウンディングボックス検出（白背景前提のモチーフ抽出）
        dw = max(1, pil_img.width // 3)
        dh = max(1, pil_img.height // 3)
        small = pil_img.resize((dw, dh), Image.BOX)
        arr_s = np.array(small.convert("L"))
        non_white = arr_s < WHITE_THRESH
        ys, xs = np.where(non_white)

        if len(ys) == 0:
            # 真っ白などモチーフが取れない場合は中央フィット
            motif = pil_img
        else:
            P = 60
            x1 = max(0, xs.min() * 3 - P)
            y1 = max(0, ys.min() * 3 - P)
            x2 = min(pil_img.width,  xs.max() * 3 + P)
            y2 = min(pil_img.height, ys.max() * 3 + P)
            motif = pil_img.crop((x1, y1, x2, y2))

        mw, mh = motif.size
        scale = min(width * FILL_W / mw, height * FILL_H / mh)
        nw, nh = max(1, int(mw * scale)), max(1, int(mh * scale))
        motif_r = motif.resize((nw, nh), Image.LANCZOS)

        # フィルター適用（モチーフのみに適用）
        motif_r = apply_filters(motif_r, **filters)

        canvas = Image.new("RGB", (width, height), bg_color)
        canvas.paste(motif_r, ((width - nw) // 2, (height - nh) // 2))

        # テキスト追加
        if text_content.strip():
            draw = ImageDraw.Draw(canvas)
            font = _load_font(text_size)
            text_color = (255, 255, 255) if sum(bg_color) < 382 else (30, 30, 30)
            bbox = draw.textbbox((0, 0), text_content, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = (width - tw) // 2
            if text_pos == "top":
                ty = 30
            elif text_pos == "middle":
                ty = (height - th) // 2
            else:  # bottom
                ty = height - th - 40
            # シャドウ効果（読みやすさ向上）
            shadow_color = (0, 0, 0) if text_color == (255, 255, 255) else (255, 255, 255)
            for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
                draw.text((tx + dx, ty + dy), text_content,
                          fill=shadow_color, font=font)
            draw.text((tx, ty), text_content, fill=text_color, font=font)

        return canvas

    except Exception:
        return None


def _load_font(size):
    """日本語OKのフォントを順に試す"""
    candidates = [
        "C:/Windows/Fonts/YuGothB.ttc",
        "C:/Windows/Fonts/YuGothM.ttc",
        "C:/Windows/Fonts/meiryob.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
        "arial.ttf",
    ]
    for fp in candidates:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ============================================================
# プリセット / バッチ管理
# ============================================================
def load_json(path, default):
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ============================================================
# UI ヘルパ
# ============================================================
class FlatButton(tk.Button):
    """フラットデザインなボタン"""
    def __init__(self, master, text="", command=None,
                 primary=False, danger=False, small=False, **kw):
        if primary:
            bg, fg, hover = COLOR_PRIMARY, "white", COLOR_PRIMARY_HOVER
        elif danger:
            bg, fg, hover = COLOR_DANGER, "white", "#dc2626"
        else:
            bg, fg, hover = COLOR_CARD, COLOR_TEXT, "#eef2f7"
        font = FONT_SMALL if small else FONT_BODY
        super().__init__(
            master, text=text, command=command,
            bg=bg, fg=fg, activebackground=hover, activeforeground=fg,
            relief="flat", bd=0, font=font,
            padx=12 if small else 16, pady=4 if small else 7,
            cursor="hand2", **kw
        )
        self._bg = bg
        self._hover = hover
        self.bind("<Enter>", lambda e: self.configure(bg=self._hover))
        self.bind("<Leave>", lambda e: self.configure(bg=self._bg))


class Card(tk.Frame):
    """カード風のセクション枠"""
    def __init__(self, master, title=None, **kw):
        super().__init__(master, bg=COLOR_CARD, bd=0,
                         highlightbackground=COLOR_BORDER,
                         highlightthickness=1, **kw)
        if title:
            tk.Label(self, text=title, font=FONT_HEADING,
                     bg=COLOR_CARD, fg=COLOR_TEXT,
                     anchor="w").pack(fill="x", padx=14, pady=(10, 4))


# ============================================================
# メインアプリ
# ============================================================
class App(TkinterDnD.Tk if DND_AVAILABLE else tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("note 画像生成アプリ — Premium Edition")
        self.geometry("1180x780")
        self.minsize(1080, 720)
        self.configure(bg=COLOR_BG)

        self._init_style()
        self._init_vars()

        self.presets = load_json(PRESET_FILE, {})
        self.batch_jobs = load_json(BATCH_FILE, [])
        self.preview_cache = {}
        self.preview_thread = None
        self.preview_lock = threading.Lock()
        self.scheduler_thread = None
        self.scheduler_running = False

        self._build_ui()
        self._bind_dnd()
        self._refresh_batch_list()

    # ---- スタイル ----
    def _init_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=COLOR_BG, foreground=COLOR_SUBTEXT,
                        padding=[18, 8], font=FONT_BODY, borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", COLOR_CARD)],
                  foreground=[("selected", COLOR_PRIMARY)])
        style.configure("TCombobox", fieldbackground=COLOR_CARD,
                        background=COLOR_CARD, padding=4)
        style.configure("Horizontal.TProgressbar",
                        troughcolor=COLOR_BORDER,
                        background=COLOR_PRIMARY, bordercolor=COLOR_BORDER,
                        thickness=8)
        style.configure("TCheckbutton", background=COLOR_CARD,
                        foreground=COLOR_TEXT, font=FONT_BODY)
        style.configure("Treeview", background=COLOR_CARD,
                        fieldbackground=COLOR_CARD, foreground=COLOR_TEXT,
                        rowheight=24, font=FONT_BODY, bordercolor=COLOR_BORDER)
        style.configure("Treeview.Heading", background=COLOR_BG,
                        foreground=COLOR_TEXT, font=FONT_HEADING,
                        relief="flat")

    # ---- 変数初期化 ----
    def _init_vars(self):
        self.src_var = tk.StringVar()
        self.dst_var = tk.StringVar()
        self.recursive_var = tk.BooleanVar(value=True)
        self.keep_structure_var = tk.BooleanVar(value=True)

        # 複数サイズ選択用
        self.size_vars = {name: tk.BooleanVar(value=(name == "note標準 (1920×1006)"))
                          for name in SIZE_PRESETS}

        self.output_format = tk.StringVar(value="PNG")
        self.bg_color_var = tk.StringVar(value="#FFFFFF")
        self.text_content_var = tk.StringVar(value="")
        self.text_size_var = tk.IntVar(value=42)
        self.text_pos_var = tk.StringVar(value="bottom")

        # フィルター
        self.f_sepia = tk.BooleanVar(value=False)
        self.f_gray = tk.BooleanVar(value=False)
        self.f_sat = tk.DoubleVar(value=1.0)
        self.f_bright = tk.DoubleVar(value=1.0)
        self.f_contrast = tk.DoubleVar(value=1.0)
        self.f_blur = tk.DoubleVar(value=0.0)

        # スケジュール
        self.sched_enabled = tk.BooleanVar(value=False)
        self.sched_time = tk.StringVar(value="03:00")

        self.preview_file_var = tk.StringVar(value="")

    # ---- UI構築 ----
    def _build_ui(self):
        # ヘッダー
        header = tk.Frame(self, bg=COLOR_BG)
        header.pack(fill="x", padx=20, pady=(16, 4))
        tk.Label(header, text="note 画像生成", font=FONT_TITLE,
                 bg=COLOR_BG, fg=COLOR_TEXT).pack(side="left")
        tk.Label(header, text="  Premium Edition",
                 font=("Yu Gothic UI", 10), bg=COLOR_BG, fg=COLOR_PRIMARY
                 ).pack(side="left", padx=(2, 0), pady=(8, 0))
        tk.Label(header,
                 text="高機能フラットデザイン版 — リアルタイムプレビュー / フィルター / バッチ / スケジュール",
                 font=FONT_SMALL, bg=COLOR_BG, fg=COLOR_SUBTEXT
                 ).pack(side="left", padx=12, pady=(8, 0))

        # タブ
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=20, pady=10)

        self.tab_main = tk.Frame(notebook, bg=COLOR_BG)
        self.tab_batch = tk.Frame(notebook, bg=COLOR_BG)
        notebook.add(self.tab_main, text="  メイン変換  ")
        notebook.add(self.tab_batch, text="  バッチ / スケジュール  ")

        self._build_main_tab(self.tab_main)
        self._build_batch_tab(self.tab_batch)

    # ---- メインタブ ----
    def _build_main_tab(self, parent):
        # 左右2カラム
        left = tk.Frame(parent, bg=COLOR_BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right = tk.Frame(parent, bg=COLOR_BG, width=460)
        right.pack(side="right", fill="both", padx=(8, 0))
        right.pack_propagate(False)

        # ===== 左: 設定 =====
        # ソース/出力
        c1 = Card(left, title="📁 フォルダ設定")
        c1.pack(fill="x", pady=(8, 6))
        self._make_folder_row(c1, "ソース:", self.src_var, self._browse_src)
        self._make_folder_row(c1, "出力先:", self.dst_var, self._browse_dst)
        opt = tk.Frame(c1, bg=COLOR_CARD)
        opt.pack(fill="x", padx=14, pady=(2, 10))
        ttk.Checkbutton(opt, text="サブフォルダも処理",
                        variable=self.recursive_var).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(opt, text="フォルダ構造を維持",
                        variable=self.keep_structure_var).pack(side="left")

        # 出力サイズ（複数選択）
        c2 = Card(left, title="📐 出力サイズ（複数選択可）")
        c2.pack(fill="x", pady=6)
        grid = tk.Frame(c2, bg=COLOR_CARD)
        grid.pack(fill="x", padx=14, pady=(0, 10))
        for i, name in enumerate(SIZE_PRESETS):
            cb = ttk.Checkbutton(grid, text=name, variable=self.size_vars[name])
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=(0, 16), pady=2)

        # 出力形式・背景色
        c3 = Card(left, title="🎨 スタイル設定")
        c3.pack(fill="x", pady=6)
        row1 = tk.Frame(c3, bg=COLOR_CARD)
        row1.pack(fill="x", padx=14, pady=(2, 4))
        tk.Label(row1, text="形式:", bg=COLOR_CARD, fg=COLOR_TEXT,
                 font=FONT_BODY).pack(side="left")
        ttk.Combobox(row1, textvariable=self.output_format,
                     values=["PNG", "JPG", "WebP"], state="readonly",
                     width=8).pack(side="left", padx=(6, 16))
        tk.Label(row1, text="背景色:", bg=COLOR_CARD,
                 font=FONT_BODY).pack(side="left")
        self.color_swatch = tk.Frame(row1, bg=self.bg_color_var.get(),
                                     width=24, height=24,
                                     highlightbackground=COLOR_BORDER,
                                     highlightthickness=1)
        self.color_swatch.pack(side="left", padx=(6, 4))
        tk.Entry(row1, textvariable=self.bg_color_var, width=10,
                 font=FONT_MONO, relief="flat",
                 highlightbackground=COLOR_BORDER, highlightthickness=1,
                 ).pack(side="left", padx=(0, 4))
        FlatButton(row1, text="色選択", command=self._pick_color,
                   small=True).pack(side="left")
        self.bg_color_var.trace_add("write", lambda *a: self._on_color_change())

        # テキスト
        row2 = tk.Frame(c3, bg=COLOR_CARD)
        row2.pack(fill="x", padx=14, pady=(2, 10))
        tk.Label(row2, text="テキスト:", bg=COLOR_CARD,
                 font=FONT_BODY).pack(side="left")
        tk.Entry(row2, textvariable=self.text_content_var, width=22,
                 font=FONT_BODY, relief="flat",
                 highlightbackground=COLOR_BORDER, highlightthickness=1
                 ).pack(side="left", padx=(6, 10))
        tk.Label(row2, text="サイズ:", bg=COLOR_CARD,
                 font=FONT_BODY).pack(side="left")
        tk.Spinbox(row2, from_=10, to=120, textvariable=self.text_size_var,
                   width=4, font=FONT_BODY).pack(side="left", padx=(4, 10))
        tk.Label(row2, text="位置:", bg=COLOR_CARD,
                 font=FONT_BODY).pack(side="left")
        ttk.Combobox(row2, textvariable=self.text_pos_var,
                     values=["top", "middle", "bottom"], state="readonly",
                     width=8).pack(side="left", padx=(4, 0))

        # フィルター
        c4 = Card(left, title="✨ フィルター効果")
        c4.pack(fill="x", pady=6)
        fr = tk.Frame(c4, bg=COLOR_CARD)
        fr.pack(fill="x", padx=14, pady=(2, 4))
        ttk.Checkbutton(fr, text="セピア", variable=self.f_sepia,
                        command=self._on_filter_change).pack(side="left", padx=(0, 14))
        ttk.Checkbutton(fr, text="モノクロ", variable=self.f_gray,
                        command=self._on_filter_change).pack(side="left", padx=(0, 14))
        FlatButton(fr, text="リセット",
                   command=self._reset_filters, small=True).pack(side="right")

        self._make_slider(c4, "彩度", self.f_sat, 0.0, 2.0)
        self._make_slider(c4, "明度", self.f_bright, 0.3, 2.0)
        self._make_slider(c4, "コントラスト", self.f_contrast, 0.3, 2.0)
        self._make_slider(c4, "ぼかし", self.f_blur, 0.0, 10.0)
        tk.Frame(c4, bg=COLOR_CARD, height=6).pack()

        # プリセット
        c5 = Card(left, title="💾 プリセット")
        c5.pack(fill="x", pady=6)
        pr = tk.Frame(c5, bg=COLOR_CARD)
        pr.pack(fill="x", padx=14, pady=(2, 10))
        self.preset_combo = ttk.Combobox(pr, values=list(self.presets.keys()),
                                         state="readonly", width=24)
        self.preset_combo.pack(side="left", padx=(0, 6))
        FlatButton(pr, text="読込", command=self._load_preset,
                   small=True).pack(side="left", padx=2)
        FlatButton(pr, text="保存", command=self._save_preset,
                   small=True).pack(side="left", padx=2)
        FlatButton(pr, text="削除", command=self._delete_preset,
                   danger=True, small=True).pack(side="left", padx=2)

        # 実行ボタン
        bottom = tk.Frame(left, bg=COLOR_BG)
        bottom.pack(fill="x", pady=(10, 0))
        self.btn_start = FlatButton(bottom, text="▶  変換開始",
                                    command=self._start, primary=True)
        self.btn_start.pack(side="right")
        self.progress = ttk.Progressbar(bottom, length=320, mode="determinate",
                                        style="Horizontal.TProgressbar")
        self.progress.pack(side="left", padx=(0, 10), pady=8, fill="x", expand=True)
        self.progress_label = tk.Label(bottom, text="待機中", font=FONT_SMALL,
                                       bg=COLOR_BG, fg=COLOR_SUBTEXT)
        self.progress_label.pack(side="left")

        # ログ
        log_card = Card(left)
        log_card.pack(fill="both", expand=True, pady=(6, 0))
        self.log_text = tk.Text(log_card, height=6, font=FONT_MONO,
                                bg=COLOR_CARD, fg=COLOR_TEXT,
                                relief="flat", bd=0, state="disabled",
                                highlightthickness=0, padx=14, pady=8)
        self.log_text.pack(fill="both", expand=True, padx=2, pady=2)

        # ===== 右: プレビュー =====
        prev_card = Card(right, title="👁  リアルタイムプレビュー")
        prev_card.pack(fill="both", expand=True, pady=(8, 0))

        sel = tk.Frame(prev_card, bg=COLOR_CARD)
        sel.pack(fill="x", padx=14, pady=(0, 6))
        FlatButton(sel, text="ファイル選択…",
                   command=self._pick_preview_file, small=True
                   ).pack(side="left")
        self.preview_filename = tk.Label(sel, text="（未選択）",
                                         font=FONT_SMALL, bg=COLOR_CARD,
                                         fg=COLOR_SUBTEXT, anchor="w")
        self.preview_filename.pack(side="left", padx=(8, 0), fill="x", expand=True)

        # キャンバス
        self.preview_canvas = tk.Canvas(prev_card, bg="#f2f3f6",
                                        highlightthickness=1,
                                        highlightbackground=COLOR_BORDER,
                                        height=320)
        self.preview_canvas.pack(fill="both", expand=True, padx=14, pady=8)
        self.preview_status = tk.Label(prev_card,
                                       text="画像をドラッグ&ドロップするとプレビューされます",
                                       font=FONT_SMALL, bg=COLOR_CARD,
                                       fg=COLOR_SUBTEXT)
        self.preview_status.pack(pady=(0, 10))

        # 設定変更でプレビュー再描画
        for var in (self.bg_color_var, self.text_content_var,
                    self.text_pos_var):
            var.trace_add("write", lambda *a: self._schedule_preview())
        for var in (self.text_size_var, self.f_sat, self.f_bright,
                    self.f_contrast, self.f_blur):
            var.trace_add("write", lambda *a: self._schedule_preview())

    # ---- バッチタブ ----
    def _build_batch_tab(self, parent):
        wrap = tk.Frame(parent, bg=COLOR_BG)
        wrap.pack(fill="both", expand=True)

        # 説明
        tk.Label(wrap,
                 text="複数のソースフォルダ→出力フォルダのペアを登録し、一括／スケジュール実行できます。",
                 font=FONT_SMALL, bg=COLOR_BG, fg=COLOR_SUBTEXT,
                 anchor="w").pack(fill="x", padx=4, pady=(10, 6))

        # ジョブリスト
        list_card = Card(wrap, title="📋 バッチジョブ")
        list_card.pack(fill="both", expand=True, padx=4, pady=4)

        cols = ("src", "dst", "sizes", "format")
        self.batch_tree = ttk.Treeview(list_card, columns=cols, show="headings",
                                       height=8)
        for c, t, w in [("src", "ソース", 320), ("dst", "出力先", 320),
                        ("sizes", "サイズ", 180), ("format", "形式", 80)]:
            self.batch_tree.heading(c, text=t)
            self.batch_tree.column(c, width=w, anchor="w")
        self.batch_tree.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        btn_row = tk.Frame(list_card, bg=COLOR_CARD)
        btn_row.pack(fill="x", padx=12, pady=(0, 10))
        FlatButton(btn_row, text="＋ 現在の設定を追加",
                   command=self._add_batch_job, primary=True, small=True
                   ).pack(side="left", padx=2)
        FlatButton(btn_row, text="選択を削除",
                   command=self._remove_batch_job, danger=True, small=True
                   ).pack(side="left", padx=2)
        FlatButton(btn_row, text="全クリア",
                   command=self._clear_batch_jobs, small=True
                   ).pack(side="left", padx=2)
        FlatButton(btn_row, text="▶ 一括実行",
                   command=self._run_batch_all, primary=True, small=True
                   ).pack(side="right", padx=2)

        # スケジュール設定
        sched_card = Card(wrap, title="⏰ スケジュール実行")
        sched_card.pack(fill="x", padx=4, pady=4)
        sr = tk.Frame(sched_card, bg=COLOR_CARD)
        sr.pack(fill="x", padx=14, pady=(2, 10))
        ttk.Checkbutton(sr, text="毎日この時刻に実行",
                        variable=self.sched_enabled,
                        command=self._toggle_scheduler).pack(side="left")
        tk.Label(sr, text="  時刻 (HH:MM):", bg=COLOR_CARD,
                 font=FONT_BODY).pack(side="left", padx=(6, 4))
        tk.Entry(sr, textvariable=self.sched_time, width=8,
                 font=FONT_MONO, relief="flat",
                 highlightbackground=COLOR_BORDER, highlightthickness=1
                 ).pack(side="left")
        self.sched_status = tk.Label(sr, text="スケジューラ停止中",
                                     font=FONT_SMALL, bg=COLOR_CARD,
                                     fg=COLOR_SUBTEXT)
        self.sched_status.pack(side="left", padx=14)

    # ---- 共通UI部品 ----
    def _make_folder_row(self, parent, label, var, cmd):
        row = tk.Frame(parent, bg=COLOR_CARD)
        row.pack(fill="x", padx=14, pady=4)
        tk.Label(row, text=label, font=FONT_BODY, bg=COLOR_CARD,
                 fg=COLOR_TEXT, width=8, anchor="w").pack(side="left")
        e = tk.Entry(row, textvariable=var, font=FONT_BODY, relief="flat",
                     highlightbackground=COLOR_BORDER, highlightthickness=1)
        e.pack(side="left", fill="x", expand=True, padx=4, ipady=3)
        FlatButton(row, text="参照…", command=cmd, small=True
                   ).pack(side="left", padx=4)

    def _make_slider(self, parent, label, var, mn, mx):
        row = tk.Frame(parent, bg=COLOR_CARD)
        row.pack(fill="x", padx=14, pady=1)
        tk.Label(row, text=label, font=FONT_SMALL, bg=COLOR_CARD,
                 fg=COLOR_SUBTEXT, width=10, anchor="w").pack(side="left")
        s = ttk.Scale(row, from_=mn, to=mx, variable=var, orient="horizontal")
        s.pack(side="left", fill="x", expand=True, padx=4)
        val_lbl = tk.Label(row, text=f"{var.get():.2f}", font=FONT_SMALL,
                           bg=COLOR_CARD, fg=COLOR_TEXT, width=5)
        val_lbl.pack(side="left")
        var.trace_add("write",
                      lambda *a: val_lbl.configure(text=f"{var.get():.2f}"))

    # ---- イベント ----
    def _on_color_change(self):
        try:
            self.color_swatch.configure(bg=self.bg_color_var.get())
        except Exception:
            pass
        self._schedule_preview()

    def _on_filter_change(self):
        # セピアとモノクロは排他
        if self.f_sepia.get() and self.f_gray.get():
            self.f_gray.set(False)
        self._schedule_preview()

    def _reset_filters(self):
        self.f_sepia.set(False)
        self.f_gray.set(False)
        self.f_sat.set(1.0)
        self.f_bright.set(1.0)
        self.f_contrast.set(1.0)
        self.f_blur.set(0.0)

    def _browse_src(self):
        d = filedialog.askdirectory(title="ソースフォルダを選択")
        if d:
            self.src_var.set(d)

    def _browse_dst(self):
        d = filedialog.askdirectory(title="出力フォルダを選択")
        if d:
            self.dst_var.set(d)

    def _pick_color(self):
        from tkinter.colorchooser import askcolor
        c = askcolor(color=self.bg_color_var.get(), title="背景色を選択")
        if c[1]:
            self.bg_color_var.set(c[1])

    def _pick_preview_file(self):
        f = filedialog.askopenfilename(
            title="プレビュー用画像を選択",
            filetypes=[("画像ファイル", "*.jpg *.jpeg *.png *.gif *.bmp *.webp")]
        )
        if f:
            self._set_preview_file(f)

    def _set_preview_file(self, path):
        self.preview_file_var.set(path)
        self.preview_filename.configure(text=os.path.basename(path))
        self._schedule_preview()

    # ---- D&D ----
    def _bind_dnd(self):
        if not DND_AVAILABLE:
            return
        try:
            self.preview_canvas.drop_target_register(DND_FILES)
            self.preview_canvas.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass
        try:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._on_drop)
        except Exception:
            pass

    def _on_drop(self, event):
        # event.data はスペース区切り {path with space} 形式
        data = event.data.strip()
        paths = []
        cur = ""
        in_brace = False
        for ch in data:
            if ch == "{":
                in_brace = True
                cur = ""
            elif ch == "}":
                in_brace = False
                paths.append(cur)
                cur = ""
            elif ch == " " and not in_brace:
                if cur:
                    paths.append(cur)
                    cur = ""
            else:
                cur += ch
        if cur:
            paths.append(cur)
        if not paths:
            return
        p = paths[0]
        if os.path.isdir(p):
            self.src_var.set(p)
        elif os.path.isfile(p):
            self._set_preview_file(p)

    # ---- プレビュー ----
    def _schedule_preview(self):
        if hasattr(self, "_preview_after"):
            try:
                self.after_cancel(self._preview_after)
            except Exception:
                pass
        self._preview_after = self.after(250, self._render_preview)

    def _render_preview(self):
        path = self.preview_file_var.get()
        if not path or not os.path.isfile(path):
            return
        # 選択中のサイズの先頭を使う
        chosen = [n for n, v in self.size_vars.items() if v.get()]
        if not chosen:
            self.preview_status.configure(
                text="サイズを1つ以上選択してください", fg=COLOR_WARN)
            return
        size_name = chosen[0]
        w = SIZE_PRESETS[size_name]["w"]
        h = SIZE_PRESETS[size_name]["h"]

        try:
            bg = tuple(int(self.bg_color_var.get().lstrip("#")[i:i+2], 16)
                       for i in (0, 2, 4))
        except Exception:
            bg = (255, 255, 255)

        filters = {
            "sepia": self.f_sepia.get(),
            "grayscale": self.f_gray.get(),
            "saturation": self.f_sat.get(),
            "brightness": self.f_bright.get(),
            "contrast": self.f_contrast.get(),
            "blur": self.f_blur.get(),
        }
        text = self.text_content_var.get()
        ts = self.text_size_var.get()
        tp = self.text_pos_var.get()

        def work():
            with self.preview_lock:
                img = make_image(path, w, h, bg, text, ts, tp, filters)
            self.after(0, lambda: self._show_preview(img, size_name))

        if self.preview_thread and self.preview_thread.is_alive():
            return
        self.preview_thread = threading.Thread(target=work, daemon=True)
        self.preview_thread.start()

    def _show_preview(self, img, size_name):
        if img is None:
            self.preview_canvas.delete("all")
            self.preview_status.configure(
                text="この画像は処理できませんでした", fg=COLOR_DANGER)
            return
        cw = max(self.preview_canvas.winfo_width(), 200)
        ch = max(self.preview_canvas.winfo_height(), 200)
        scale = min(cw / img.width, ch / img.height, 1.0)
        nw = max(1, int(img.width * scale))
        nh = max(1, int(img.height * scale))
        thumb = img.resize((nw, nh), Image.LANCZOS)
        self._preview_img = ImageTk.PhotoImage(thumb)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(cw // 2, ch // 2,
                                         image=self._preview_img)
        self.preview_status.configure(
            text=f"{size_name} — {img.width}×{img.height}px",
            fg=COLOR_SUBTEXT)

    # ---- ログ ----
    def _log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ---- プリセット ----
    def _collect_settings(self):
        return {
            "sizes": [n for n, v in self.size_vars.items() if v.get()],
            "format": self.output_format.get(),
            "bg_color": self.bg_color_var.get(),
            "text": self.text_content_var.get(),
            "text_size": self.text_size_var.get(),
            "text_pos": self.text_pos_var.get(),
            "filters": {
                "sepia": self.f_sepia.get(),
                "grayscale": self.f_gray.get(),
                "saturation": self.f_sat.get(),
                "brightness": self.f_bright.get(),
                "contrast": self.f_contrast.get(),
                "blur": self.f_blur.get(),
            },
            "recursive": self.recursive_var.get(),
            "keep_structure": self.keep_structure_var.get(),
        }

    def _apply_settings(self, s):
        for n, v in self.size_vars.items():
            v.set(n in s.get("sizes", []))
        self.output_format.set(s.get("format", "PNG"))
        self.bg_color_var.set(s.get("bg_color", "#FFFFFF"))
        self.text_content_var.set(s.get("text", ""))
        self.text_size_var.set(s.get("text_size", 42))
        self.text_pos_var.set(s.get("text_pos", "bottom"))
        f = s.get("filters", {})
        self.f_sepia.set(f.get("sepia", False))
        self.f_gray.set(f.get("grayscale", False))
        self.f_sat.set(f.get("saturation", 1.0))
        self.f_bright.set(f.get("brightness", 1.0))
        self.f_contrast.set(f.get("contrast", 1.0))
        self.f_blur.set(f.get("blur", 0.0))
        self.recursive_var.set(s.get("recursive", True))
        self.keep_structure_var.set(s.get("keep_structure", True))

    def _save_preset(self):
        from tkinter.simpledialog import askstring
        name = askstring("プリセット保存", "プリセット名:")
        if not name:
            return
        self.presets[name] = self._collect_settings()
        save_json(PRESET_FILE, self.presets)
        self.preset_combo.configure(values=list(self.presets.keys()))
        self.preset_combo.set(name)
        self._log(f"✓ プリセット保存: {name}")

    def _load_preset(self):
        name = self.preset_combo.get()
        if not name or name not in self.presets:
            return
        self._apply_settings(self.presets[name])
        self._log(f"✓ プリセット読込: {name}")
        self._schedule_preview()

    def _delete_preset(self):
        name = self.preset_combo.get()
        if not name or name not in self.presets:
            return
        if messagebox.askyesno("確認", f"プリセット '{name}' を削除しますか？"):
            del self.presets[name]
            save_json(PRESET_FILE, self.presets)
            self.preset_combo.configure(values=list(self.presets.keys()))
            self.preset_combo.set("")
            self._log(f"✓ プリセット削除: {name}")

    # ---- バッチジョブ ----
    def _add_batch_job(self):
        s = self._collect_settings()
        if not self.src_var.get() or not self.dst_var.get():
            messagebox.showerror("エラー", "ソース/出力フォルダを指定してください")
            return
        if not s["sizes"]:
            messagebox.showerror("エラー", "サイズを1つ以上選択してください")
            return
        job = {
            "src": self.src_var.get(),
            "dst": self.dst_var.get(),
            "settings": s,
        }
        self.batch_jobs.append(job)
        save_json(BATCH_FILE, self.batch_jobs)
        self._refresh_batch_list()

    def _remove_batch_job(self):
        sel = self.batch_tree.selection()
        if not sel:
            return
        idx = self.batch_tree.index(sel[0])
        del self.batch_jobs[idx]
        save_json(BATCH_FILE, self.batch_jobs)
        self._refresh_batch_list()

    def _clear_batch_jobs(self):
        if not self.batch_jobs:
            return
        if messagebox.askyesno("確認", "全てのバッチジョブを削除しますか？"):
            self.batch_jobs.clear()
            save_json(BATCH_FILE, self.batch_jobs)
            self._refresh_batch_list()

    def _refresh_batch_list(self):
        for item in self.batch_tree.get_children():
            self.batch_tree.delete(item)
        for job in self.batch_jobs:
            s = job["settings"]
            sizes = ", ".join([sz.split(" ")[0] for sz in s.get("sizes", [])])
            self.batch_tree.insert("", "end", values=(
                job["src"], job["dst"], sizes, s.get("format", "PNG")
            ))

    def _run_batch_all(self):
        if not self.batch_jobs:
            messagebox.showinfo("情報", "バッチジョブが登録されていません")
            return
        threading.Thread(target=self._batch_worker, daemon=True).start()

    def _batch_worker(self):
        self._log(f"\n=== バッチ実行開始 ({len(self.batch_jobs)} ジョブ) ===")
        for i, job in enumerate(self.batch_jobs, 1):
            self._log(f"\n[ジョブ {i}/{len(self.batch_jobs)}] {job['src']}")
            self._run_one_job(job)
        self._log(f"\n=== バッチ実行完了 ===")

    def _run_one_job(self, job):
        src = job["src"]
        dst = job["dst"]
        s = job["settings"]
        if not os.path.isdir(src):
            self._log(f"  スキップ: ソースが存在しません")
            return
        os.makedirs(dst, exist_ok=True)
        files = find_files(src, recursive=s.get("recursive", True))
        if not files:
            self._log("  対象ファイルなし")
            return
        try:
            bg = tuple(int(s["bg_color"].lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            bg = (255, 255, 255)

        sizes = s.get("sizes", [])
        fmt = s.get("format", "PNG")
        ext = fmt.lower()
        ok = 0
        skip = 0
        for fpath in files:
            for size_name in sizes:
                w = SIZE_PRESETS[size_name]["w"]
                h = SIZE_PRESETS[size_name]["h"]
                img = make_image(fpath, w, h, bg,
                                 s.get("text", ""), s.get("text_size", 42),
                                 s.get("text_pos", "bottom"),
                                 s.get("filters", {}))
                if img is None:
                    skip += 1
                    continue
                if s.get("keep_structure", True):
                    rel = os.path.relpath(os.path.dirname(fpath), src)
                    out_dir = os.path.join(dst, rel)
                else:
                    out_dir = dst
                if len(sizes) > 1:
                    out_dir = os.path.join(out_dir, size_name.split(" ")[0])
                os.makedirs(out_dir, exist_ok=True)
                base = os.path.splitext(os.path.basename(fpath))[0] + f".{ext}"
                out_path = os.path.join(out_dir, base)
                try:
                    if fmt == "JPG":
                        img.save(out_path, "JPEG", quality=95)
                    elif fmt == "WebP":
                        img.save(out_path, "WEBP", quality=95)
                    else:
                        img.save(out_path)
                    ok += 1
                except Exception as e:
                    self._log(f"  保存失敗: {e}")
                    skip += 1
        self._log(f"  完了: {ok} 枚出力 / {skip} 件スキップ")

    # ---- スケジューラ ----
    def _toggle_scheduler(self):
        if self.sched_enabled.get():
            self._start_scheduler()
        else:
            self._stop_scheduler()

    def _start_scheduler(self):
        if self.scheduler_running:
            return
        self.scheduler_running = True
        self.scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        self.sched_status.configure(text=f"⏰ 毎日 {self.sched_time.get()} に実行",
                                    fg=COLOR_ACCENT)
        self._log(f"スケジューラ開始: 毎日 {self.sched_time.get()}")

    def _stop_scheduler(self):
        self.scheduler_running = False
        self.sched_status.configure(text="スケジューラ停止中", fg=COLOR_SUBTEXT)
        self._log("スケジューラ停止")

    def _scheduler_loop(self):
        last_run_date = None
        while self.scheduler_running:
            try:
                target = self.sched_time.get().strip()
                hh, mm = target.split(":")
                hh, mm = int(hh), int(mm)
                now = datetime.datetime.now()
                if (now.hour == hh and now.minute == mm
                        and last_run_date != now.date()):
                    self._log(f"\n⏰ スケジュール起動 ({target})")
                    last_run_date = now.date()
                    self._batch_worker()
            except Exception:
                pass
            time.sleep(30)

    # ---- メイン実行 ----
    def _start(self):
        src = self.src_var.get().strip()
        dst = self.dst_var.get().strip()
        if not src or not os.path.isdir(src):
            messagebox.showerror("エラー", "ソースフォルダを正しく指定してください")
            return
        if not dst:
            messagebox.showerror("エラー", "出力フォルダを指定してください")
            return
        sizes = [n for n, v in self.size_vars.items() if v.get()]
        if not sizes:
            messagebox.showerror("エラー", "サイズを1つ以上選択してください")
            return
        os.makedirs(dst, exist_ok=True)
        self.btn_start.configure(state="disabled")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        threading.Thread(target=self._process,
                         args=(src, dst, sizes), daemon=True).start()

    def _process(self, src, dst, sizes):
        recursive = self.recursive_var.get()
        keep = self.keep_structure_var.get()
        fmt = self.output_format.get()
        ext = fmt.lower()
        text = self.text_content_var.get()
        ts = self.text_size_var.get()
        tp = self.text_pos_var.get()
        try:
            bg = tuple(int(self.bg_color_var.get().lstrip("#")[i:i+2], 16)
                       for i in (0, 2, 4))
        except Exception:
            bg = (255, 255, 255)
        filters = {
            "sepia": self.f_sepia.get(),
            "grayscale": self.f_gray.get(),
            "saturation": self.f_sat.get(),
            "brightness": self.f_bright.get(),
            "contrast": self.f_contrast.get(),
            "blur": self.f_blur.get(),
        }

        files = find_files(src, recursive=recursive)
        total = len(files) * len(sizes)
        if total == 0:
            self._log("対象ファイルが見つかりませんでした")
            self.btn_start.configure(state="normal")
            return

        self._log(f"開始: {len(files)} 枚 × {len(sizes)} サイズ = {total} 出力")
        self.progress["maximum"] = total
        self.progress["value"] = 0

        ok = 0
        skip = 0
        idx = 0
        for fpath in files:
            fname = os.path.relpath(fpath, src)
            for size_name in sizes:
                idx += 1
                w = SIZE_PRESETS[size_name]["w"]
                h = SIZE_PRESETS[size_name]["h"]
                self.progress_label.configure(
                    text=f"{idx}/{total}  {fname[:30]} → {size_name.split(' ')[0]}")
                img = make_image(fpath, w, h, bg, text, ts, tp, filters)
                if img is None:
                    skip += 1
                else:
                    if keep:
                        rel = os.path.relpath(os.path.dirname(fpath), src)
                        out_dir = os.path.join(dst, rel)
                    else:
                        out_dir = dst
                    if len(sizes) > 1:
                        out_dir = os.path.join(out_dir, size_name.split(" ")[0])
                    os.makedirs(out_dir, exist_ok=True)
                    base = os.path.splitext(os.path.basename(fpath))[0] + f".{ext}"
                    out_path = os.path.join(out_dir, base)
                    try:
                        if fmt == "JPG":
                            img.save(out_path, "JPEG", quality=95)
                        elif fmt == "WebP":
                            img.save(out_path, "WEBP", quality=95)
                        else:
                            img.save(out_path)
                        ok += 1
                    except Exception as e:
                        self._log(f"  保存失敗 [{fname}]: {e}")
                        skip += 1
                self.progress["value"] = idx
                self.update_idletasks()

        self._log(f"\n✓ 完了: 出力 {ok} / スキップ {skip}")
        self.progress_label.configure(text="完了")
        messagebox.showinfo("完了",
                            f"{ok} ファイルを出力しました\n保存先: {dst}")
        self.btn_start.configure(state="normal")


if __name__ == "__main__":
    app = App()
    app.mainloop()
