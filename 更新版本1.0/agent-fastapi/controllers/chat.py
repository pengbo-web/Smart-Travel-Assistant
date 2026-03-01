from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from jwt_create import get_current_user_ws, get_current_user
from typing import Dict
from sqlmodel import Session, select
from database import get_session
from state_graph import ToolInfo
from state_graph import get_tool_list_ws, get_tool_list
from services.chat import main_model, conversation_data, get_location_data
import uuid
from core.response import response
from models.conversations_list import ConversationsList
from sqlalchemy import desc
from fastapi.encoders import jsonable_encoder
from schemas.chat import GetConversationValidate, LocationDataValidate

router = APIRouter(prefix="/chat", tags=["和模型对话"])


# 和模型对话(为什么要用websocket，保证模型输出太多的话，中途不会被打断)
@router.websocket("/send_message")
async def send_message(
    websocket: WebSocket,
    session: Session = Depends(get_session),
    tool_info: ToolInfo = Depends(get_tool_list_ws),
):
    print("进来")
    # 建立对话连接
    await websocket.accept()
    # token校验
    user_id = await get_current_user_ws(websocket)
    if user_id == "401":
        return
    # 前端发送的数据格式
    """
  {'sessionId':'会话id','content':'发送给模型的问题'}
  """
    try:
        while True:
            # 循环接受前端消息
            data: Dict[str, str] = await websocket.receive_json()
            print("收到消息:", data)
            # 参数校验
            sessionId = data.get("sessionId", "").strip()
            content = data.get("content", "").strip()
            if not sessionId or not content:
                await websocket.send_json(
                    {"role": "end", "content": "sessionId和content必填", "code": 422}
                )
                continue
            # 调用对话
            # await main_model(sessionId, user_id, content, session, tool_info)
            try:
                async for event in main_model(
                    sessionId, user_id, content, session, tool_info
                ):
                    await websocket.send_json(event)
                # 模型回复结束
                await websocket.send_json(
                    {"role": "end", "content": "模型回复结束", "code": 200}
                )
            except Exception as err:  # type: ignore
                print(err)
                await websocket.send_json(
                    {"role": "end", "content": "出错了", "code": 500}
                )
    except WebSocketDisconnect as error:
        print("用户断开连接", error)


# 创建会话id
@router.get("/create_conversation")
async def create_conversation(user_id=Depends(get_current_user)):  # type: ignore
    session_id = str(uuid.uuid4())
    return response({"sessionId": session_id})


# 获取全部会话列表
@router.get("/all_conversation_list")
async def all_conversation_list(
    session: Session = Depends(get_session), user_id: str = Depends(get_current_user)
):
    query = (
        select(ConversationsList)
        .where(ConversationsList.user_id == user_id)
        .order_by(desc(ConversationsList.id))  # type: ignore
    )
    res = session.exec(query).all()
    json_data = jsonable_encoder(res)
    return response(json_data)


# 获取某个会话下的对话记录
@router.post("/get_conversation")
async def get_conversation(
    req: GetConversationValidate,
    user_id: str = Depends(get_current_user),
    tool_info: ToolInfo = Depends(get_tool_list),
):
    print(req.sessionId)
    res = await conversation_data(req.sessionId, tool_info)
    return response(res)


"""
用户：帮我规划一个西安三日游

模型：以下是我为你规划的一个西安三日游：
第一天：秦始皇陵
第二天：华清宫
第三天：武则天乾陵
祝你玩得愉快
"""


# 获取经纬度数据
@router.post("/location_data")
async def location_data(
    req: LocationDataValidate,
    user_id: str = Depends(get_current_user),
    tool_info: ToolInfo = Depends(get_tool_list),
):
    print(req.content)
    res = await get_location_data(req.content, tool_info)
    return response(res)
