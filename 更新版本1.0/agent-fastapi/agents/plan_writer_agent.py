"""
PlanWriterAgent — 攻略写作 Agent

职责: 基于 ResearchAgent 和 TransportAgent 的产出，
      生成个性化旅游攻略，并为景点搜索配图
模型: qwen3-max
工具: search-image（geng-search-image MCP）
内部循环: plan_writer_llm → image_tool_node → plan_writer_llm（循环）→ plan_writer_done
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


def _create_plan_writer_llm(tools: list[BaseTool]) -> ChatOpenAI:
    """创建 PlanWriterAgent 专用的 LLM（绑定 image 组工具）"""
    llm = ChatOpenAI(
        model="qwen3-max",
        api_key=os.getenv("API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    return llm.bind_tools(tools)


async def plan_writer_llm_node(
    state: MultiAgentState, tools: list[BaseTool]
) -> dict:
    """
    PlanWriterAgent 的 LLM 推理节点。

    将 research_result、transport_result 和用户偏好注入 Prompt，
    让 LLM 生成攻略文本，过程中可调用 search-image 获取景点配图。
    """
    prefs = state.get("preferences", {})
    supervisor = state["supervisor_result"]

    prompt_text = _load_prompt("prompts/plan_writer.txt").format(
        research_result=state.get("research_result", "（暂无数据）"),
        transport_result=state.get("transport_result", "（无出行交通数据）"),
        travelers=prefs.get("travelers", "未指定"),
        pace=prefs.get("pace", "无偏好"),
        style=", ".join(prefs.get("style", ["综合"])),
        budget=prefs.get("budget", "灵活"),
        destination=supervisor["destination"],
        travel_days=supervisor["travel_days"],
    )

    llm_with_tools = _create_plan_writer_llm(tools)

    # 系统提示 + 最后一条用户消息
    messages = [SystemMessage(content=prompt_text)] + state["messages"][-1:]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


async def image_tool_node(
    state: MultiAgentState, tools: list[BaseTool]
) -> dict:
    """
    PlanWriterAgent 的图片搜索工具执行节点。

    仅处理 search-image 工具调用，为景点搜索配图。
    使用 asyncio.gather 并发执行多个图片搜索请求。
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
                return f"工具 {name} 不在 image 工具组中"
            tasks.append(_err())

    results = await asyncio.gather(*tasks, return_exceptions=True)

    tool_messages = []
    for tc, result in zip(last_message.tool_calls, results):
        if isinstance(result, Exception):
            content = f"图片搜索失败: {repr(result)}"
        else:
            content = str(result)
        tool_messages.append(
            ToolMessage(content=content, tool_call_id=tc["id"])
        )
    return {"messages": tool_messages}


def plan_writer_route(state: MultiAgentState) -> str:
    """
    PlanWriter 内部路由函数。

    检查最后一条 AI 消息是否包含工具调用：
    - 有工具调用 → 'call_tool'（继续搜索图片）
    - 无工具调用 → 'done'（攻略写作完毕）
    """
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "call_tool"
    return "done"


async def plan_writer_done_node(state: MultiAgentState) -> dict:
    """
    攻略完成节点。

    提取最后一条 AI 消息的内容作为 plan_content，
    供后续 MapRouteAgent 使用。
    """
    last_ai = cast(AIMessage, state["messages"][-1])
    return {
        "plan_content": last_ai.content,
    }
