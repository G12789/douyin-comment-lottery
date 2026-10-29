# -*- coding: utf-8 -*-
"""抖音评论区抽奖核心逻辑：去重、排除作者、纯随机。"""
from __future__ import annotations

import csv
import io
import json
import random
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CommentEntry:
    user_id: str
    nickname: str
    content: str
    avatar_url: str
    is_follower: bool | None = None

    @property
    def dedupe_key(self) -> str:
        uid = (self.user_id or "").strip()
        if uid:
            return f"id:{uid}"
        return f"name:{(self.nickname or '').strip().lower()}"


def _norm_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _norm_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "已关注", "粉丝", "是"}:
        return True
    if text in {"0", "false", "no", "n", "未关注", "否"}:
        return False
    return None


def parse_records(raw: list[dict[str, Any]]) -> list[CommentEntry]:
    out: list[CommentEntry] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        nickname = _norm_text(item.get("nickname") or item.get("nick_name") or item.get("name"))
        content = _norm_text(item.get("content") or item.get("text") or item.get("comment"))
        if not nickname and not content:
            continue
        out.append(
            CommentEntry(
                user_id=_norm_text(item.get("user_id") or item.get("uid") or item.get("sec_uid")),
                nickname=nickname or "未知用户",
                content=content,
                avatar_url=_norm_text(
                    item.get("avatar_url") or item.get("avatar") or item.get("avatar_thumb")
                ),
                is_follower=_norm_bool(
                    item.get("is_follower")
                    if "is_follower" in item
                    else item.get("is_fans")
                    if "is_fans" in item
                    else item.get("followed_me")
                    if "followed_me" in item
                    else item.get("follower_status")
                    if "follower_status" in item
                    else item.get("fans_status")
                ),
            )
        )
    return out


def parse_json_text(text: str) -> list[CommentEntry]:
    text = text.strip()
    if not text:
        return []
    data = json.loads(text)
    if isinstance(data, dict):
        for key in ("comments", "data", "list", "items"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]
    if not isinstance(data, list):
        raise ValueError("JSON 必须是数组，或包含 comments/data/list 字段的对象")
    return parse_records(data)


def parse_csv_text(text: str) -> list[CommentEntry]:
    text = text.strip()
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, Any]] = []
    for row in reader:
        rows.append(dict(row))
    if not rows:
        raise ValueError("CSV 为空或缺少表头")
    return parse_records(rows)


def dedupe_comments(comments: list[CommentEntry]) -> tuple[list[CommentEntry], int]:
    seen: set[str] = set()
    kept: list[CommentEntry] = []
    removed = 0
    for c in comments:
        key = c.dedupe_key
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        kept.append(c)
    return kept, removed


def exclude_author(
    comments: list[CommentEntry],
    author_nickname: str = "",
    author_user_id: str = "",
) -> tuple[list[CommentEntry], int]:
    nick = author_nickname.strip().lower()
    uid = author_user_id.strip()
    kept: list[CommentEntry] = []
    removed = 0
    for c in comments:
        if uid and c.user_id == uid:
            removed += 1
            continue
        if nick and c.nickname.strip().lower() == nick:
            removed += 1
            continue
        kept.append(c)
    return kept, removed


def filter_keyword(comments: list[CommentEntry], keyword: str) -> tuple[list[CommentEntry], int]:
    kw = keyword.strip()
    if not kw:
        return comments, 0
    kept = [c for c in comments if kw in c.content]
    return kept, len(comments) - len(kept)


def filter_followers(comments: list[CommentEntry], require_follower: bool) -> tuple[list[CommentEntry], int]:
    if not require_follower:
        return comments, 0
    kept = [c for c in comments if c.is_follower is True]
    return kept, len(comments) - len(kept)


def draw_winners(
    comments: list[CommentEntry],
    count: int,
    *,
    seed: int | None = None,
) -> list[CommentEntry]:
    if count <= 0:
        raise ValueError("抽取人数必须大于 0")
    if len(comments) < count:
        raise ValueError(f"符合条件的评论只有 {len(comments)} 条，不够抽 {count} 人")
    rng = random.Random(seed)
    pool = comments.copy()
    rng.shuffle(pool)
    return pool[:count]


def run_lottery(
    comments: list[CommentEntry],
    *,
    winner_count: int,
    author_nickname: str = "",
    author_user_id: str = "",
    keyword: str = "",
    seed: int | None = None,
    require_follower: bool = False,
) -> dict[str, Any]:
    total_raw = len(comments)
    after_author, removed_author = exclude_author(comments, author_nickname, author_user_id)
    after_dedupe, removed_dup = dedupe_comments(after_author)
    after_follow, removed_not_follower = filter_followers(after_dedupe, require_follower)
    eligible, removed_kw = filter_keyword(after_follow, keyword)
    winners = draw_winners(eligible, winner_count, seed=seed)
    return {
        "stats": {
            "total_raw": total_raw,
            "removed_author": removed_author,
            "removed_duplicate": removed_dup,
            "removed_not_follower": removed_not_follower,
            "removed_keyword": removed_kw,
            "eligible": len(eligible),
            "winner_count": len(winners),
        },
        "winners": [asdict(w) for w in winners],
        "eligible_pool": [asdict(c) for c in eligible],
        "eligible_preview": [asdict(c) for c in eligible[:200]],
    }


def winners_to_csv(winners: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["nickname", "user_id", "content", "avatar_url", "is_follower"])
    writer.writeheader()
    for w in winners:
        writer.writerow(
            {
                "nickname": w.get("nickname", ""),
                "user_id": w.get("user_id", ""),
                "content": w.get("content", ""),
                "avatar_url": w.get("avatar_url", ""),
                "is_follower": w.get("is_follower", ""),
            }
        )
    return buf.getvalue()
