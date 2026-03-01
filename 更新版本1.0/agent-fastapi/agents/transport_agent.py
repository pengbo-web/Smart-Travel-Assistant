"""
TransportAgent — 交通查询 Agent

职责: 查询出发地到目的地的火车/高铁方案
模型: qwen3-max
工具: get-tickets, get-stations-code-in-city, get-interline-tickets,
      get-train-route-stations, get-current-date, relative-date,
      maps_direction_transit, maps_geo
内部循环: transport_llm → transport_tool → transport_llm → transport_done
"""

import asyncio
import os
from typing import cast

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from graph.state import MultiAgentState


def _load_prompt(path: str) -> str:
    """读取 Prompt 模板文件"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ────────────────────────────────────────────────────────
# transport_check — 判断是否需要查交通
# ────────────────────────────────────────────────────────


async def transport_check_node(state: MultiAgentState) -> dict:
    """
    判断是否需要执行 TransportAgent。

    如果用户未填出发地，直接标记完成跳过。
    """
    departure = state.get("preferences", {}).get("departure", "").strip()
    if not departure:
        return {
            "transport_done": True,
            "transport_result": "",
        }
    return {}  # 继续到 transport_llm


def transport_check_router(state: MultiAgentState) -> str:
    """
    transport_check 之后的路由。

    Returns:
        "transport_agent" — 有出发地，执行查询
        "merge_check"     — 无出发地，跳过直接到合并点
    """
    if state.get("transport_done"):
        return "merge_check"
    return "transport_agent"


# ────────────────────────────────────────────────────────
# TransportAgent 节点函数
# ────────────────────────────────────────────────────────


def _create_transport_llm(tools: list[BaseTool]) -> ChatOpenAI:
    """创建 TransportAgent 专用的 LLM（绑定 transport 组工具）"""
    llm = ChatOpenAI(
        model="qwen3-max",
        api_key=os.getenv("API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    return llm.bind_tools(tools)


async def transport_llm_node(
    state: MultiAgentState, tools: list[BaseTool]
) -> dict:
    """
    TransportAgent 的 LLM 推理节点。

    注入出发地、目的地、日期到 Prompt，让 LLM 调用火车票查询工具。
    """
    prefs = state.get("preferences", {})
    supervisor = state["supervisor_result"]

    prompt_text = _load_prompt("prompts/transport.txt").format(
        departure=prefs.get("departure", ""),
        destination=supervisor["destination"],
        travel_date=prefs.get("travel_date", "近期"),
    )

    llm_with_tools = _create_transport_llm(tools)

    messages = [SystemMessage(content=prompt_text)] + state["messages"][-1:]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


async def transport_tool_node(
    state: MultiAgentState, tools: list[BaseTool]
) -> dict:
    """
    TransportAgent 的工具执行节点。

    并发执行多个交通查询工具调用。
    """
    tools_by_name: dict[str, BaseTool] = {t.name: t for t in tools}
    last_message = cast(AIMessage, state["messages"][-1])

    tasks = []
    for tc in last_message.tool_calls:
        tool = tools_by_name.get(tc["name"])
        if tool:
            tasks.append(tool.ainvoke(tc["args"]))
        else:
            async def _err(name=tc["name"]):
                return f"工具 {name} 不在 transport 工具组中"
            tasks.append(_err())

    results = await asyncio.gather(*tasks, return_exceptions=True)

    tool_messages = []
    for tc, result in zip(last_message.tool_calls, results):
        if isinstance(result, Exception):
            content = f"交通查询失败: {repr(result)}"
        else:
            content = str(result)
        tool_messages.append(
            ToolMessage(content=content, tool_call_id=tc["id"])
        )
    return {"messages": tool_messages}


def transport_route(state: MultiAgentState) -> str:
    """
    Transport 内部路由函数。

    检查最后一条 AI 消息是否包含工具调用：
    - 有工具调用 → 'call_tool'
    - 无工具调用 → 'done'
    """
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "call_tool"
    return "done"


async def transport_done_node(state: MultiAgentState) -> dict:
    """
    交通查询完毕。

    提取最后一条 AI 消息作为 transport_result，
    标记 transport_done = True。
    """
    last_ai = cast(AIMessage, state["messages"][-1])
    return {
        "transport_result": last_ai.content,
        "transport_done": True,
    }
