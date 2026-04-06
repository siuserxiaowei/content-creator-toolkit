"""数据模型 - 所有业务实体"""

from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from storage.database import Base


class KOL(Base):
    """KOL/博主信息"""
    __tablename__ = "kols"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), comment="博主名称")
    platform: Mapped[str] = mapped_column(String(20), comment="平台: xhs/douyin/bilibili/weibo/kuaishou")
    platform_uid: Mapped[str] = mapped_column(String(200), comment="平台用户ID")
    homepage_url: Mapped[str] = mapped_column(String(500), comment="主页URL")
    avatar_url: Mapped[str] = mapped_column(String(500), default="")
    follower_count: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text, default="", comment="博主简介")
    tags: Mapped[str] = mapped_column(String(500), default="", comment="标签，逗号分隔")
    is_monitoring: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否正在监控")
    check_interval: Mapped[int] = mapped_column(Integer, default=3600, comment="检查间隔(秒)")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contents: Mapped[list["Content"]] = relationship(back_populates="kol", cascade="all, delete-orphan")
    monitor_logs: Mapped[list["MonitorLog"]] = relationship(back_populates="kol", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_kol_platform_uid", "platform", "platform_uid", unique=True),
    )


class Content(Base):
    """爬取的内容（文章/视频/笔记）"""
    __tablename__ = "contents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kol_id: Mapped[int] = mapped_column(ForeignKey("kols.id"), comment="关联KOL")
    platform: Mapped[str] = mapped_column(String(20))
    content_type: Mapped[str] = mapped_column(String(20), comment="类型: video/article/note/short_video")
    content_id: Mapped[str] = mapped_column(String(200), comment="平台内容ID")
    title: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(500))
    cover_url: Mapped[str] = mapped_column(String(500), default="")
    media_urls: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="媒体文件URL列表")
    tags: Mapped[str] = mapped_column(String(500), default="", comment="内容标签")
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    share_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="原始数据JSON")
    is_downloaded: Mapped[bool] = mapped_column(Boolean, default=False)
    is_analyzed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    kol: Mapped["KOL"] = relationship(back_populates="contents")
    comments: Mapped[list["Comment"]] = relationship(back_populates="content", cascade="all, delete-orphan")
    analysis: Mapped["TopicAnalysis | None"] = relationship(back_populates="content", uselist=False)

    __table_args__ = (
        Index("idx_content_platform_id", "platform", "content_id", unique=True),
        Index("idx_content_kol", "kol_id"),
    )


class Comment(Base):
    """评论数据"""
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"))
    comment_id: Mapped[str] = mapped_column(String(200), comment="平台评论ID")
    parent_comment_id: Mapped[str] = mapped_column(String(200), default="", comment="父评论ID（回复）")
    user_name: Mapped[str] = mapped_column(String(100), default="")
    user_id: Mapped[str] = mapped_column(String(200), default="")
    text: Mapped[str] = mapped_column(Text)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    content: Mapped["Content"] = relationship(back_populates="comments")


class MonitorLog(Base):
    """监控日志 - 记录每次检查结果"""
    __tablename__ = "monitor_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    kol_id: Mapped[int] = mapped_column(ForeignKey("kols.id"))
    check_type: Mapped[str] = mapped_column(String(20), comment="检查类型: scheduled/manual")
    status: Mapped[str] = mapped_column(String(20), comment="结果: success/failed/changed/unchanged")
    new_contents_count: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    kol: Mapped["KOL"] = relationship(back_populates="monitor_logs")


class TopicAnalysis(Base):
    """选题分析结果"""
    __tablename__ = "topic_analyses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("contents.id"), unique=True)
    topic_category: Mapped[str] = mapped_column(String(100), default="", comment="选题分类")
    topic_keywords: Mapped[str] = mapped_column(String(500), default="", comment="关键词")
    hook_type: Mapped[str] = mapped_column(String(100), default="", comment="开头hook类型")
    structure_summary: Mapped[str] = mapped_column(Text, default="", comment="内容结构摘要")
    engagement_score: Mapped[float] = mapped_column(Float, default=0.0, comment="互动率评分")
    replicability_score: Mapped[float] = mapped_column(Float, default=0.0, comment="可复制性评分")
    analysis_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="详细分析JSON")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    content: Mapped["Content"] = relationship(back_populates="analysis")


class GeneratedScript(Base):
    """生成的视频脚本"""
    __tablename__ = "generated_scripts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    topic: Mapped[str] = mapped_column(String(200), comment="选题")
    style_reference: Mapped[str] = mapped_column(String(200), default="", comment="参考风格/KOL")
    target_platform: Mapped[str] = mapped_column(String(20), default="", comment="目标平台")
    target_duration: Mapped[int] = mapped_column(Integer, default=60, comment="目标时长(秒)")
    hook: Mapped[str] = mapped_column(Text, default="", comment="开头hook")
    body: Mapped[str] = mapped_column(Text, default="", comment="正文")
    cta: Mapped[str] = mapped_column(Text, default="", comment="结尾CTA")
    full_script: Mapped[str] = mapped_column(Text, comment="完整脚本")
    source_content_ids: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="参考内容ID")
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", comment="状态: draft/reviewed/final")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NotifyConfig(Base):
    """通知配置"""
    __tablename__ = "notify_configs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    channel: Mapped[str] = mapped_column(String(50), comment="渠道: telegram/email/webhook/wechat")
    config: Mapped[dict] = mapped_column(JSON, comment="渠道配置JSON")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
