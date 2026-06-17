"""
智能评论状态机数据模型

每个 CommentTask 实例代表一个「在指定目标下自动评论」的长期任务，
其生命周期由状态机驱动，支持风控、审核、跟进等复杂流转。
"""

from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field


class CommentTaskStatus(str, Enum):
    """状态机状态"""
    MONITORING = "monitoring"           # 监控中：等待触发条件
    ANALYZING = "analyzing"             # 意图分析中：LLM分析内容上下文
    GENERATING = "generating"           # 生成候选：已生成备选评论
    REVIEWING = "reviewing"             # 待审核：等待人工确认
    QUEUED = "queued"                   # 风控排队：冷却期等待
    EXECUTED = "executed"               # 已执行：评论已发出
    FOLLOW_UP = "follow_up"             # 需要跟进：收到回复，形成对话链
    DELETED = "deleted"                 # 被删除/屏蔽
    PAUSED = "paused"                   # 暂停：人工或风控触发
    FAILED = "failed"                   # 失败：重试耗尽或异常


class RiskLevel(str, Enum):
    """风控等级"""
    CONSERVATIVE = "conservative"       # 保守：长冷却、低频次、严格去重
    STANDARD = "standard"               # 标准：适中策略
    AGGRESSIVE = "aggressive"           # 激进：短冷却、高频次


class CommentRecord(BaseModel):
    """单次评论执行记录"""
    id: str = Field(default_factory=lambda: f"cm_{datetime.now().timestamp()}")
    task_id: str
    target_video_id: Optional[str] = None
    target_comment_id: Optional[str] = None
    generated_text: str
    final_text: str
    status: Literal["pending", "sent", "deleted", "failed"] = "pending"
    platform_response: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None


class CommentTask(BaseModel):
    """智能评论任务（状态机实例）"""
    id: str = Field(default_factory=lambda: f"ct_{int(datetime.now().timestamp() * 1000)}")
    name: str = Field(..., description="任务名称，如：小红书美妆号互动")
    
    # 目标配置
    target_platform: Literal["douyin", "xiaohongshu", "kuaishou", "shipinhao"] = Field(..., description="目标平台")
    target_account: str = Field(..., description="目标博主ID/主页链接")
    trigger_type: Literal["new_video", "keyword", "hot_comment"] = Field(default="new_video", description="触发类型")
    trigger_keywords: list[str] = Field(default=[], description="触发关键词列表")
    exclude_keywords: list[str] = Field(default=[], description="排除关键词")
    
    # 状态机当前状态
    status: CommentTaskStatus = Field(default=CommentTaskStatus.MONITORING)
    status_entered_at: datetime = Field(default_factory=datetime.now)
    status_message: Optional[str] = Field(default=None, description="状态说明")
    
    # 风控配置
    risk_level: RiskLevel = Field(default=RiskLevel.STANDARD)
    daily_limit: int = Field(default=10, ge=1, le=100, description="每日评论上限")
    cooldown_seconds: int = Field(default=300, ge=60, description="两次评论最小间隔(秒)")
    max_daily_per_target: int = Field(default=2, ge=1, description="同一目标每日最大评论数")
    deduplicate: bool = Field(default=True, description="是否启用评论内容去重")
    
    # 内容配置
    persona: str = Field(default="专业但友好的行业从业者", description="评论人格设定")
    comment_style: Literal["professional", "casual", "humorous", "emotional"] = Field(default="casual")
    max_length: int = Field(default=100, le=500, description="单条评论最大字数")
    require_approval: bool = Field(default=False, description="是否人工审核后再发送")
    
    # 统计
    total_executed: int = Field(default=0)
    total_failed: int = Field(default=0)
    total_deleted: int = Field(default=0)
    last_executed_at: Optional[datetime] = None
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    paused_until: Optional[datetime] = None
    
    # 运行配置
    auto_start: bool = Field(default=False)
    schedule_cron: Optional[str] = Field(default=None, description="可选的定时调度cron")
    
    class Config:
        use_enum_values = True


class CommentTaskCreate(BaseModel):
    """创建任务请求"""
    name: str
    target_platform: Literal["douyin", "xiaohongshu", "kuaishou", "shipinhao"]
    target_account: str
    trigger_type: Literal["new_video", "keyword", "hot_comment"] = "new_video"
    trigger_keywords: list[str] = []
    exclude_keywords: list[str] = []
    risk_level: RiskLevel = RiskLevel.STANDARD
    daily_limit: int = 10
    cooldown_seconds: int = 300
    persona: str = "专业但友好的行业从业者"
    comment_style: Literal["professional", "casual", "humorous", "emotional"] = "casual"
    max_length: int = 100
    require_approval: bool = False
    auto_start: bool = False


class CommentTaskUpdate(BaseModel):
    """更新任务请求（部分字段）"""
    name: Optional[str] = None
    trigger_keywords: Optional[list[str]] = None
    exclude_keywords: Optional[list[str]] = None
    risk_level: Optional[RiskLevel] = None
    daily_limit: Optional[int] = None
    cooldown_seconds: Optional[int] = None
    persona: Optional[str] = None
    comment_style: Optional[str] = None
    max_length: Optional[int] = None
    require_approval: Optional[bool] = None
    auto_start: Optional[bool] = None
    status: Optional[CommentTaskStatus] = None


class StateTransitionEvent(BaseModel):
    """状态转移事件（用于审计日志）"""
    id: str = Field(default_factory=lambda: f"ev_{int(datetime.now().timestamp() * 1000)}")
    task_id: str
    from_status: CommentTaskStatus
    to_status: CommentTaskStatus
    event: str = Field(..., description="触发事件名称")
    reason: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
