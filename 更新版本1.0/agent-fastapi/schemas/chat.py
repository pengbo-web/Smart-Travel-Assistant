from pydantic import BaseModel, field_validator
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


# 获取经纬度
class LocationDataValidate(BaseModel):
    # 模型回复的内容
    content: str

    # 自定义参数校验
    @field_validator("content", mode="before")
    @classmethod
    def check_not_empty(cls, v: Any, info: Any) -> Any:
        if not isinstance(v, str) or not v.strip():
            raise ValueError(f"{info.field_name}必填")
        return v
