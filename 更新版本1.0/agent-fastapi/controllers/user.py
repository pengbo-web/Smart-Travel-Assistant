from fastapi import APIRouter,Depends,UploadFile
from core.response import response
from schemas.user import UserLoginValidate
import os
from dotenv import load_dotenv
import httpx
from sqlmodel import select,Session
from models.user import User
from database import get_session
from typing import cast
from uuid import uuid4
from jwt_create import create_access_token
"""
APIRouter 是 FastAPI 提供的一个路由分组器（Router）。
它的作用是：把一组相关的接口（API）集中在一起，单独定义、统一管理，再挂载到主应用上。
prefix	给该模块的所有接口统一加上路径前缀（比如 /user）
tags	给接口分组（在 docs 文档中显示为“用户相关”、“文章相关”）
"""
router = APIRouter(prefix='/user',tags=['用户相关的接口'])

load_dotenv()

APPID = os.getenv('APPID')
SECRET = os.getenv('SECRET')

# 登录请求地址
code2Session = 'https://api.weixin.qq.com/sns/jscode2session'

# 用户登录接口
# Depends是依赖注入
@router.post('/user_login')
async def login(req:UserLoginValidate,session:Session = Depends(get_session)):
  try:
      print('用户登录')
      # 构造请求参数
      params = {
        'appid':APPID,
        'secret':SECRET,
        'js_code':req.code,
        'grant_type':'authorization_code',
      }
      async with httpx.AsyncClient() as client:
        r = await client.get(code2Session,params=params)
        print(r.json())
      data = r.json()
      if "errcode" in data:
        return response([],400,data)
      openid:str = data.get('openid')
      # 查询用户是否已存在
      statement = select(User).where(User.openid == openid)
      # 执行上一步的sql语句
      userinfo = session.exec(statement).first()
      print(f"User info: {userinfo}")
      # 不存在用户信息
      if not userinfo:
        # 插入数据库
        userinfo = User(
          avatar=req.avatar,
          nickname=req.nickname,
          openid=openid
        )
        # 先放入会话里
        session.add(userinfo)
        # 提交事务,插入到数据
        session.commit()
        #同步数据
        session.refresh(userinfo)
      # 生成token
      usertoken = create_access_token({'openid':openid})
      # 返回前端
      return response({'avatar':req.avatar,'nickname':req.nickname,'usertoken':usertoken})
  except Exception as e:
      import traceback
      traceback.print_exc()
      return response([], 500, f"Internal Server Error: {str(e)}")


# 图片上传（头像上传）
@router.post('/upload_image')
async def upload_image(file:UploadFile):
  print(file)
  # 文件大小
  MAX_FILE_SIZE = 10 * 1024 * 1024
  # 文件类型
  ALLOWED_CONTENT_TYPES = {'image/jpeg','image/png','image/webp'}
  # 校验类型
  if file.content_type not in ALLOWED_CONTENT_TYPES:
    return response([],422,'请上传合法的头像')
  # 校验大小
  if cast(int,file.size) > MAX_FILE_SIZE:
    return response([],422,'上传的头像太大')
  # 重命名文件
  original_ext = os.path.splitext(cast(str,file.filename))[1]
  new_filename = f"{uuid4().hex}{original_ext}"
  save_folder = os.path.join(os.getcwd(),'image')
  file_path = os.path.join(save_folder,new_filename)
  # 存入文件
  with open(file_path,'wb') as f:
    content = await file.read()
    f.write(content)
  return response({'upload_image':f"http://127.0.0.1:4000/image/{new_filename}"})

