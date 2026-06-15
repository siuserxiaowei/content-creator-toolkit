# 内容创作系统 Content Creator Toolkit

<!-- SIUSER-REPO-GUIDE:START -->
## Repository Guide

### What This Repository Does

内容创作者工具箱：聚合创作者监控、AI 分析和选题自动化能力。

English summary: Creator toolkit for creator monitoring, AI analysis, and content automation workflows.

### Online Entry Points

- GitHub repository: https://github.com/siuserxiaowei/content-creator-toolkit
- Live / GitHub Pages: not configured for this repository
- Default branch: `main`
- Primary language: `Python`

### How To Read / Learn This Repository

1. 先读本 README，确认项目目标、在线入口和本地运行方式。
2. 按仓库目录从入口文件、数据文件、脚本和文档依次阅读。
3. 如果要修改内容，先小范围改动，再运行本 README 中的验证命令。

### Clone This Repository

```bash
git clone https://github.com/siuserxiaowei/content-creator-toolkit.git
cd content-creator-toolkit
```

### Run Or View Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Repository Map

| Path | Purpose |
| --- | --- |
| `README.md` | 项目入口说明，先读这里。 |
| `docs/` | 文档或 GitHub Pages 输出目录。 |
| `scripts/` | 构建、同步、生成或维护脚本。 |
| `tests/` | 测试用例或验证脚本。 |
| `DEV_LOG.md` | 项目文件。 |
| `api/` | 项目目录。 |
| `config/` | 项目目录。 |
| `core/` | 项目目录。 |
| `main.py` | 项目文件。 |
| `requirements.txt` | 项目文件。 |
| `storage/` | 项目目录。 |
| `web/` | 项目目录。 |

### Maintenance Notes

- Keep this README in sync when the project purpose, live link, or run commands change.
- Prefer small, focused commits when changing code, data, or generated pages.
- Run the relevant build or validation command before publishing changes.
- If this is a generated/static archive, update the source data first, then regenerate the public files.

### Privacy And Safety

- Do not commit API keys, tokens, passwords, cookies, private URLs, or internal account data.
- Keep private source material out of public GitHub Pages output unless it has been explicitly cleared for publication.
- When in doubt, run a quick secret scan such as `rg -n "token|secret|password|access_key|authorization"` before pushing.
<!-- SIUSER-REPO-GUIDE:END -->

<!-- SIUSER-SEO-INTRO:START -->

## 项目介绍 / Project Introduction

**中文介绍**：多平台内容创作者工具箱，支持选题、素材监控、AI 分析、内容生产和跨平台发布工作流。

**English**: A multi-platform creator toolkit for topic discovery, media monitoring, AI analysis, content production, and cross-platform publishing workflows.

**SEO 关键词 / SEO Keywords**: creator tools, content automation, AI analysis, social media, 内容创作者工具

<!-- SIUSER-SEO-INTRO:END -->

多平台 KOL 监控与 AI 选题分析系统。自动抓取主流社交平台的创作者内容数据，通过 AI 深度分析选题策略，帮助内容创作者发现爆款规律、提炼可复制的方法论。

![首页仪表盘](docs/screenshots/01_home.png)

## 核心功能

### 1. 多平台 KOL 监控

添加你关注的博主，系统自动抓取并持续监控他们的最新内容。

**支持平台：**
- 国内：抖音 / B站 / 小红书 / 微博
- 国际：YouTube / Twitter(X) / TikTok / Instagram
- 通用：粘贴任意视频链接，自动识别平台并提取元数据

![KOL管理](docs/screenshots/02_kol.png)

### 2. 内容数据采集

一键抓取博主的视频/帖子数据，包括标题、描述、封面、点赞数、评论数、转发量、播放量等完整元数据。支持关键词搜索和 URL 直接粘贴抓取。

![内容列表](docs/screenshots/03_contents.png)

### 3. AI 选题分析

基于 **Gemini 2.5** 大模型，对抓取的内容进行深度选题分析。

