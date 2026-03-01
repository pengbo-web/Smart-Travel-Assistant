"""Multi-Agent 服务层

处理 WebSocket 消息流转：
  - 普通消息 → 创建新 graph 执行
  - 偏好提交 → update_state + resume graph
  - 历史记录 → 读取 state 中的 messages

支持 preference_card / tool / tool_result / assistant 四类流式输出。

连接池策略：
  checkpointer / store 由 main.py lifespan 统一创建，
  通过 graph_deps dict 注入，避免每次请求重建连接。
"""

from sqlmodel import Session, select
import json
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    ToolMessage,
)
from typing import Any, AsyncGenerator

from graph.builder import build_multi_agent_graph
from agents.preference import handle_preference_submission
from tool_list import TOOL_LIST
from models.conversations_list import ConversationsList


# ────────────────────────────────────────────────────────
# 主对话函数（Multi-Agent 版）
# ────────────────────────────────────────────────────────


async def main_model(
    thread_id: str,
    user_id: str,
    content: str,
    session: Session,
    graph_deps: dict,
    msg_type: str = "normal",
    preferences: dict | None = None,
) -> AsyncGenerator[dict[str, object], None]:
    """
    与 Multi-Agent 图交互的核心函数。

    Args:
        thread_id: 会话 ID
        user_id: 用户 ID（openid）
        content: 用户消息内容
        session: 数据库会话
        graph_deps: 全局图依赖 {tool_groups, checkpointer, store}
        msg_type: "normal" 普通消息 | "preference_submit" 偏好提交
        preferences: 用户偏好数据（仅 msg_type="preference_submit" 时）
    """
    # 存储会话（仅普通消息）
    if msg_type == "normal" and content:
        await storage_conversation(thread_id, user_id, content, session)

    # 从全局连接池获取依赖（由 main.py lifespan 创建）
    graph = build_multi_agent_graph(
        checkpointer=graph_deps["checkpointer"],
        store=graph_deps["store"],
        tool_groups=graph_deps["tool_groups"],
    )
    config = {"configurable": {"thread_id": thread_id}}

    if msg_type == "preference_submit" and preferences:
        # ── 偏好提交：update_state + resume ──
        state_update = await handle_preference_submission(preferences)
        await graph.aupdate_state(config, state_update)
        # resume：传 None 恢复图执行
        input_data = None
    else:
        # ── 普通消息 ──
        input_data = {"messages": [{"role": "user", "content": content}]}

    # ── 流式输出 ──
    async for item, metadata in graph.astream(
        input_data, stream_mode="messages", config=config
    ):
        # 偏好卡片
        if isinstance(item, AIMessageChunk):
            if item.additional_kwargs.get("type") == "preference_card":
                try:
                    card_data = json.loads(item.content)
                except (json.JSONDecodeError, TypeError):
                    card_data = item.content
                yield {"role": "preference_card", "content": card_data}
            # 工具调用提示
            elif item.tool_calls:
                for call in item.tool_calls:
                    tool_name = call["name"]
                    desc = TOOL_LIST.get(tool_name, "未知工具")
                    if desc != "未知工具":
                        yield {"role": "tool", "content": desc}
            # 文本流式输出
            elif item.content:
                yield {"role": "assistant", "content": item.content}

        # 工具执行结果
        elif isinstance(item, ToolMessage):
            yield {
                "role": "tool_result",
                "content": {item.name: item.content},
            }


# ────────────────────────────────────────────────────────
# 会话存储
# ────────────────────────────────────────────────────────


async def storage_conversation(
    thread_id: str, user_id: str, content: str, session: Session
):
    """创建会话记录（首次消息时）"""
    conversation_list = select(ConversationsList).where(
        ConversationsList.user_id == user_id,
        ConversationsList.thread_id == thread_id,
    )
    conversation_res = session.exec(conversation_list).first()
    if not conversation_res:
        conversation_storage = ConversationsList(
            user_id=user_id, thread_id=thread_id, title=content
        )
        session.add(conversation_storage)
        session.commit()


# ────────────────────────────────────────────────────────
# 历史记录
# ────────────────────────────────────────────────────────


async def conversation_data(thread_id: str, graph_deps: dict) -> Any:
    """获取某个会话下的对话记录"""
    graph = build_multi_agent_graph(
        checkpointer=graph_deps["checkpointer"],
        store=graph_deps["store"],
        tool_groups=graph_deps["tool_groups"],
    )
    config = {"configurable": {"thread_id": thread_id}}

    history = []
    async for snap in graph.aget_state_history(config):
        history.append(snap)

    if not history:
        return []

    valid_snaps = [snap for snap in history if snap.values.get("messages")]
    if not valid_snaps:
        return []

    latest = max(valid_snaps, key=lambda s: s.metadata.get("step", -1))
    msgs = latest.values.get("messages")

    formatted = []
    for item in msgs:
        if isinstance(item, HumanMessage):
            formatted.append({"role": "user", "content": item.content})
        elif isinstance(item, AIMessage):
            # 偏好卡片
            if item.additional_kwargs.get("type") == "preference_card":
                try:
                    card_data = json.loads(item.content)
                except (json.JSONDecodeError, TypeError):
                    card_data = item.content
                formatted.append({
                    "role": "preference_card",
                    "content": card_data,
                })
            elif item.content:
                formatted.append({"role": "assistant", "content": item.content})
            if getattr(item, "tool_calls", None):
                for call in item.tool_calls:
                    tool_name = call.get("name")
                    formatted.append({
                        "role": "tool",
                        "content": TOOL_LIST.get(tool_name, tool_name),
                    })
        elif isinstance(item, ToolMessage):
            formatted.append({
                "role": "tool_result",
                "content": {item.name: item.content},
            })

    return formatted
