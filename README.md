# 抖音评论区抽奖工具（Douyin Comment Lottery）

一个**免费、开源、本地运行**的抖音视频评论区抽奖工具。自动抓取评论、按规则公平随机、滚动定格中奖者，方便做粉丝福利开奖并录屏。

> 纯本地运行，不上传任何数据到第三方服务器；支持本地网页版、图形界面一键版、命令行三种用法。

## 特性

- **自动抓取评论**：基于 Playwright 打开抖音网页版，监听评论接口并自动滚动加载，无需手动整理。
- **公平随机**：
  - 自动**排除作者本人**；
  - **同一用户只算一次**（按 user_id 去重）；
  - 纯随机抽取，支持**随机种子**复现结果；
  - 可选**关键词过滤**（如只抽评论含"想装"的用户）；
  - 可选**只抽已关注**的粉丝。
- **可视化开奖**：抽奖时快速滚动评论头像，最后定格中奖者，**适合录屏发抖音**，开奖过程公开透明。
- **结果展示与导出**：直接显示中奖者头像、昵称、评论，可一键导出 CSV（Excel 可打开）。
- **三种用法**：本地网页版、图形界面一键版、命令行，按需选择。

## 抽奖规则（默认）

| 规则 | 说明 |
|---|---|
| 排除作者 | 自动识别并排除视频作者本人，避免自己中奖 |
| 用户去重 | 同一用户多条评论只算一次 |
| 纯随机 | 使用 Python 随机数从符合条件的用户中抽取 |
| 关键词过滤 | 可选，仅评论包含指定关键词的用户参与（如"想装"） |
| 仅粉丝 | 可选，只抽已关注账号的用户（识别不到关注状态的会被过滤） |
| 随机种子 | 可选，填入相同数字可复现同一次开奖结果 |

## 环境要求

- Windows / macOS / Linux
- Python 3.10+
- 首次使用需要在自动打开的浏览器里**登录一次抖音网页版**（登录态保存在本机，下次免登录）

## 快速开始

### 方式一：图形界面一键版（推荐，全自动）

双击 `一键自动抽奖.bat`（Windows），或手动执行：

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 安装 Playwright 浏览器（首次较慢）
python -m playwright install chromium

# 3. 启动
python auto_lottery.py
```

在弹窗里：
1. 粘贴抖音视频链接（复制分享文字也可以，会自动提取链接）；
2. 设置抽取人数、关键词、是否只抽粉丝、滚动轮数；
3. 点击开始，程序会自动打开浏览器抓评论 → 滚动开奖 → 定格中奖者。

### 方式二：本地网页版

双击 `启动抽奖.bat`（Windows），或手动执行：

```bash
pip install -r requirements.txt
python app.py
```

然后浏览器打开 <http://127.0.0.1:8766>，把评论数据（JSON / CSV）粘贴进去，配置规则后点击抽奖。

### 方式三：命令行

```bash
python cli.py --input sample_comments.json --winners 5 --author 你的昵称 --keyword 想装
```

常用参数：

| 参数 | 说明 |
|---|---|
| `--input` | 评论 JSON 或 CSV 文件路径 |
| `--winners` | 抽取人数，默认 5 |
| `--author` | 作者昵称，排除自己 |
| `--author-id` | 作者 user_id（更准确） |
| `--keyword` | 评论关键词过滤，如"想装" |
| `--require-follower` | 只抽已关注账号 |
| `--seed` | 随机种子，可复现 |
| `--export` | 导出 CSV 路径 |

## 评论数据格式

如果不使用自动抓取，也可以把评论整理成 JSON 导入（参考 `sample_comments.json`）：

```json
[
  {"nickname": "小明", "user_id": "u001", "content": "想装", "avatar_url": "https://..."},
  {"nickname": "小红", "user_id": "u002", "content": "想装+1", "avatar_url": "https://..."}
]
```

也支持 CSV，表头：`nickname,user_id,content,avatar_url`。

## 目录结构

```
抖音评论抽奖工具/
├── app.py                # 本地网页版（Flask）
├── auto_lottery.py       # 图形界面一键版（Tkinter，全自动抓取+开奖）
├── cli.py                # 命令行版
├── douyin_scraper.py     # Playwright 评论抓取
├── lottery_core.py       # 抽奖核心逻辑（去重/过滤/随机）
├── requirements.txt      # 依赖
├── sample_comments.json  # 示例评论数据
├── 启动抽奖.bat           # Windows 启动网页版
└── 一键自动抽奖.bat       # Windows 一键全自动
```

## 技术栈

- [Flask](https://flask.palletsprojects.com/)：本地网页服务
- [Playwright](https://playwright.dev/)：浏览器自动化与评论抓取
- Tkinter / Pillow：图形界面与头像处理
- Python 标准库 `random`：公平随机抽取

## 常见问题

- **抓不到评论？** 请确认已在弹出的浏览器里登录抖音，并手动点开评论区；确认视频评论未被关闭。
- **评论很多抓不全？** 把"滚动加载轮数"调大，等待滚动完成。
- **登录态会泄露吗？** 登录信息只保存在本机 `.douyin_browser_profile` 目录，该目录已被 `.gitignore` 排除，不会被上传或提交。

## 免责声明

- 本工具仅用于个人学习与合法的粉丝福利抽奖，请勿用于刷量、骚扰、欺诈等违规用途。
- 工具通过浏览器自动化获取用户本人可见的评论数据，请遵守抖音 / 字节跳动的用户协议与相关法律法规；因不当使用产生的后果由使用者自行承担。

## License

[MIT](LICENSE)