![选题分析](docs/screenshots/05_analysis.png)

#### 分析维度

**1. 博主画像分析**
- (a) 博主擅长什么内容
- (b) 视频的"钩子"（Hook）是什么
- (c) 哪些选题比较火

**2. 多条内容对比分析**
- (a) 哪些内容爆了
- (b) 哪些数据没那么好
- (c) 核心差异在哪里

分析结果支持以 **Markdown 文档**和 **JSON 格式**导出。

### 4. 内容详情

点击任一内容卡片，查看完整的元数据和 AI 分析结果。

![内容详情](docs/screenshots/04_detail.png)

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | FastAPI + SQLAlchemy (async) + SQLite |
| 前端 | Vue 3 + Tailwind CSS（单文件 SPA） |
| AI | Gemini 2.5 (通过 OpenAI 兼容接口) |
| 爬虫 | httpx + yt-dlp（多平台） |
| 调度 | APScheduler（自动监控） |

## 快速开始

### 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

需要额外安装 yt-dlp（用于 YouTube/Twitter 等国际平台抓取）：

```bash
brew install yt-dlp   # macOS
# 或
pip install yt-dlp
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

关键配置项：

```env
# AI 分析（必填，否则选题分析功能不可用）
OPENAI_API_KEY=你的Gemini API Key
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
OPENAI_MODEL=gemini-2.5-flash

# 平台 Cookie（按需填写，用于对应平台的数据抓取）
DOUYIN_COOKIE=你的抖音Cookie
BILIBILI_COOKIE=
XHS_COOKIE=
WEIBO_COOKIE=
```

> **获取 Gemini API Key：** 前往 [Google AI Studio](https://aistudio.google.com/apikey) 创建免费 API Key。

### 3. 启动服务

```bash
python main.py
```

浏览器访问 `http://localhost:8000` 即可使用。

## 费用说明

> **本系统运行涉及第三方 API 调用费用，请注意：**

- **AI 选题分析**需要消耗 LLM API 额度。当前使用 Gemini 2.5 Flash，Google 提供一定的免费额度，超出后会产生费用。
- 每次分析一条内容约消耗 1K-2K tokens。批量分析多条内容时费用会累积。
- 数据抓取本身不消耗 API 额度。
- 建议在 [Google AI Studio](https://aistudio.google.com/) 监控你的用量。

## 项目结构

```
├── main.py                 # 入口
├── config/settings.py      # 配置
├── api/                    # REST API
│   ├── kol.py             # KOL 管理
│   ├── crawl.py           # 数据抓取
│   ├── content.py         # 内容管理
│   ├── analysis.py        # 选题分析
│   └── monitor.py         # 监控仪表盘
├── core/
│   ├── crawler/           # 多平台爬虫
│   │   ├── douyin.py
│   │   ├── bilibili.py
│   │   ├── xhs.py
│   │   ├── weibo.py
│   │   └── ytdlp_engine.py  # YouTube/Twitter/TikTok/Instagram
│   ├── analyzer/          # AI 分析引擎
│   ├── monitor/           # 自动监控
│   └── scheduler/         # 定时任务
├── storage/               # 数据库模型
├── web/index.html         # 前端（单文件 Vue3 SPA）
└── data/                  # SQLite 数据库 & 导出文件
```

## License

MIT

<!-- SIUSER-CONTACT:START -->

## 联系我 / Contact

想交流 AI 工具、内容自动化、SEO、私域增长或项目合作，可以扫码加我微信。

For collaboration on AI tools, content automation, SEO, private-domain growth, or product experiments, scan the WeChat QR code below.

<img src="https://raw.githubusercontent.com/siuserxiaowei/siuserxiaowei/main/assets/contact/wechat-qrcode.jpg" width="180" alt="WeChat QR code / 微信二维码" />

**关键词 / Keywords**: creator tools, content automation, AI analysis, social media, AI tools, AI automation, GitHub Pages, SEO

<!-- SIUSER-CONTACT:END -->
