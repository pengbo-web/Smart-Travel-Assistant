"""
Multi-Agent 共享状态定义

所有 Agent 节点通过 MultiAgentState 共享数据，
LangGraph 的 add_messages reducer 自动追加对话历史。
"""

from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.graph import add_messages
from typing_extensions import TypedDict


class Preferences(TypedDict, total=False):
    """用户旅行偏好，由前端偏好卡收集"""

    travelers: str       # "一个人" | "情侣" | "家庭" | "朋友"
    pace: str            # "特种兵" | "舒适游" | "无偏好"
    style: list[str]     # ["自然风光", "城市漫步", "历史文化", "特色体验"]
    budget: str          # "节俭" | "奢侈" | "灵活"
    departure: str       # 出发城市（选填，空字符串表示未填）
    travel_date: str     # ISO 格式 "2026-05-01"（选填，空字符串表示未填）


class SupervisorResult(TypedDict):
    """SupervisorAgent 的结构化输出"""

    intent: str          # "travel_plan" | "chat"
    destination: str     # 目的地城市
    travel_days: int     # 旅行天数（默认 3）


class MultiAgentState(TypedDict):
    """
    整个 Multi-Agent 图的共享状态。

    字段流转规则:
      - messages:          所有节点读写，add_messages 自动追加
      - supervisor_result: Supervisor 写入 → Preference/Research/Transport 读取
      - preferences:       PreferenceNode 写入 → Research/PlanWriter 读取
      - preferences_done:  Supervisor 初始化 / PreferenceNode 设 True → Supervisor 路由判断
      - weather_strategy:  WeatherStrategyNode 写入 → ResearchAgent 读取
      - research_result:   ResearchAgent 写入 → PlanWriterAgent 读取
      - research_done:     ResearchAgent 写入 → MergeNode 读取
      - transport_result:  TransportAgent 写入 → PlanWriterAgent 读取
      - transport_done:    TransportAgent 写入 → MergeNode 读取
      - plan_content:      PlanWriterAgent 写入 → MapRouteAgent 读取
    """

    # ── 对话历史（所有 Agent 共享，自动追加）──
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Supervisor 解析结果 ──
    supervisor_result: SupervisorResult

    # ── 偏好收集 ──
    preferences: Preferences
    preferences_done: bool   # false → 推送偏好卡; true → 进入规划

    # ── 天气策略（Python 纯逻辑计算）──
    weather_strategy: str    # "realtime" | "extended" | "historical"

    # ── ResearchAgent 产出 ──
    research_result: str     # 天气 + 景点信息整合文本
    research_done: bool

    # ── TransportAgent 产出 ──
    transport_result: str    # 火车/高铁信息，无出发地时为 ""
    transport_done: bool

    # ── PlanWriterAgent 产出 ──
    plan_content: str        # 完整 Markdown 攻略文本


# ────────────────────────────────────────────────────────
# 安全消息检索辅助函数
# ────────────────────────────────────────────────────────


def find_last_ai_with_tool_calls(messages: list[BaseMessage]) -> AIMessage:
    """
    从消息列表中反向查找最近一条带有 tool_calls 的 AIMessage。

    并发分支（Research ∥ Transport）可能导致 messages 交叉排列，
    最后一条消息不一定是当前 Agent 的 AIMessage。
    此函数安全地跳过 ToolMessage 等非目标消息。

    Raises:
        ValueError: 未找到带有 tool_calls 的 AIMessage
    """
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            return msg
    raise ValueError("messages 中未找到带有 tool_calls 的 AIMessage")


def find_last_ai_message(messages: list[BaseMessage]) -> AIMessage:
    """
    从消息列表中反向查找最近一条 AIMessage（无论是否含 tool_calls）。

    用于 done_node 提取最终文本内容。

    Raises:
        ValueError: 未找到 AIMessage
    """
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return msg
    raise ValueError("messages 中未找到 AIMessage")


