from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from jwt_create import get_current_user_ws, get_current_user
from typing import Dict
from sqlmodel import Session, select
from database import get_session
from services.chat import main_model, conversation_data
import uuid
from core.response import response
from models.conversations_list import ConversationsList
from sqlalchemy import desc
from fastapi.encoders import jsonable_encoder
from schemas.chat import GetConversationValidate


# ────────────────────────────────────────────────────────
# 从 app.state 获取工具分组（Multi-Agent 版）
# ────────────────────────────────────────────────────────


def get_tool_groups_ws(websocket: WebSocket) -> dict:
    """WebSocket 专用：从 app.state 获取工具分组"""
    tool_groups = getattr(websocket.app.state, "tool_groups", None)
    if tool_groups is None:
        raise RuntimeError("工具分组未初始化")
    return tool_groups


def get_tool_groups(request=Depends()):
    """HTTP 接口专用：从 app.state 获取工具分组"""
    from fastapi import Request

    def _inner(request: Request) -> dict:
        tool_groups = getattr(request.app.state, "tool_groups", None)
        if tool_groups is None:
            raise RuntimeError("工具分组未初始化")
        return tool_groups

    return _inner


router = APIRouter(prefix="/chat", tags=["和模型对话"])


# 和模型对话（Multi-Agent 版，支持偏好提交）
@router.websocket("/send_message")
async def send_message(
    websocket: WebSocket,
    session: Session = Depends(get_session),
):
    # 建立对话连接
    await websocket.accept()
    # token 校验
    user_id = await get_current_user_ws(websocket)
    if user_id == "401":
        return

    # 从 app.state 获取工具分组
    tool_groups = get_tool_groups_ws(websocket)

    try:
        while True:
            data: Dict[str, str] = await websocket.receive_json()
            print("收到消息:", data)

            sessionId = data.get("sessionId", "").strip()
            msg_type = data.get("type", "normal")  # "normal" | "preference_submit"

            # 偏好提交消息
            if msg_type == "preference_submit":
                preferences = data.get("preferences", {})
                if not sessionId or not preferences:
                    await websocket.send_json(
                        {"role": "end", "content": "sessionId和preferences必填", "code": 422}
                    )
                    continue
                try:
                    async for event in main_model(
                        sessionId, user_id, "", session, tool_groups,
                        msg_type="preference_submit",
                        preferences=preferences,
                    ):
                        await websocket.send_json(event)
                    await websocket.send_json(
                        {"role": "end", "content": "模型回复结束", "code": 200}
                    )
                except Exception as err:
                    print(err)
                    await websocket.send_json(
                        {"role": "end", "content": "出错了", "code": 500}
                    )
            else:
                # 普通消息
                content = data.get("content", "").strip()
                if not sessionId or not content:
                    await websocket.send_json(
                        {"role": "end", "content": "sessionId和content必填", "code": 422}
                    )
                    continue
                try:
                    async for event in main_model(
                        sessionId, user_id, content, session, tool_groups,
                    ):
                        await websocket.send_json(event)
                    await websocket.send_json(
                        {"role": "end", "content": "模型回复结束", "code": 200}
                    )
                except Exception as err:
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
):
    # 从请求中获取 tool_groups
    from fastapi import Request

    # 注意：此处需要从 app.state 获取 tool_groups
    # 但 Depends 无法直接在 post 中获取 Request，所以走全局变量
    # TODO: P1-08 中通过 main.py 改造统一注入
    tool_groups = {}  # 占位，将在 P1-08 中通过 Depends 注入
    print(req.sessionId)
    res = await conversation_data(req.sessionId, tool_groups)
    return response(res)


# ────────────────────────────────────────────────────────
# 注意：原有的 location_data 接口已废弃
# Multi-Agent 架构中，MapRouteAgent 直接在图内调用 map_data 工具
# 无需前端单独请求经纬度数据
# ────────────────────────────────────────────────────────
