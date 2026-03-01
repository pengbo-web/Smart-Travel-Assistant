from fastapi import FastAPI

# 实例化
app = FastAPI()
# get表示要设计一个get接口
"""
get
post
"""
@app.get('/')
def hello():
  print('12346789999000')
  return{'data':'99999'}

# -----------同步和异步----------------
# 同步函数
# 假如10个用户同时请求一个下单接口
import time
@app.get('/order')
def create_order():
  print('开始下单')
  time.sleep(2)#查询库存耗时2s
  time.sleep(3)#支付耗时3s
  print('下单完成')
# 10个用户下单5*10=50s

# 异步函数，async，await
import asyncio
@app.get('/order_async')
async def create_order_b():
  print('开始下单')
  await asyncio.sleep(2)#查询库存耗时2s
  await asyncio.sleep(3)#支付耗时3s
  print('下单完成')
# 10个用户下单5s完成

# 常见的请求接收前端传递的参数

# get接收数据：路径参数（单个参数）
@app.get('/api/{name}')
async def hello_a(name:str):
  print(name)
  return{'data':f"你好。我叫{name}"}

# get接收数据：路径参数（多个参数）
@app.get('/api_b/{name}/{age}')
async def hello_b(name:str,age:int):
  print(name,age)
  return{"data":f"你好，我叫{name},年龄{age}岁"}

# post请求
from pydantic import BaseModel
class Item(BaseModel):
  name:str
  age:int

@app.post("/api_c")
async def hello_c(item:Item):
  print(item.age,item.name)
  return{"data":f"你好，我叫{item.name},年龄{item.age}岁"}




# 自定义端口
if __name__ == '__main__':
  import uvicorn
  uvicorn.run(
    app="main:app",
    host='127.0.0.1',
    port=4000,
    reload=True
  )