def sanitize_messages_for_api(messages: list[BaseMessage]) -> list[BaseMessage]:
    """
    清理消息列表，确保符合 OpenAI API 的 tool_calls 配对规则。

    OpenAI API 要求：每个含 tool_calls 的 assistant message 之后
    必须紧跟对应的 tool messages（按 tool_call_id 匹配）。

    Multi-Agent 图中不同 Agent 的 tool_calls/ToolMessage 交叉排列时，
    该条件会被打破（例如 research 和 transport 并发产生的消息交错）。

    策略：
    - 遍历消息列表
    - 对含 tool_calls 的 AIMessage，检查后续是否紧跟匹配的 ToolMessage
    - 配对完整 → 保留 AIMessage + ToolMessages
    - 配对不完整 → 仅保留文本内容（去掉 tool_calls）
    - 孤立的 ToolMessage（未紧跟在其 AIMessage 后）→ 跳过
    """
    result: list[BaseMessage] = []
    i = 0
    while i < len(messages):
        msg = messages[i]

        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            # 收集此 AIMessage 的所有 tool_call_id
            expected_ids = {tc["id"] for tc in msg.tool_calls}

            # 向后扫描紧跟的 ToolMessages
            j = i + 1
            found_msgs: list[BaseMessage] = []
            found_ids: set[str] = set()
            while j < len(messages) and isinstance(messages[j], ToolMessage):
                if messages[j].tool_call_id in expected_ids:
                    found_msgs.append(messages[j])
                    found_ids.add(messages[j].tool_call_id)
                j += 1

            if expected_ids == found_ids:
                # 完整配对：保留 AIMessage + ToolMessages
                result.append(msg)
                result.extend(found_msgs)
            else:
                # 配对不完整：仅保留文本内容（去掉 tool_calls 信息）
                if msg.content:
                    result.append(AIMessage(content=msg.content))
            i = j

        elif isinstance(msg, ToolMessage):
            # 孤立的 ToolMessage（未紧跟在对应 AIMessage 后），跳过
            i += 1

        else:
            result.append(msg)
            i += 1

    return result


def extract_agent_tool_history(
    messages: list[BaseMessage],
    agent_tool_names: set[str],
) -> list[BaseMessage]:
    """
    从共享消息列表中提取属于特定 Agent 的 ReAct 循环消息。

    Multi-Agent 图中所有 Agent 共享同一个 messages 列表，
    后期 Agent（如 MapRoute）会看到前期 Agent（Research、Transport）
    的工具调用历史，可能导致 LLM 模仿调用不属于自己的工具。

    本函数基于工具名称过滤，只保留：
    - HumanMessage（用户原始请求，提供通用上下文）
    - 本 Agent 的 AIMessage + 对应 ToolMessage（基于 tool_call_id 匹配）

    对于混合调用（AIMessage 同时包含本 Agent 和其他 Agent 的 tool_calls），
    只保留本 Agent 的 tool_calls，创建新 AIMessage 避免 API 校验失败。

    Args:
        messages: 完整共享消息列表（state["messages"]）
        agent_tool_names: 本 Agent 拥有的工具名称集合

    Returns:
        仅包含 HumanMessage + 本 Agent 工具交互的干净消息列表
    """
    from langchain_core.messages import HumanMessage

    result: list[BaseMessage] = []
    keep_tool_call_ids: set[str] = set()

    for msg in messages:
        if isinstance(msg, HumanMessage):
            result.append(msg)

        elif isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            # 只保留属于本 Agent 的工具调用
            own_calls = [
                tc for tc in msg.tool_calls if tc["name"] in agent_tool_names
            ]
            if own_calls:
                result.append(
                    AIMessage(content=msg.content or "", tool_calls=own_calls)
                )
                for tc in own_calls:
                    keep_tool_call_ids.add(tc["id"])

        elif isinstance(msg, ToolMessage) and msg.tool_call_id in keep_tool_call_ids:
            result.append(msg)

        # 其他消息（Supervisor AIMessage、偏好卡、其他 Agent 文本等）跳过
        # 这些上下文已通过 SystemMessage 的 Prompt 模板注入

    return result
