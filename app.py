# -*- coding: utf-8 -*-
"""
抖音评论区抽奖 — 本地网页版
双击 run.bat 或: python app.py
浏览器打开 http://127.0.0.1:8766
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path

from flask import Flask, Response, render_template_string, request

from lottery_core import parse_csv_text, parse_json_text, run_lottery, winners_to_csv

app = Flask(__name__)
BASE = Path(__file__).resolve().parent

INDEX_HTML = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>抖音评论抽奖</title>
  <style>
    :root { color-scheme: dark; }
    * { box-sizing: border-box; }
    body {
      margin: 0; font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
      background: #0b1220; color: #e2e8f0; min-height: 100vh;
    }
    .wrap { max-width: 980px; margin: 0 auto; padding: 28px 20px 60px; }
    h1 { margin: 0 0 8px; font-size: 28px; }
    .sub { color: #94a3b8; margin-bottom: 24px; line-height: 1.6; }
    .card {
      background: #111827; border: 1px solid #1f2937; border-radius: 16px;
      padding: 20px; margin-bottom: 18px;
    }
    label { display: block; font-size: 14px; color: #cbd5e1; margin: 12px 0 6px; }
    input, select, textarea {
      width: 100%; background: #0f172a; color: #f8fafc; border: 1px solid #334155;
      border-radius: 10px; padding: 10px 12px; font-size: 14px;
    }
    textarea { min-height: 220px; font-family: Consolas, monospace; resize: vertical; }
    .row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
    @media (max-width: 760px) { .row { grid-template-columns: 1fr; } }
    .btn {
      margin-top: 16px; background: linear-gradient(135deg, #f97316, #ea580c);
      color: white; border: 0; border-radius: 12px; padding: 14px 22px;
      font-size: 16px; font-weight: 700; cursor: pointer;
    }
    .btn:hover { filter: brightness(1.05); }
    .hint { font-size: 12px; color: #64748b; margin-top: 6px; line-height: 1.5; }
    .stats { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 16px; }
    .tag {
      background: #1e293b; border-radius: 999px; padding: 6px 12px;
      font-size: 13px; color: #cbd5e1;
    }
    .winners { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
    .winner {
      background: #0f172a; border: 1px solid #334155; border-radius: 14px; padding: 16px;
    }
    .winner-head { display: flex; gap: 12px; align-items: center; margin-bottom: 10px; }
    .avatar {
      width: 56px; height: 56px; border-radius: 50%; object-fit: cover;
      border: 2px solid #38bdf8; background: #1e293b;
    }
    .name { font-size: 18px; font-weight: 700; }
    .comment { color: #cbd5e1; line-height: 1.6; word-break: break-all; }
    .err { color: #fca5a5; background: #450a0a; padding: 12px; border-radius: 10px; }
    .actions { margin-top: 14px; display: flex; gap: 10px; flex-wrap: wrap; }
    .link-btn {
      display: inline-block; text-decoration: none; background: #1d4ed8; color: white;
      padding: 10px 14px; border-radius: 10px; font-size: 14px;
    }
    pre {
      background: #020617; border-radius: 10px; padding: 12px; overflow: auto;
      font-size: 12px; color: #94a3b8;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>抖音评论区抽奖</h1>
    <p class="sub">
      规则：排除作者本人 · 同一用户只算一次 · 纯随机 · 可选关键词过滤（如「想装」）<br>
      CSV 是什么？就是 Excel 能打开的表格文件，方便存档和发给别人；网页里会直接显示头像、昵称、评论。
    </p>

    {% if error %}
    <div class="card err">{{ error }}</div>
    {% endif %}

    <form class="card" method="post">
      <label>数据格式</label>
      <select name="format">
        <option value="json" {% if fmt=='json' %}selected{% endif %}>JSON（推荐）</option>
        <option value="csv" {% if fmt=='csv' %}selected{% endif %}>CSV 表格</option>
      </select>

      <label>评论数据（粘贴或从文件复制）</label>
      <textarea name="raw_data" placeholder='JSON 示例：
[
  {"nickname":"小明","user_id":"u001","content":"想装","avatar_url":"https://..."},
  {"nickname":"小红","user_id":"u002","content":"想装+1","avatar_url":"https://..."}
]

CSV 示例表头：
nickname,user_id,content,avatar_url'>{{ raw_data }}</textarea>
      <div class="hint">抖音没有公开评论 API，需先把评论整理成 JSON/CSV 再导入。见下方示例文件 sample_comments.json。</div>

      <div class="row">
        <div>
          <label>抽取人数</label>
          <input type="number" name="winner_count" min="1" max="999" value="{{ winner_count }}" />
        </div>
        <div>
          <label>作者昵称（排除自己）</label>
          <input type="text" name="author_nickname" value="{{ author_nickname }}" placeholder="你的抖音昵称" />
        </div>
        <div>
          <label>作者 user_id（可选，更准）</label>
          <input type="text" name="author_user_id" value="{{ author_user_id }}" placeholder="有就填，没有留空" />
        </div>
      </div>

      <div class="row">
        <div>
          <label>关键词过滤（可选）</label>
          <input type="text" name="keyword" value="{{ keyword }}" placeholder="例如：想装（留空=不过滤）" />
        </div>
        <div>
          <label>随机种子（可选，填数字可复现同一结果）</label>
          <input type="text" name="seed" value="{{ seed }}" placeholder="留空=每次不同" />
        </div>
        <div></div>
      </div>

      <button class="btn" type="submit">开始抽奖</button>
    </form>

    {% if result %}
    <div class="card">
      <h2 style="margin-top:0">抽奖结果</h2>
      <div class="stats">
        <span class="tag">原始 {{ result.stats.total_raw }} 条</span>
        <span class="tag">排除作者 {{ result.stats.removed_author }}</span>
        <span class="tag">去重 {{ result.stats.removed_duplicate }}</span>
        <span class="tag">关键词过滤 {{ result.stats.removed_keyword }}</span>
        <span class="tag">可抽池 {{ result.stats.eligible }} 人</span>
        <span class="tag">抽中 {{ result.stats.winner_count }} 人</span>
      </div>

      <div class="winners">
        {% for w in result.winners %}
        <div class="winner">
          <div class="winner-head">
            {% if w.avatar_url %}
            <img class="avatar" src="/avatar?url={{ w.avatar_url | urlencode }}" alt="" />
            {% else %}
            <div class="avatar"></div>
            {% endif %}
            <div>
              <div class="name">{{ w.nickname }}</div>
              {% if w.user_id %}<div class="hint">ID: {{ w.user_id }}</div>{% endif %}
            </div>
          </div>
          <div class="comment">{{ w.content }}</div>
        </div>
        {% endfor %}
      </div>

      <div class="actions">
        <a class="link-btn" href="/export.csv?payload={{ payload | urlencode }}">导出 CSV</a>
      </div>
    </div>
    {% endif %}

    <div class="card">
      <h3 style="margin-top:0">纯 Python 命令行也能用</h3>
      <pre>python cli.py --input sample_comments.json --winners 5 --author 你的昵称 --keyword 想装</pre>
    </div>
  </div>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(
        INDEX_HTML,
        error=None,
        result=None,
        payload="",
        fmt="json",
        raw_data="",
        winner_count=5,
        author_nickname="",
        author_user_id="",
        keyword="想装",
        seed="",
    )


@app.post("/")
def draw():
    fmt = request.form.get("format", "json")
    raw_data = request.form.get("raw_data", "")
    winner_count = int(request.form.get("winner_count", 5) or 5)
    author_nickname = request.form.get("author_nickname", "")
    author_user_id = request.form.get("author_user_id", "")
    keyword = request.form.get("keyword", "")
    seed_raw = request.form.get("seed", "").strip()
    seed = int(seed_raw) if seed_raw.isdigit() else None

    ctx = dict(
        fmt=fmt,
        raw_data=raw_data,
        winner_count=winner_count,
        author_nickname=author_nickname,
        author_user_id=author_user_id,
        keyword=keyword,
        seed=seed_raw,
    )

    try:
        comments = parse_json_text(raw_data) if fmt == "json" else parse_csv_text(raw_data)
        result = run_lottery(
            comments,
            winner_count=winner_count,
            author_nickname=author_nickname,
            author_user_id=author_user_id,
            keyword=keyword,
            seed=seed,
        )
        payload = json.dumps(result["winners"], ensure_ascii=False)
        return render_template_string(
            INDEX_HTML,
            error=None,
            result=result,
            payload=payload,
            **ctx,
        )
    except Exception as exc:
        return render_template_string(INDEX_HTML, error=str(exc), result=None, payload="", **ctx)


@app.get("/export.csv")
def export_csv():
    payload = request.args.get("payload", "")
    winners = json.loads(payload) if payload else []
    csv_text = winners_to_csv(winners)
    return Response(
        csv_text,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=douyin_lottery_winners.csv"},
    )


@app.get("/avatar")
def avatar_proxy():
    url = request.args.get("url", "")
    if not url.startswith("http"):
        return Response(status=404)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        data = resp.read()
        ctype = resp.headers.get("Content-Type", "image/jpeg")
    return Response(data, mimetype=ctype)


if __name__ == "__main__":
    print("打开浏览器访问: http://127.0.0.1:8766")
    app.run(host="127.0.0.1", port=8766, debug=False)
