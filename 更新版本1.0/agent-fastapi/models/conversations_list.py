from sqlmodel import SQLModel, Field
from datetime import date


# 存储用户的会话
class ConversationsList(SQLModel, table=True):#映射为数据库中的一张表
    id: int | None = Field(default=None, primary_key=True, index=True)
    user_id: str = Field(index=True)
    thread_id: str = Field(index=True)
    title: str = Field()
    created_at: date = Field(default_factory=date.today)
