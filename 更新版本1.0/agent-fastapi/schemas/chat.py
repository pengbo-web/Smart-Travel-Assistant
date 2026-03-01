from pydantic import BaseModel, field_validator, model_validator
from typing import Any


# 获取会话id
class GetConversationValidate(BaseModel):
    # 会话id
    sessionId: str

    # 自定义参数校验
    @field_validator("sessionId", mode="before")
    @classmethod
    def check_not_empty(cls, v: Any, info: Any) -> Any:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name}必填")
        return v


# ────────────────────────────────────────────────────────
# 偏好提交校验（对齐 PREFERENCE_CARD 的 6 个字段）
# ────────────────────────────────────────────────────────

# 合法选项常量（与 agents/preference.py PREFERENCE_CARD 一致）
VALID_TRAVELERS = {"一个人", "情侣", "家庭", "朋友"}
VALID_PACE = {"特种兵", "舒适游", "无偏好"}
VALID_STYLE = {"自然风光", "城市漫步", "历史文化", "特色体验"}
VALID_BUDGET = {"节俭", "奢侈", "灵活"}


class PreferenceSubmit(BaseModel):
    """
    用户偏好提交数据校验。

    必填: travelers, pace, style, budget
    选填: departure（出发城市）, travel_date（出行日期 YYYY-MM-DD）

    示例:
        {
            "travelers": "情侣",
            "pace": "舒适游",
            "style": ["自然风光", "历史文化"],
            "budget": "灵活",
            "departure": "北京",
            "travel_date": "2026-03-15"
        }
    """

    travelers: str
    pace: str
    style: list[str]
    budget: str
    departure: str = ""
    travel_date: str = ""

    @field_validator("travelers")
    @classmethod
    def validate_travelers(cls, v: str) -> str:
        if v not in VALID_TRAVELERS:
            raise ValueError(f"travelers 必须是 {VALID_TRAVELERS} 之一")
        return v

    @field_validator("pace")
    @classmethod
    def validate_pace(cls, v: str) -> str:
        if v not in VALID_PACE:
            raise ValueError(f"pace 必须是 {VALID_PACE} 之一")
        return v

    @field_validator("style")
    @classmethod
    def validate_style(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("style 至少选择一项")
        invalid = set(v) - VALID_STYLE
        if invalid:
            raise ValueError(f"style 包含无效选项: {invalid}")
        return v

    @field_validator("budget")
    @classmethod
    def validate_budget(cls, v: str) -> str:
        if v not in VALID_BUDGET:
            raise ValueError(f"budget 必须是 {VALID_BUDGET} 之一")
        return v

    @field_validator("travel_date")
    @classmethod
    def validate_travel_date(cls, v: str) -> str:
        if v:
            try:
                from datetime import datetime
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("travel_date 格式必须为 YYYY-MM-DD")
        return v
