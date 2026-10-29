# -*- coding: utf-8 -*-
"""命令行抽奖：适合录屏或终端直接看结果。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from lottery_core import parse_csv_text, parse_json_text, run_lottery, winners_to_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="抖音评论区抽奖")
    parser.add_argument("--input", required=True, help="评论 JSON 或 CSV 文件路径")
    parser.add_argument("--winners", type=int, default=5, help="抽取人数，默认 5")
    parser.add_argument("--author", default="", help="作者昵称，排除自己")
    parser.add_argument("--author-id", default="", help="作者 user_id")
    parser.add_argument("--keyword", default="", help="评论关键词过滤，如 想装")
    parser.add_argument("--require-follower", action="store_true", help="只抽已关注账号，识别不到关注状态的会过滤")
    parser.add_argument("--seed", type=int, default=None, help="随机种子，可复现")
    parser.add_argument("--export", default="", help="导出 CSV 路径")
    args = parser.parse_args()

    text = Path(args.input).read_text(encoding="utf-8")
    suffix = Path(args.input).suffix.lower()
    comments = parse_json_text(text) if suffix == ".json" else parse_csv_text(text)

    result = run_lottery(
        comments,
        winner_count=args.winners,
        author_nickname=args.author,
        author_user_id=args.author_id,
        keyword=args.keyword,
        seed=args.seed,
        require_follower=args.require_follower,
    )

    stats = result["stats"]
    print("=== 统计 ===")
    print(f"原始评论: {stats['total_raw']}")
    print(f"排除作者: {stats['removed_author']}")
    print(f"重复去重: {stats['removed_duplicate']}")
    print(f"未关注/无法识别过滤: {stats.get('removed_not_follower', 0)}")
    print(f"关键词过滤: {stats['removed_keyword']}")
    print(f"可抽人数: {stats['eligible']}")
    print(f"抽中人数: {stats['winner_count']}")
    print("\n=== 中奖名单 ===")
    for i, w in enumerate(result["winners"], 1):
        print(f"\n[{i}] {w['nickname']}")
        if w.get("user_id"):
            print(f"    ID: {w['user_id']}")
        print(f"    评论: {w['content']}")
        if w.get("avatar_url"):
            print(f"    头像: {w['avatar_url']}")

    if args.export:
        Path(args.export).write_text(winners_to_csv(result["winners"]), encoding="utf-8-sig")
        print(f"\n已导出 CSV: {args.export}")


if __name__ == "__main__":
    main()
