"""
SupervisorAgent — 意图路由

职责: 解析用户意图（travel_plan / chat），提取目的地和天数，路由到对应分支
模型: qwen-max（轻量结构化输出，只做分类不做生成）
工具: 无
"""

import os

from langchain_community.chat_models.tongyi import ChatTongyi
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
from typing import Literal

from graph.state import MultiAgentState


# ────────────────────────────────────────────────────────
# 结构化输出模型
# ────────────────────────────────────────────────────────


class SupervisorOutput(BaseModel):
    """Supervisor 的结构化输出，使用 Pydantic 强制约束返回格式"""

    intent: Literal["travel_plan", "chat"] = Field(
        description="意图分类：travel_plan=旅游规划，chat=闲聊/其他"
    )
    destination: str = Field(
        default="",
        description="目的地城市名，如'杭州'、'西安'，非旅游意图时为空",
    )
    travel_days: int = Field(
        default=3,
        description="旅行天数，用户未说明时默认3天",
    )
    reason: str = Field(
        default="",
        description="分类依据，用于调试和日志",
    )


# ────────────────────────────────────────────────────────
# Prompt
# ────────────────────────────────────────────────────────

SUPERVISOR_PROMPT = """你是旅游助手的意图分析模块，只负责分析用户消息的意图并提取关键信息。

分类规则：
1. 如果用户提到"旅行/旅游/规划/攻略/景点/几日游"等旅游相关词汇 → intent="travel_plan"
2. 其他所有情况（闲聊、问好、技术问题等）→ intent="chat"

提取规则（仅 travel_plan 时）：
- destination：从消息中提取目的地城市名
- travel_days：提取旅行天数，未提及则默认 3

请严格按照指定的 JSON Schema 输出，不要输出任何多余文字。"""


# ────────────────────────────────────────────────────────
# 节点函数
# ────────────────────────────────────────────────────────


def _create_supervisor_llm():
    """创建 Supervisor 专用的结构化输出 LLM"""
    llm = ChatTongyi(
        model="qwen-max",
        api_key=os.getenv("API_KEY"),
    )
    return llm.with_structured_output(SupervisorOutput)


async def supervisor_node(state: MultiAgentState) -> dict:
    """
    Supervisor 节点：
    1. 分析意图（travel_plan / chat）
    2. 初始化偏好状态（如果是首次旅游请求）
    3. 返回路由所需字段
    """
    llm = _create_supervisor_llm()

    # 只传入最后一条用户消息（减少 token）
    from langchain_core.messages import SystemMessage

    messages = [SystemMessage(content=SUPERVISOR_PROMPT)] + state["messages"][-1:]
    result: SupervisorOutput = await llm.ainvoke(messages)

    update: dict = {
        "supervisor_result": {
            "intent": result.intent,
            "destination": result.destination,
            "travel_days": result.travel_days,
        },
    }

    # 旅游意图 + 偏好未完成时，初始化标记
    if result.intent == "travel_plan" and not state.get("preferences_done"):
        update["preferences_done"] = False
        update["transport_done"] = False
        update["research_done"] = False
        update["transport_result"] = ""

    return update


def supervisor_router(state: MultiAgentState) -> str:
    """
    Supervisor 之后的条件路由。

    Returns:
        "chat_agent"       — 闲聊
        "preference_node"  — 首次旅游请求，推送偏好卡
        "weather_strategy" — 偏好已完成，进入规划流水线
    """
    intent = state["supervisor_result"]["intent"]
    if intent == "chat":
        return "chat_agent"
    # travel_plan
    if state.get("preferences_done"):
        return "weather_strategy"
    return "preference_node"
