# 开发日志

## 2026-04-06 - Sprint 3: 竞品对标全面补齐

### 竞品调研
调研了新榜、蝉妈妈、灰豚数据、飞瓜数据、即梦、有米有数、vidIQ、Social Blade等10+竞品，提炼核心UX模式。

### 新增后端API
- `POST /crawl/profile` — 抓取KOL资料（粉丝数/头像/简介），B站+微博已实现
- `POST /crawl/save` — 保存搜索结果到内容库（kol_id改为可选）
- `GET /contents/{id}/detail` — 内容完整详情（含评论+AI分析结果）
- `GET /monitor/dashboard` 增强 — 新增total_contents/analyzed_contents/platform_stats/topic_categories/recent_engagement

### 爬虫增强
- BaseCrawler新增 `fetch_user_profile()` 方法
- BilibiliCrawler实现用户资料抓取（acc/info + stat fallback）
- WeiboCrawler实现用户资料抓取（m.weibo.cn API）

### 前端新功能
- **KOL资料卡增强**: 头像+粉丝数+简介+「刷新资料」按钮
- **内容详情弹窗**: 点击标题展开完整信息（描述/评论/AI分析/4项数据指标）
- **数据可视化**: Chart.js图表 — 平台内容分布饼图 + 互动对比柱状图
- **搜索结果可保存**: 每条搜索结果旁有「保存」按钮，一键入库
- **Dashboard增强**: 统计卡片改为"监控中/总内容/已分析/发现更新"

### 数据模型变更
- Content.kol_id 改为可选（nullable=True），支持无KOL关联的搜索保存内容

---

## 2026-04-06 - Sprint 2: 前端交互重做 + 爬取API

### 新增
- **爬取操作API** (`api/crawl.py`)
  - `POST /api/v1/crawl/kol` - 手动抓取KOL最新内容（入库去重）
  - `POST /api/v1/crawl/search` - 关键词搜索各平台内容（已验证B站可用）
  - `POST /api/v1/crawl/comments` - 抓取指定内容的评论
- **前端全面重做** (`web/index.html`)
  - 仪表盘新增快速操作区（添加KOL/搜索内容/生成脚本/全量检查）
  - KOL卡片新增操作按钮：抓取内容 / 查看内容 / 分析选题 / 暂停监控 / 删除
  - 内容列表新增：分析选题按钮 / 抓评论按钮 / 搜索抓取入口 / 分页
  - 新增搜索弹窗：选平台+输关键词，实时搜索各平台内容
  - 所有空状态都有引导提示和操作按钮
  - Toast通知系统（操作反馈）
  - 添加KOL时自动生成主页URL + 各平台UID获取提示
  - 平台名中文化（xhs→小红书, douyin→抖音 等）

### 修复
- Python 3.9 兼容性（`from __future__ import annotations` + `Optional[X]`）
- SQLAlchemy `metadata` 保留字冲突（改为 `extra_data`）
- OpenAI客户端懒加载（避免无API key时启动报错）

---

## 2026-04-06 - Sprint 1: 全系统搭建

### 已完成

#### 1. 项目基础设施
- 项目目录结构（config/core/storage/api/web/data/logs/tests/scripts）
- pydantic-settings 配置管理，自动读取 .env
- loguru 日志系统（控制台+文件+错误分离，按天轮转，保留30天）
- SQLAlchemy async + aiosqlite 数据库层
- 7张数据表：KOL / Content / Comment / MonitorLog / TopicAnalysis / GeneratedScript / NotifyConfig

#### 2. KOL监控模块 (`core/monitor/`)
- MonitorEngine 监控引擎：检查KOL主页是否有新内容
- 支持手动触发和定时调度两种模式
- 新内容自动入库 + 去重（platform + content_id 唯一索引）
- 每次检查记录 MonitorLog（成功/失败/有变更/无变更）

#### 3. 多平台爬虫 (`core/crawler/`)
- BaseCrawler 抽象基类：统一接口（fetch_user_posts / fetch_post_detail / fetch_post_comments / search_posts）
- 5个平台实现：
  - **小红书** (xhs.py) - Web API，支持笔记列表/详情/评论/搜索
  - **抖音** (douyin.py) - Web API，支持视频列表/详情/评论/搜索
  - **B站** (bilibili.py) - 公开API，支持UP主视频/详情/评论/搜索
  - **微博** (weibo.py) - 移动端API，支持微博列表/详情/评论/搜索
  - **快手** (kuaishou.py) - GraphQL API，支持视频列表/详情/评论/搜索
- CrawlerFactory 工厂模式，按平台名自动返回爬虫实例（单例）
- tenacity 重试机制，httpx 异步HTTP客户端

#### 4. 通知系统 (`core/notify.py`)
- 基于 apprise，支持 Telegram / Email / 50+渠道
- 新内容通知 / 分析完成通知 / 脚本生成通知
- 支持动态添加通知渠道

#### 5. 媒体下载 (`core/downloader/`)
- 优先调用远程媒体下载器（用户已有项目）
- 本地 yt-dlp 兜底下载
- 批量下载接口

#### 6. 选题分析引擎 (`core/analyzer/`)
- LLM 驱动（OpenAI API，支持自定义 base_url）
- 分析维度：选题分类/关键词/Hook类型/内容结构/互动率评分/可复制性评分
- 结合热门评论辅助分析
- 支持单条分析和KOL批量分析
- 选题趋势排行（按可复制性排序）

#### 7. 视频脚本生成 (`core/scriptgen/`)
- LLM 驱动，根据选题+平台+时长生成完整脚本
- 输出结构：Hook(前3秒) / 正文 / CTA / 画面建议 / BGM建议
- 支持引用已分析内容作为参考
- 根据目标平台调整风格（抖音快节奏 vs B站深度）

#### 8. 任务调度 (`core/scheduler/`)
- APScheduler 异步调度器
- 每30分钟自动检查所有KOL
- 每小时自动分析未分析的内容

#### 9. RESTful API (`api/`)
- KOL管理：增删改查 + 统计
- 内容管理：分页列表 + 评论查看
- 监控管理：手动触发检查 + 日志查看 + 仪表盘
- 选题分析：触发分析 + 趋势排行
- 脚本生成：生成 / 列表 / 状态管理

#### 10. Web管理后台 (`web/index.html`)
- Vue3 + Tailwind CSS 单页应用
- 5个页面：仪表盘 / KOL管理 / 内容列表 / 选题分析 / 视频脚本
- 支持添加KOL、触发检查、分析选题、生成脚本、一键复制
- 响应式设计

#### 11. 运维脚本
- `scripts/setup.sh` - 一键安装环境
- `scripts/start.sh` - 一键启动服务

### 待办（下一阶段）
- [ ] 爬虫反爬对抗增强（签名生成、指纹伪装、IP代理池）
- [ ] 平台Cookie管理界面（Web端可直接粘贴Cookie）
- [ ] 内容对比/diff功能（类changedetection.io）
- [ ] 评论词云分析
- [ ] 脚本导出（Markdown/PDF）
- [ ] Docker Compose 一键部署
- [ ] 数据导出（CSV/Excel）
- [ ] 多用户权限管理
