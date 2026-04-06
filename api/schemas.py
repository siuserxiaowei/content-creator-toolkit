"""API请求/响应模型"""

from datetime import datetime
from pydantic import BaseModel, Field


# ===== KOL =====
class KOLCreate(BaseModel):
    name: str
    platform: str = Field(..., pattern="^(xhs|douyin|bilibili|weibo|kuaishou)$")
    platform_uid: str
    homepage_url: str
    description: str = ""
    tags: str = ""
    check_interval: int = Field(default=3600, ge=300, le=86400)


class KOLUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: str | None = None
    is_monitoring: bool | None = None
    check_interval: int | None = Field(default=None, ge=300, le=86400)


class KOLResponse(BaseModel):
    id: int
    name: str
    platform: str
    platform_uid: str
    homepage_url: str
    avatar_url: str
    follower_count: int
    description: str
    tags: str
    is_monitoring: bool
    check_interval: int
    last_checked_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== Content =====
class ContentResponse(BaseModel):
    id: int
    kol_id: int
    platform: str
    content_type: str
    content_id: str
    title: str
    description: str
    url: str
    cover_url: str
    tags: str
    like_count: int
    comment_count: int
    share_count: int
    view_count: int
    published_at: datetime | None
    is_downloaded: bool
    is_analyzed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ContentListResponse(BaseModel):
    total: int
    items: list[ContentResponse]


# ===== Monitor =====
class MonitorTriggerRequest(BaseModel):
    kol_id: int


class MonitorLogResponse(BaseModel):
    id: int
    kol_id: int
    check_type: str
    status: str
    new_contents_count: int
    message: str
    checked_at: datetime

    model_config = {"from_attributes": True}


# ===== Analysis =====
class AnalysisRequest(BaseModel):
    content_id: int | None = None
    kol_id: int | None = None
    batch: bool = False


class TopicAnalysisResponse(BaseModel):
    id: int
    content_id: int
    topic_category: str
    topic_keywords: str
    hook_type: str
    structure_summary: str
    engagement_score: float
    replicability_score: float
    analysis_detail: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== Script =====
class ScriptGenerateRequest(BaseModel):
    topic: str
    style_reference: str = ""
    target_platform: str = "douyin"
    target_duration: int = Field(default=60, ge=15, le=600)
    source_content_ids: list[int] = []
    additional_instructions: str = ""


class ScriptResponse(BaseModel):
    id: int
    title: str
    topic: str
    style_reference: str
    target_platform: str
    target_duration: int
    hook: str
    body: str
    cta: str
    full_script: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== 通用 =====
class MessageResponse(BaseModel):
    message: str
    data: dict | None = None
