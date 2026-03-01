from sqlmodel import Session, select
from state_graph import ToolInfo
import os
from dotenv import load_dotenv

load_dotenv()

DB_URI = str(os.getenv("DB_URI"))
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from state_graph import state_graph, tongyi_max
from langchain_core.messages import AIMessageChunk, ToolMessage, HumanMessage, AIMessage

# from langchain_core.messages import HumanMessage
from model_prompt import prompt, map_prompt
from tool_list import TOOL_LIST
from typing import AsyncGenerator, Any
from models.conversations_list import ConversationsList
from langchain.agents import create_agent
import json


# 和模型对话
""""
thread_id:会话id
user_id：用户id，openid
content：用户的问题
session：会话
tool_info：工具数据
"""


async def main_model(
    thread_id: str, user_id: str, content: str, session: Session, tool_info: ToolInfo
) -> AsyncGenerator[dict[str, object], None]:
    # print("111")
    # 存储会话
    await storage_conversation(thread_id, user_id, content, session)
    # 数据库连接，建表
    async with (
        AsyncPostgresStore.from_conn_string(DB_URI) as store,
        AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer,
    ):
        await store.setup()
        await checkpointer.setup()
        # 连接图形api构建器
        state_state_graph = state_graph(checkpointer, store, prompt, tool_info)
        # 创建会话id
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        # 创建问题
        messages = {"messages": [{"role": "user", "content": content}]}
        # 开始流式输出
        async for item, metadata in state_state_graph.astream(messages, stream_mode="messages", config=config):  # type: ignore
            # print("+++++++++++")
            if isinstance(item, AIMessageChunk) and item.tool_calls:
                for call in item.tool_calls:
                    # 获取工具名称
                    tool_name = call["name"]
                    # 匹配对应的工具名称
                    desc = TOOL_LIST.get(tool_name, "未知工具")
                    if desc == "未知工具":
                        continue
                    # 整理数据格式返回前端
                    yield {"role": "tool", "content": desc}
            # 工具执行结果
            elif isinstance(item, ToolMessage):
                yield {"role": "tool_result", "content": {item.name: item.content}}
            # 模型回复
            elif isinstance(item, AIMessageChunk) and item.content:
                yield {"role": "assistant", "content": item.content}


# 存储会话
async def storage_conversation(
    thread_id: str, user_id: str, content: str, session: Session
):
    # 查询是否存在会话
    conversation_list = select(ConversationsList).where(
        ConversationsList.user_id == user_id, ConversationsList.thread_id == thread_id
    )
    conversation_res = session.exec(conversation_list).first()
    if not conversation_res:
        conversation_storage = ConversationsList(
            user_id=user_id, thread_id=thread_id, title=content
        )
        session.add(conversation_storage)
        session.commit()


# 获取某个会话下的对话记录
async def conversation_data(thread_id: str, tool_info: ToolInfo) -> Any:
    async with (
        AsyncPostgresStore.from_conn_string(DB_URI) as store,
        AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer,
    ):
        await store.setup()
        await checkpointer.setup()
        # 连接图形api构建器
        state_state_graph = state_graph(checkpointer, store, prompt, tool_info)
        # 创建会话id
        config = {
            "configurable": {
                "thread_id": thread_id,
            }
        }
        # 存储对话历史
        history = []
        # 请求历史对话数据
        async for snap in state_state_graph.aget_state_history(config):  # type: ignore
            # print(snap, "===================")
            history.append(snap)
        if not history:
            return []
        # 获取messages里的内容
        valid_snaps = [snap for snap in history if snap.values.get("messages")]
        if not valid_snaps:
            return []
        # 排序，把最近的对话取到后面展示
        latest = max(valid_snaps, key=lambda s: s.metadata.get("step", -1))  # type: ignore
        msgs = latest.values.get("messages")
        # print(msgs, "=================")
        # 构建返回格式，返回前端
        formatted = []
        for item in msgs:
            if isinstance(item, HumanMessage):
                formatted.append({"role": "user", "content": item.content})
            elif isinstance(item, AIMessage):
                if item.content:
                    formatted.append({"role": "assistant", "content": item.content})
                # 获取工具名称
                if getattr(item, "tool_calls", None):
                    for call in item.tool_calls:
                        tool_name = call.get("name")
                        formatted.append(
                            {
                                "role": "tool",
                                "content": TOOL_LIST.get(tool_name, tool_name),
                            }
                        )
            # 获取工具结果
            elif isinstance(item, ToolMessage):
                formatted.append(
                    {"role": "tool_result", "content": {item.name: item.content}}
                )
        return formatted


# 获取经纬度数据
async def get_location_data(content: str, tool_info: ToolInfo) -> Any:
    messages = {"messages": [{"role": "user", "content": content}]}
    try:
        agent = create_agent(
            model=tongyi_max, system_prompt=map_prompt, tools=tool_info["all_tools"]
        )
        res = await agent.ainvoke(messages)  # type: ignore
        # print(res)
        last_ai_msg = next(
            (m for m in reversed(res["messages"]) if isinstance(m, AIMessage)), None
        )
        print(last_ai_msg)
        if last_ai_msg:
            data = json.loads(last_ai_msg.content)  # type: ignore
            print(data)
            return data
        else:
            return []
    except Exception as err:  # type: ignore
        print(err)
        return []
