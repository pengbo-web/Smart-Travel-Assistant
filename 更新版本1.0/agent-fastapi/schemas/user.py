from pydantic import BaseModel,field_validator
from typing import Any
# 登录接口
"""
传递参数
code:code值
avatar:头像
nickname:昵称
"""
class UserLoginValidate(BaseModel):
  code:str
  avatar:str
  nickname:str

  # 自定义参数校验
  @field_validator("code","avatar","nickname",mode='before')
  @classmethod
  def check_not_empty(cls,v:Any,info:Any)->Any:
    if not isinstance(v,str) or not v.strip():
      raise ValueError(f"{info.field_name}必填")
    return v


