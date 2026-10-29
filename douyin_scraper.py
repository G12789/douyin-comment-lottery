# -*- coding: utf-8 -*-
"""Playwright 自动抓取抖音网页版视频评论。"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from lottery_core import CommentEntry

PROFILE_DIR = Path(__file__).resolve().parent / ".douyin_browser_profile"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def _avatar_from_user(user: dict) -> str:
    if not isinstance(user, dict):
        return ""
    thumb = (
        user.get("avatar_thumb")
        or user.get("avatar_medium")
        or user.get("avatar_larger")
        or user.get("avatar_168x168")
        or user.get("avatar_300x300")
        or user.get("avatar")
        or {}
    )
    if isinstance(thumb, str):
        return thumb
    if isinstance(thumb, dict):
        urls = thumb.get("url_list") or thumb.get("urlList") or thumb.get("uri") or []
        if isinstance(urls, str):
            return urls
        if urls:
            return str(urls[0])
    for key in ("avatar_url", "avatarUrl", "avatar_uri"):
        val = user.get(key)
        if isinstance(val, str) and val:
            return val
    return ""


def _extract_follower_status(user: dict, raw_item: dict | None = None) -> bool | None:
    """尽量判断“评论者是否关注了当前账号”。识别不到返回 None，后续严格模式会过滤。"""
    raw_item = raw_item or {}
    candidates = []
    for src in (raw_item, user):
        if not isinstance(src, dict):
            continue
        for key in (
            "is_follower",
            "is_fans",
            "followed_me",
            "is_followed",
            "follower_status",
            "fans_status",
            "followed_by",
        ):
            if key in src:
                candidates.append(src.get(key))
        rel = src.get("relation") or src.get("follow_info") or {}
        if isinstance(rel, dict):
            for key in ("is_follower", "is_fans", "followed_me", "followed_by", "follower_status", "fans_status"):
                if key in rel:
                    candidates.append(rel.get(key))
    for val in candidates:
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            if val > 0:
                return True
            if val == 0:
                return False
        if isinstance(val, str):
            text = val.strip().lower()
            if text in {"1", "true", "yes", "粉丝", "已关注", "已关注你"}:
                return True
            if text in {"0", "false", "no", "未关注"}:
                return False
    return None


def parse_api_comment(item: dict) -> CommentEntry | None:
    if not isinstance(item, dict):
        return None
    text = str(item.get("text") or item.get("content") or "").strip()
    user = item.get("user") or {}
    nickname = str(user.get("nickname") or user.get("nick_name") or "").strip()
    uid = str(user.get("uid") or user.get("sec_uid") or user.get("short_id") or "").strip()
    avatar = _avatar_from_user(user)
    if not text and not nickname:
        return None
    return CommentEntry(
        user_id=uid,
        nickname=nickname or "未知用户",
        content=text,
        avatar_url=avatar,
        is_follower=_extract_follower_status(user, item),
    )


def _looks_like_comment(item: dict) -> bool:
    if not isinstance(item, dict):
        return False
    if item.get("text") or item.get("content"):
        return True
    user = item.get("user")
    return isinstance(user, dict) and bool(user.get("nickname") or user.get("nick_name"))


def _walk_comment_lists(value, depth: int = 0):
    """递归找抖音接口里的评论数组，兼容 data/comments/reply_list 等多层结构。"""
    if depth > 6:
        return
    if isinstance(value, list):
        if any(isinstance(x, dict) and _looks_like_comment(x) for x in value[:5]):
            yield value
        for item in value[:120]:
            yield from _walk_comment_lists(item, depth + 1)
    elif isinstance(value, dict):
        priority = (
            "comments",
            "comment_list",
            "reply_list",
            "reply_comments",
            "reply_comment_list",
            "reply_comment",
            "data",
            "list",
            "items",
        )
        for key in priority:
            if key in value:
                yield from _walk_comment_lists(value[key], depth + 1)
        for key, child in value.items():
            if key not in priority:
                yield from _walk_comment_lists(child, depth + 1)


def extract_comments_from_payload(data: dict) -> list[CommentEntry]:
    out: list[CommentEntry] = []
    if not isinstance(data, dict):
        return out

    buckets: list = []
    seen_bucket_ids: set[int] = set()
    for bucket in _walk_comment_lists(data):
        marker = id(bucket)
        if marker not in seen_bucket_ids:
            seen_bucket_ids.add(marker)
            buckets.extend(bucket)

    for item in buckets:
        parsed = parse_api_comment(item)
        if parsed:
            out.append(parsed)
        for reply_key in ("reply_comment", "reply_comments", "reply_comment_list"):
            replies = item.get(reply_key) if isinstance(item, dict) else None
            if isinstance(replies, list):
                for reply in replies:
                    rp = parse_api_comment(reply)
                    if rp:
                        out.append(rp)
    return out


def extract_author_from_payload(data: dict) -> tuple[str, str]:
    if not isinstance(data, dict):
        return "", ""
    aweme = data.get("aweme_detail") or data.get("aweme") or data.get("item") or data
    if not isinstance(aweme, dict):
        return "", ""
    author = aweme.get("author") or {}
    if not isinstance(author, dict):
        return "", ""
    nick = str(author.get("nickname") or "").strip()
    uid = str(author.get("uid") or author.get("sec_uid") or "").strip()
    return nick, uid


def scrape_douyin_comments(
    video_url: str,
    *,
    max_scroll_rounds: int = 40,
    idle_stop_rounds: int = 4,
    login_wait_seconds: int = 5,
    on_status: Callable[[str], None] | None = None,
) -> tuple[list[CommentEntry], str, str]:
    """
    打开抖音视频页，监听评论接口并滚动加载。
    返回 (评论列表, 作者昵称, 作者uid)
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("请先安装 playwright: pip install playwright && playwright install chromium") from exc

    def say(msg: str) -> None:
        if on_status:
            on_status(msg)

    collected: dict[str, CommentEntry] = {}
    author_nickname = ""
    author_user_id = ""

    def merge(items: list[CommentEntry]) -> int:
        added = 0
        for item in items:
            key = item.dedupe_key
            if key not in collected:
                collected[key] = item
                added += 1
        return added

    say("启动浏览器…")
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1360, "height": 920},
            user_agent=UA,
            locale="zh-CN",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--start-maximized",
            ],
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except Exception:
            pass

        def on_response(response) -> None:
            nonlocal author_nickname, author_user_id
            url = response.url
            if response.status != 200:
                return
            if not any(k in url for k in ("comment/list", "comment/list/", "comment/list/reply", "aweme/detail", "aweme/v1/web/general/search")):
                return
            try:
                data = response.json()
            except Exception:
                return
            if "comment/list" in url:
                merge(extract_comments_from_payload(data))
            nick, uid = extract_author_from_payload(data)
            if nick:
                author_nickname = nick
            if uid:
                author_user_id = uid

        page.on("response", on_response)

        say("打开视频页…")
        page.goto(video_url, wait_until="domcontentloaded", timeout=90000)
        page.wait_for_timeout(2500)

        say(f"等待 {login_wait_seconds}s，如需登录请在浏览器里完成…")
        elapsed = 0
        while elapsed < login_wait_seconds:
            remain = login_wait_seconds - elapsed
            say(f"等待中… 还剩 {remain}s 开始滚动，已捕获 {len(collected)} 条")
            step = min(5, remain)
            page.wait_for_timeout(step * 1000)
            elapsed += step

        # 尝试点开评论区。抖音 DOM 经常改，保留多套选择器和文字兜底。
        for selector in (
            '[data-e2e="feed-comment-icon"]',
            '[data-e2e*="comment"]',
            'button:has-text("评论")',
            'text=评论',
            '[class*="comment"]',
        ):
            try:
                loc = page.locator(selector).first
                if loc.count() and loc.is_visible(timeout=1200):
                    loc.click(timeout=2000)
                    page.wait_for_timeout(1200)
                    break
            except Exception:
                pass

        say("如果评论区没有自动打开，请现在手动点一下评论图标（等待 5 秒）…")
        page.wait_for_timeout(5000)

        idle_rounds = 0
        last_count = len(collected)
        for i in range(max_scroll_rounds):
            say(f"滚动加载评论 {i + 1}/{max_scroll_rounds}，已捕获 {len(collected)} 条")
            page.evaluate(
                """() => {
                    const selectors = [
                        '[data-e2e="comment-list"]',
                        '[data-e2e*="comment"]',
                        '[class*="CommentList"]',
                        '[class*="comment-list"]',
                        '[class*="comment-mainContent"]',
                        '[class*="related-video-card-comment"]',
                        '[role="dialog"]'
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && el.scrollHeight > el.clientHeight + 20) {
                            el.scrollTop = el.scrollHeight;
                            return;
                        }
                    }
                    window.scrollBy(0, 520);
                }"""
            )
            try:
                page.mouse.wheel(0, 560)
            except Exception:
                pass
            page.keyboard.press("End")
            page.wait_for_timeout(2300)

            current = len(collected)
            if current == last_count:
                idle_rounds += 1
                if idle_rounds >= idle_stop_rounds:
                    say("连续多轮没有新评论，停止滚动")
                    break
            else:
                idle_rounds = 0
                last_count = current

        # DOM 兜底：接口抓到多少都再合并当前可见评论，避免接口变动导致数量过少。
        say("合并页面可见评论作为兜底…")
        dom_items = page.evaluate(
            """() => {
                    const nodes = document.querySelectorAll('[class*="CommentItem"], [data-e2e="comment-item"], [class*="comment-item"], [class*="commentItem"], [class*="CommentContent"]');
                const out = [];
                nodes.forEach((node) => {
                    const nameEl = node.querySelector('[class*="user-name"], [class*="UserName"], [class*="nickname"], [class*="Nickname"], a');
                    const textEl = node.querySelector('[class*="content"], [class*="Content"], [class*="text"], [class*="Text"], p, span');
                    const imgEl = node.querySelector('img');
                    const nickname = nameEl ? nameEl.innerText.trim() : '';
                    const content = textEl ? textEl.innerText.trim() : '';
                    const avatar = imgEl ? (imgEl.currentSrc || imgEl.src || imgEl.getAttribute('data-src') || imgEl.getAttribute('data-original') || '') : '';
                        const allText = node.innerText || '';
                        const isFollower = /粉丝|已关注你|关注了你/.test(allText) ? true : null;
                        if (nickname || content) out.push({nickname, content, avatar_url: avatar, user_id: '', is_follower: isFollower});
                });
                return out;
            }"""
        )
        if isinstance(dom_items, list):
            before_dom = len(collected)
            for row in dom_items:
                if isinstance(row, dict):
                    merge(
                        [
                            CommentEntry(
                                user_id=str(row.get("user_id") or ""),
                                nickname=str(row.get("nickname") or "未知用户"),
                                content=str(row.get("content") or ""),
                                avatar_url=str(row.get("avatar_url") or ""),
                                is_follower=row.get("is_follower"),
                            )
                        ]
                    )
            if len(collected) > before_dom:
                say(f"DOM 兜底补充 {len(collected) - before_dom} 条评论")

        # 页面标题/作者区域再兜底
        if not author_nickname:
            try:
                author_nickname = page.locator('[data-e2e="video-author-name"]').first.inner_text(timeout=2000).strip()
            except Exception:
                pass

        context.close()

    if not collected:
        raise RuntimeError(
            "没有抓到任何评论。常见原因：\n"
            "1. 未登录抖音网页版，或登录后没有手动点开评论区\n"
            "2. 视频链接不对、视频不可见、评论被关闭，或评论太少\n"
            "3. 抖音页面/接口又更新了 — 先在弹出的浏览器里确认能看到评论，再重试\n"
            "提示：复制抖音分享出来的一整段文字也可以，工具会自动提取里面的视频链接。"
        )

    say(f"抓取完成，共 {len(collected)} 条（按用户去重前）")
    return list(collected.values()), author_nickname, author_user_id


def normalize_douyin_url(url: str) -> str:
    raw = url.strip()
    if not raw:
        raise ValueError("视频链接不能为空")
    # 抖音复制出来常是“复制此链接... https://v.douyin.com/xxx/ ...”，先抽出第一段 URL。
    m = re.search(r"https?://[^\s，。、“”\"'<>]+", raw)
    url = m.group(0) if m else raw
    url = url.strip().strip(".,，。!！?？)")
    if not re.match(r"^https?://", url):
        url = "https://" + url
    parts = urlsplit(url)
    if not parts.netloc:
        raise ValueError(f"未识别到有效抖音链接：{raw}")
    # 去掉片段，保留 query；避免中文/标点尾巴影响跳转。
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
