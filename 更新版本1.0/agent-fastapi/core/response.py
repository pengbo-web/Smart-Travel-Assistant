# 统一接口返回数据类型，格式
from typing import Any
from pydantic import BaseModel
from fastapi.responses import JSONResponse

class ResponseModel(BaseModel):
  code:int = 200
  msg:Any = 'SUCCESS'
  data:Any | None = None


def response(
    data:Any = None,#返回的数据，可以是任意类型，也可以是 None
    code:int = 200,#→ 状态码，默认 200
    msg:Any = 'SUCCESS'#提示消息，默认 "SUCCESS"
)->JSONResponse:
  if data is None:
    data = []
  payload = ResponseModel(code=code,msg=msg,data=data).model_dump()
  return JSONResponse(content=payload,status_code=code)
