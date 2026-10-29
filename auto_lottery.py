# -*- coding: utf-8 -*-
"""
抖音评论全自动抽奖 — 一键完成：
1. 弹窗填链接和规则
2. 自动打开浏览器抓评论
3. 自动抽奖
4. 弹窗展示中奖者（头像+昵称+评论）

运行: python auto_lottery.py
或双击: 一键自动抽奖.bat
"""
from __future__ import annotations

import io
import random
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageTk

from douyin_scraper import normalize_douyin_url, scrape_douyin_comments
from lottery_core import CommentEntry, run_lottery, winners_to_csv


class AutoLotteryApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("抖音评论自动抽奖")
        self.root.geometry("560x520")
        self.root.resizable(False, False)
        self.root.configure(bg="#0f172a")

        self._photos: list[ImageTk.PhotoImage] = []
        self._avatar_img_cache: dict[tuple[str, int], Image.Image] = {}
        self._photo_cache: dict[tuple, ImageTk.PhotoImage] = {}
        self._build_form()

    def _label(self, parent: tk.Misc, text: str) -> None:
        tk.Label(parent, text=text, fg="#cbd5e1", bg="#0f172a", anchor="w").pack(fill="x", pady=(10, 4))

    def _build_form(self) -> None:
        wrap = tk.Frame(self.root, bg="#0f172a", padx=22, pady=18)
        wrap.pack(fill="both", expand=True)

        tk.Label(
            wrap,
            text="抖音评论自动抽奖",
            font=("Microsoft YaHei UI", 18, "bold"),
            fg="#f8fafc",
            bg="#0f172a",
        ).pack(anchor="w")
        tk.Label(
            wrap,
            text="脚本会自动打开浏览器抓评论 → 抽奖 → 弹窗显示结果",
            fg="#94a3b8",
            bg="#0f172a",
        ).pack(anchor="w", pady=(4, 12))

        self._label(wrap, "抖音视频链接")
        self.url_var = tk.StringVar()
        tk.Entry(wrap, textvariable=self.url_var, font=("Segoe UI", 11)).pack(fill="x", ipady=6)

        row1 = tk.Frame(wrap, bg="#0f172a")
        row1.pack(fill="x")
        col_a = tk.Frame(row1, bg="#0f172a")
        col_b = tk.Frame(row1, bg="#0f172a")
        col_a.pack(side="left", fill="x", expand=True, padx=(0, 8))
        col_b.pack(side="left", fill="x", expand=True)

        self._label(col_a, "你的昵称（排除自己，可留空自动识别）")
        self.author_var = tk.StringVar()
        tk.Entry(col_a, textvariable=self.author_var).pack(fill="x", ipady=5)

        self._label(col_b, "抽取人数")
        self.count_var = tk.StringVar(value="5")
        tk.Entry(col_b, textvariable=self.count_var).pack(fill="x", ipady=5)

        row2 = tk.Frame(wrap, bg="#0f172a")
        row2.pack(fill="x")
        col_c = tk.Frame(row2, bg="#0f172a")
        col_d = tk.Frame(row2, bg="#0f172a")
        col_c.pack(side="left", fill="x", expand=True, padx=(0, 8))
        col_d.pack(side="left", fill="x", expand=True)

        self._label(col_c, "评论关键词（如：想装，留空=不过滤）")
        self.keyword_var = tk.StringVar(value="想装")
        tk.Entry(col_c, textvariable=self.keyword_var).pack(fill="x", ipady=5)

        self._label(col_d, "滚动加载轮数（评论越多可加大）")
        self.scroll_var = tk.StringVar(value="40")
        tk.Entry(col_d, textvariable=self.scroll_var).pack(fill="x", ipady=5)

        self.require_follow_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            wrap,
            text="只抽已关注我的账号（识别不到关注状态的也过滤）",
            variable=self.require_follow_var,
            fg="#e2e8f0",
            bg="#0f172a",
            activebackground="#0f172a",
            activeforeground="#ffffff",
            selectcolor="#0f172a",
            anchor="w",
        ).pack(fill="x", pady=(12, 0))

        self.start_btn = tk.Button(
            wrap,
            text="开始：打开网页抓评论并抽奖",
            font=("Microsoft YaHei UI", 12, "bold"),
            bg="#ea580c",
            fg="white",
            activebackground="#f97316",
            activeforeground="white",
            relief="flat",
            padx=12,
            pady=10,
            command=self._on_start,
        )
        self.start_btn.pack(fill="x", pady=(18, 10))

        self.status_var = tk.StringVar(value="就绪")
        tk.Label(wrap, textvariable=self.status_var, fg="#38bdf8", bg="#0f172a", wraplength=500, justify="left").pack(
            anchor="w"
        )

        tk.Label(
            wrap,
            text="首次使用请在弹出的浏览器里登录抖音；如果评论区没自动弹开，请手动点一下评论图标。登录状态会保存在本机，下次不用重复登录。",
            fg="#64748b",
            bg="#0f172a",
            wraplength=500,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

    def _set_status(self, text: str) -> None:
        self.root.after(0, lambda: self.status_var.set(text))

    def _on_start(self) -> None:
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "请先粘贴抖音视频链接")
            return
        try:
            winner_count = int(self.count_var.get().strip() or "5")
            scroll_rounds = int(self.scroll_var.get().strip() or "40")
        except ValueError:
            messagebox.showwarning("提示", "抽取人数和滚动轮数必须是数字")
            return

        self.start_btn.config(state="disabled")
        self._set_status("准备开始…")

        def worker() -> None:
            try:
                video_url = normalize_douyin_url(url)
                comments, auto_author, auto_uid = scrape_douyin_comments(
                    video_url,
                    max_scroll_rounds=scroll_rounds,
                    on_status=self._set_status,
                )
                author = self.author_var.get().strip() or auto_author
                result = run_lottery(
                    comments,
                    winner_count=winner_count,
                    author_nickname=author,
                    author_user_id=auto_uid,
                    keyword=self.keyword_var.get().strip(),
                    require_follower=self.require_follow_var.get(),
                )
                self.root.after(0, lambda r=result, a=author: self._show_roll(r, a))
            except Exception as exc:
                err = str(exc)
                self.root.after(0, lambda e=err: messagebox.showerror("失败", e))
            finally:
                self.root.after(0, lambda: self.start_btn.config(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    def _fetch_avatar_image(self, url: str, size: int, fetch: bool = True) -> Image.Image | None:
        """下载并裁剪成圆形头像（纯 PIL，不碰 Tk，可在后台线程调用）。带缓存。
        fetch=False 时只查缓存、绝不联网（给滚动主线程用，防止卡顿）。"""
        if not url:
            return None
        key = (url, size)
        cached = self._avatar_img_cache.get(key)
        if cached is not None:
            return cached
        if not fetch:
            return None
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
            # 抖音头像有时是非正方形，先居中裁成正方形，避免被压扁或只显示一角。
            w, h = img.size
            side = min(w, h)
            left = (w - side) // 2
            top = (h - side) // 2
            img = img.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
            img.putalpha(mask)
            self._avatar_img_cache[key] = img
            return img
        except Exception:
            return None

    def _load_avatar(self, url: str, size: int = 64) -> ImageTk.PhotoImage | None:
        img = self._fetch_avatar_image(url, size)
        if img is None:
            return None
        photo = ImageTk.PhotoImage(img)
        self._photos.append(photo)
        return photo

    def _avatar_placeholder(self, parent: tk.Misc, nickname: str, size: int = 64) -> tk.Canvas:
        canvas = tk.Canvas(parent, width=size, height=size, bg="#0f172a", highlightthickness=0)
        canvas.create_oval(2, 2, size - 2, size - 2, fill="#1e293b", outline="#334155", width=2)
        char = (nickname or "?").strip()[:1] or "?"
        canvas.create_text(size // 2, size // 2, text=char, fill="#cbd5e1", font=("Microsoft YaHei UI", 18, "bold"))
        return canvas

    def _circle_placeholder_photo(self, size: int) -> ImageTk.PhotoImage:
        """灰色圆形占位图（用于滚动时还没下载好的头像）。整程序共用一张，省内存。"""
        key = ("__circle__", size)
        photo = self._photo_cache.get(key)
        if photo is None:
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.ellipse((1, 1, size - 2, size - 2), fill=(30, 41, 59, 255), outline=(51, 65, 85, 255), width=2)
            photo = ImageTk.PhotoImage(img)
            self._photo_cache[key] = photo
        return photo

    def _roll_avatar_photo(self, item: dict[str, Any], size: int) -> ImageTk.PhotoImage:
        """滚动时取头像：只用已缓存的（不联网），没有就用灰圆占位。PhotoImage 复用，帧率稳。"""
        url = str(item.get("avatar_url") or "")
        if url:
            key = (url, size)
            photo = self._photo_cache.get(key)
            if photo is not None:
                return photo
            img = self._fetch_avatar_image(url, size, fetch=False)
            if img is not None:
                photo = ImageTk.PhotoImage(img)
                self._photo_cache[key] = photo
                return photo
        return self._circle_placeholder_photo(size)

    def _show_roll(self, result: dict[str, Any], author: str) -> None:
        """先滚动候选评论，再定格中奖者，方便录抖音视频。"""
        stats = result["stats"]
        winners: list[dict[str, Any]] = result["winners"]
        pool: list[dict[str, Any]] = result.get("eligible_pool") or winners
        if not pool:
            self._show_winners(result, author)
            return

        popup = tk.Toplevel(self.root)
        popup.title("正在随机抽取")
        popup.geometry("820x620")
        popup.configure(bg="#020617")
        popup.transient(self.root)
        popup.grab_set()

        # 滚动期间在后台把头像下载好：中奖者用大图（定格揭晓用），候选池用小图（滚动翻动用）。
        reveal_size = 96
        roll_size = 44

        def _preload() -> None:
            for w in winners:
                self._fetch_avatar_image(str(w.get("avatar_url") or ""), reveal_size)
            seen: set[str] = set()
            for it in pool:
                u = str(it.get("avatar_url") or "")
                if u and u not in seen:
                    seen.add(u)
                    self._fetch_avatar_image(u, roll_size)
                    if len(seen) >= 150:
                        break

        threading.Thread(target=_preload, daemon=True).start()

        tk.Label(
            popup,
            text=(
                f"已抓到 {stats['total_raw']} 条评论 · "
                f"过滤未关注/无法识别 {stats.get('removed_not_follower', 0)} · "
                f"可抽 {stats['eligible']} 人"
            ),
            font=("Microsoft YaHei UI", 18, "bold"),
            fg="#f8fafc",
            bg="#020617",
        ).pack(anchor="w", padx=24, pady=(22, 6))
        tk.Label(
            popup,
            text="正在快速滚动评论名单，最后随机定格中奖者",
            font=("Microsoft YaHei UI", 12),
            fg="#94a3b8",
            bg="#020617",
        ).pack(anchor="w", padx=24, pady=(0, 14))

        hl_frame = tk.Frame(popup, bg="#111827")
        hl_frame.pack(fill="x", padx=24, pady=(0, 14))
        hl_av = tk.Label(hl_frame, bg="#111827")
        hl_av.pack(side="left", padx=(14, 0), pady=12)
        highlight = tk.Label(
            hl_frame,
            text="准备开始...",
            font=("Microsoft YaHei UI", 24, "bold"),
            fg="#fb923c",
            bg="#111827",
            padx=14,
            pady=14,
            wraplength=660,
            justify="left",
            anchor="w",
        )
        highlight.pack(side="left", fill="x", expand=True)

        list_frame = tk.Frame(popup, bg="#020617")
        list_frame.pack(fill="both", expand=True, padx=24, pady=(0, 10))
        rows: list[tuple[tk.Label, tk.Label]] = []
        for _ in range(9):
            rf = tk.Frame(list_frame, bg="#0f172a")
            rf.pack(fill="x", pady=4)
            av = tk.Label(rf, bg="#0f172a")
            av.pack(side="left", padx=(8, 0), pady=4)
            txt = tk.Label(
                rf,
                text="",
                font=("Microsoft YaHei UI", 13),
                fg="#cbd5e1",
                bg="#0f172a",
                anchor="w",
                padx=10,
                pady=8,
                justify="left",
            )
            txt.pack(side="left", fill="x", expand=True)
            rows.append((av, txt))

        btn_row = tk.Frame(popup, bg="#020617", padx=24, pady=12)
        btn_row.pack(fill="x")

        rng = random.Random()
        frames = 72

        def fmt(item: dict[str, Any], idx: int | None = None) -> str:
            name = str(item.get("nickname") or "未知用户")
            text = str(item.get("content") or "").replace("\n", " ")
            prefix = f"#{idx} " if idx is not None else ""
            return f"{prefix}{name}：{text[:46]}"

        def tick(step: int = 0) -> None:
            if not popup.winfo_exists():
                return
            if step < frames:
                sample = [rng.choice(pool) for _ in rows]
                for (av, txt), item in zip(rows, sample):
                    photo = self._roll_avatar_photo(item, roll_size)
                    av.config(image=photo)
                    av.image = photo
                    txt.config(text=fmt(item))
                hitem = rng.choice(pool)
                hphoto = self._roll_avatar_photo(hitem, roll_size)
                hl_av.config(image=hphoto)
                hl_av.image = hphoto
                highlight.config(text=fmt(hitem))
                delay = 35 + int(step * 1.6)
                self.root.after(delay, lambda s=step + 1: tick(s))
                return

            # 定格揭晓：把滚动名单换成中奖者大头像卡片，直接在本窗口展示，方便录屏。
            hl_av.config(image="")
            hl_av.image = None
            hl_frame.config(bg="#166534")
            hl_av.config(bg="#166534")
            highlight.config(text=f"🎉 恭喜中奖！共 {len(winners)} 位", fg="#ffffff", bg="#166534")
            for child in list_frame.winfo_children():
                child.destroy()
            rows.clear()

            rcanvas = tk.Canvas(list_frame, bg="#020617", highlightthickness=0)
            rscroll = ttk.Scrollbar(list_frame, orient="vertical", command=rcanvas.yview)
            rbody = tk.Frame(rcanvas, bg="#020617")
            rbody.bind("<Configure>", lambda e: rcanvas.configure(scrollregion=rcanvas.bbox("all")))
            rwin = rcanvas.create_window((0, 0), window=rbody, anchor="nw")
            rcanvas.bind("<Configure>", lambda e: rcanvas.itemconfigure(rwin, width=e.width))
            rcanvas.configure(yscrollcommand=rscroll.set)
            rcanvas.pack(side="left", fill="both", expand=True)
            rscroll.pack(side="right", fill="y")
            popup.bind("<MouseWheel>", lambda e: rcanvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

            for i, w in enumerate(winners, 1):
                card = tk.Frame(
                    rbody, bg="#0f172a", padx=14, pady=12,
                    highlightbackground="#22c55e", highlightthickness=1,
                )
                card.pack(fill="x", padx=8, pady=6)
                top = tk.Frame(card, bg="#0f172a")
                top.pack(fill="x")
                photo = self._load_avatar(str(w.get("avatar_url") or ""), reveal_size)
                if photo:
                    tk.Label(top, image=photo, bg="#0f172a").pack(side="left")
                else:
                    self._avatar_placeholder(top, str(w.get("nickname") or ""), reveal_size).pack(side="left")
                info = tk.Frame(top, bg="#0f172a")
                info.pack(side="left", padx=14, fill="x", expand=True)
                tk.Label(
                    info,
                    text=f"#{i}  {w.get('nickname', '') or '未知用户'}",
                    font=("Microsoft YaHei UI", 17, "bold"),
                    fg="#f8fafc",
                    bg="#0f172a",
                ).pack(anchor="w")
                content = str(w.get("content") or "").replace("\n", " ")
                if content:
                    tk.Label(
                        info,
                        text=content,
                        font=("Microsoft YaHei UI", 12),
                        fg="#cbd5e1",
                        bg="#0f172a",
                        wraplength=560,
                        justify="left",
                    ).pack(anchor="w", pady=(6, 0))

            # 停留在结果窗口，方便录屏；需要 ID/导出再点详细结果。
            if not btn_row.winfo_children():
                tk.Button(
                    btn_row,
                    text="查看详细结果 / 导出",
                    command=lambda: self._show_winners(result, author),
                    bg="#1d4ed8",
                    fg="white",
                    relief="flat",
                    padx=18,
                    pady=9,
                ).pack(side="left")
                tk.Button(
                    btn_row,
                    text="关闭",
                    command=popup.destroy,
                    bg="#334155",
                    fg="white",
                    relief="flat",
                    padx=18,
                    pady=9,
                ).pack(side="left", padx=10)

        tick()

    def _show_winners(self, result: dict[str, Any], author: str) -> None:
        stats = result["stats"]
        winners: list[dict[str, Any]] = result["winners"]

        popup = tk.Toplevel(self.root)
        popup.title("抽奖结果")
        popup.geometry("760x620")
        popup.configure(bg="#020617")
        popup.transient(self.root)
        popup.grab_set()

        header = tk.Frame(popup, bg="#020617", padx=20, pady=16)
        header.pack(fill="x")
        tk.Label(
            header,
            text=f"恭喜抽中 {len(winners)} 人",
            font=("Microsoft YaHei UI", 20, "bold"),
            fg="#f8fafc",
            bg="#020617",
        ).pack(anchor="w")
        tk.Label(
            header,
            text=(
                f"原始 {stats['total_raw']} 条 · 排除作者 {stats['removed_author']} · "
                f"去重 {stats['removed_duplicate']} · 关键词过滤 {stats['removed_keyword']} · "
                f"过滤未关注/无法识别 {stats.get('removed_not_follower', 0)} · "
                f"可抽 {stats['eligible']} 人"
                + (f" · 作者：{author}" if author else "")
            ),
            fg="#94a3b8",
            bg="#020617",
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

        canvas = tk.Canvas(popup, bg="#020617", highlightthickness=0)
        scroll = ttk.Scrollbar(popup, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg="#020617")
        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=body, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=8)
        scroll.pack(side="right", fill="y", pady=8)

        def on_mousewheel(event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        popup.bind("<MouseWheel>", on_mousewheel)

        for idx, w in enumerate(winners, 1):
            card = tk.Frame(body, bg="#0f172a", padx=14, pady=12, highlightbackground="#334155", highlightthickness=1)
            card.pack(fill="x", padx=12, pady=8)

            top = tk.Frame(card, bg="#0f172a")
            top.pack(fill="x")
            photo = self._load_avatar(w.get("avatar_url", ""))
            if photo:
                tk.Label(top, image=photo, bg="#0f172a").pack(side="left")
            else:
                self._avatar_placeholder(top, str(w.get("nickname") or "")).pack(side="left")

            info = tk.Frame(top, bg="#0f172a")
            info.pack(side="left", padx=12)
            tk.Label(
                info,
                text=f"#{idx}  {w.get('nickname', '')}",
                font=("Microsoft YaHei UI", 15, "bold"),
                fg="#f8fafc",
                bg="#0f172a",
            ).pack(anchor="w")
            if w.get("user_id"):
                tk.Label(info, text=f"ID: {w['user_id']}", fg="#64748b", bg="#0f172a").pack(anchor="w")

            tk.Label(
                card,
                text=w.get("content", ""),
                fg="#cbd5e1",
                bg="#0f172a",
                wraplength=620,
                justify="left",
                font=("Microsoft YaHei UI", 12),
            ).pack(anchor="w", pady=(10, 0))

        def export_csv() -> None:
            from tkinter import filedialog

            path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV 文件", "*.csv")],
                initialfile="douyin_winners.csv",
            )
            if path:
                with open(path, "w", encoding="utf-8-sig", newline="") as f:
                    f.write(winners_to_csv(winners))
                messagebox.showinfo("已导出", f"保存到:\n{path}")

        btn_row = tk.Frame(popup, bg="#020617", padx=20, pady=12)
        btn_row.pack(fill="x")
        tk.Button(
            btn_row,
            text="导出 CSV",
            command=export_csv,
            bg="#1d4ed8",
            fg="white",
            relief="flat",
            padx=16,
            pady=8,
        ).pack(side="left")
        tk.Button(
            btn_row,
            text="关闭",
            command=popup.destroy,
            bg="#334155",
            fg="white",
            relief="flat",
            padx=16,
            pady=8,
        ).pack(side="left", padx=8)

        self._set_status(f"抽奖完成，已抽中 {len(winners)} 人")

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    AutoLotteryApp().run()
