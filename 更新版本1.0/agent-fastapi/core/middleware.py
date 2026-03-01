"""
后端返回给前端的数据可以分为两大类：
1.可控返回：
  比如接口正常执行完毕、或者业务逻辑中的可预期的返回。
2.不可控返回：
  比如数据库断开，网络断开，服务器异常
"""
from fastapi import Request
from typing import Any
from core.response import response

# 全局异常处理中间件
async def gloglobal_middleware(request:Request,call_next:Any):
  try:
    # 调用下一个中间件
    # print('进入了中间件')
    return await call_next(request)
  except Exception as err:
    # print('出现错误了')
    # 接受异常
    return response([],500,str(err))
  
# 全局参数校验函数
async def validation_exception_handler(request:Request,exc:Any):
  first_error = exc.errors()[0]
  msg = first_error['msg']
  if msg in ['Field required']:
    msg = '缺少必传参数'
  return response(code=422,msg=msg,data=[])