---
name: 内容创作系统项目状态
description: 项目已完成功能和待办事项清单，下次开发直接读此文档
type: project
---

# 内容创作系统 - 项目状态

> 最后更新: 2026-04-07
> GitHub: github.com/siuserxiaowei/content-creator-toolkit

---

## 已完成功能

### 基础架构
- [x] FastAPI + Vue3 + SQLAlchemy 全栈搭建
- [x] SQLite 数据库，7 张表（KOL/Content/Comment/MonitorLog/TopicAnalysis/GeneratedScript/NotifyConfig）
- [x] APScheduler 自动调度（每30分钟检查KOL，每小时自动分析）
- [x] 单文件 Vue3 SPA 前端（web/index.html）

### 多平台数据抓取
- [x] 抖音爬虫（原生 API，需要 Cookie）
- [x] B站爬虫（公开 API）
- [x] 小红书爬虫（Web API，需要 Cookie）
- [x] 微博爬虫（移动端 API）
- [x] yt-dlp 引擎支持 YouTube/TikTok 等 100+ 平台
- [x] Twitter/Instagram 降级方案（外部 media-downloader API）
- [x] URL 粘贴抓取 — 自动识别平台提取元数据
- [x] 批量 URL 抓取
- [x] 关键词搜索抓取（抖音/B站/小红书/微博）
- [x] 快手已移除（用户决定）

### KOL 管理
- [x] 添加/删除/编辑 KOL
- [x] 抓取 KOL 内容
- [x] 刷新 KOL 资料（粉丝数/头像/简介）
- [x] 监控开关（暂停/恢复）
- [x] 查看 KOL 的内容列表

### AI 选题分析（Gemini 2.5）
- [x] 单条内容分析（分类/Hook/互动评分/可复制性/为什么火/怎么抄）
- [x] 批量分析 KOL 全部内容
- [x] 博主画像分析（擅长内容/Hook模式/热门选题）
- [x] 多条内容对比分析（爆款vs普通/核心差异）
- [x] 分析报告导出（Markdown + JSON）
- [x] 分析失败时返回具体错误信息

### 前端界面
- [x] 首页仪表盘（统计/图表/KOL列表/URL抓取入口）
- [x] KOL 管理页（资料卡片/操作按钮）
- [x] 内容列表页（封面/标题/互动数据/分页/筛选）
- [x] 内容详情弹窗（元数据/AI分析结果/评论）
- [x] 选题分析页（博主画像/内容对比/趋势排行/导出按钮）
- [x] 脚本生成页（保留但用户不打算使用）
- [x] 搜索弹窗 + 保存搜索结果
- [x] 8 平台颜色标签和图表支持

### 其他
- [x] README 文档 + 系统截图
- [x] .env.example 配置模板（推荐 Gemini）
- [x] 分析引擎技术文档（docs/analysis-engine.md，可迁移）
- [x] 通知系统（Telegram/邮件，框架已搭建）

---

## 待办事项

### 高优先级（核心体验问题）

- [ ] **添加KOL时支持粘贴主页链接自动解析** — 目前必须手动填 sec_user_id，普通用户不知道怎么找。应该支持粘贴 `https://www.douyin.com/user/xxx` 自动提取 platform_uid
- [ ] **抖音评论抓取** — 当前返回 0 条，抖音评论接口有额外签名验证（X-Bogus/a_bogus），需要逆向或用 Playwright 方案
- [ ] **分析结果持久化** — 博主画像和对比分析目前是实时生成的，每次点都要调 LLM。应该缓存到数据库，避免重复消耗 API

### 中优先级（功能增强）

- [ ] **竞品对标分析** — 同时选多个 KOL 横向对比，分析策略差异
- [ ] **选题推荐** — 基于已分析的爆款内容，自动推荐下一条该做什么选题
- [ ] **趋势预警** — 某个领域突然出现爆款内容时推送通知
- [ ] **内容搜索过滤增强** — 按分析评分、Hook类型、选题分类筛选内容
- [ ] **数据可视化增强** — 选题分析页加图表（Hook类型分布、选题分类饼图、互动趋势线）

### 低优先级（锦上添花）

- [ ] **脚本生成优化或移除** — 用户表示不用这个功能，考虑从界面移除减少干扰
- [ ] **Cookie 管理界面** — 在前端直接配置平台 Cookie，而不是改 .env
- [ ] **定时报告** — 每周自动生成 KOL 分析报告推送到邮箱/Telegram
- [ ] **多用户支持** — 登录/权限（目前是单用户）

---

## 已知问题

- 抖音爬虫完全依赖 Cookie，Cookie 过期后需要手动更新
- yt-dlp 不支持抖音用户主页 URL，只能抓单个视频
- 系统环境有 SOCKS 代理（all_proxy=socks5://127.0.0.1:7891），需要安装 socksio
- 批量分析时如果某条内容已分析过会报 UNIQUE 约束错误（已有 is_analyzed 检查但 race condition 可能导致）
