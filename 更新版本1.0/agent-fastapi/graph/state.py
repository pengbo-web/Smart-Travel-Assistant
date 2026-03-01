"""
Multi-Agent 共享状态定义

所有 Agent 节点通过 MultiAgentState 共享数据，
LangGraph 的 add_messages reducer 自动追加对话历史。
"""

from typing import Annotated

from langchain_core.messages import BaseMessage
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
