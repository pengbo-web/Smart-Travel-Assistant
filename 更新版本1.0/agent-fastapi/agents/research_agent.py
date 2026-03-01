"""
ResearchAgent — 信息搜集 Agent

职责: 并发搜集目的地天气 + 景点/美食信息
模型: qwen3-max
工具: query-weather, bailian_web_search, maps_text_search
内部循环: research_llm → research_tool → research_llm（直到无工具调用）→ research_done
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


def _extract_month(date_str: str) -> str:
    """从 ISO 日期字符串提取月份，如 '2026-05-01' → '5'"""
    if not date_str:
        return ""
    try:
        return str(int(date_str.split("-")[1]))
    except (IndexError, ValueError):
        return ""


def _create_research_llm(tools: list[BaseTool]) -> ChatOpenAI:
    """创建 ResearchAgent 专用的 LLM（绑定 research 组工具）"""
    llm = ChatOpenAI(
        model="qwen3-max",
        api_key=os.getenv("API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    return llm.bind_tools(tools)


async def research_llm_node(state: MultiAgentState, tools: list[BaseTool]) -> dict:
    """
    ResearchAgent 的 LLM 推理节点。

    根据天气策略和用户偏好注入上下文到 Prompt，
    让 LLM 决定调用哪些搜索/天气工具。
    """
    prefs = state.get("preferences", {})
    supervisor = state["supervisor_result"]

    # 注入上下文到 Prompt 模板
    prompt_text = _load_prompt("prompts/research.txt").format(
        destination=supervisor["destination"],
        travel_days=supervisor["travel_days"],
        style=", ".join(prefs.get("style", ["综合"])),
        weather_strategy=state.get("weather_strategy", "realtime"),
        month=_extract_month(prefs.get("travel_date", "")),
    )

    llm_with_tools = _create_research_llm(tools)

    # 只传系统提示 + 最后一条用户消息（减少 token 消耗）
    messages = [SystemMessage(content=prompt_text)] + state["messages"][-1:]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


async def research_tool_node(state: MultiAgentState, tools: list[BaseTool]) -> dict:
    """
    ResearchAgent 的工具执行节点。

    关键改进：去掉 Semaphore，使用 asyncio.gather 真正并发。
    天气查询和景点搜索互不依赖，可以同时发起。
    """
    tools_by_name: dict[str, BaseTool] = {t.name: t for t in tools}
    last_message = cast(AIMessage, state["messages"][-1])

    # 构造并发任务列表
    tasks = []
    for tc in last_message.tool_calls:
        tool = tools_by_name.get(tc["name"])
        if tool:
            tasks.append(tool.ainvoke(tc["args"]))
        else:
            # 工具不存在时直接生成错误消息（不应发生，但兜底）
            async def _err(name=tc["name"]):
                return f"工具 {name} 不在 research 工具组中"
            tasks.append(_err())

    # ★ 真正并发执行
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 组装 ToolMessage 列表
    tool_messages = []
    for tc, result in zip(last_message.tool_calls, results):
        if isinstance(result, Exception):
            content = f"工具执行失败: {repr(result)}"
        else:
            content = str(result)
        tool_messages.append(
            ToolMessage(content=content, tool_call_id=tc["id"])
        )
    return {"messages": tool_messages}


def research_route(state: MultiAgentState) -> str:
    """
    Research 内部路由函数。

    检查最后一条 AI 消息是否包含工具调用：
    - 有工具调用 → 'call_tool'（继续循环）
    - 无工具调用 → 'done'（搜集完毕）
    """
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "call_tool"
    return "done"


async def research_done_node(state: MultiAgentState) -> dict:
    """
    搜集完毕节点。

    提取最后一条 AI 消息的内容作为 research_result，
    并标记 research_done = True，供 MergeNode 检查。
    """
    last_ai = cast(AIMessage, state["messages"][-1])
    return {
        "research_result": last_ai.content,
        "research_done": True,
    }
