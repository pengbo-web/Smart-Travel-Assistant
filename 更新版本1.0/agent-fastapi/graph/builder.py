"""
Multi-Agent 图结构组装

将所有 Agent 节点注册到 LangGraph StateGraph，
定义边（连接）和条件路由，编译生成可执行的图。

核心流程：
  START → Supervisor → [chat_agent / preference_node / weather_strategy]
  weather_strategy → Research ∥ Transport（并发）→ merge_node
  merge_node → PlanWriter → MapRoute → END
"""

from functools import partial

from langgraph.graph import END, START, StateGraph

from agents.chat_agent import chat_agent_node
from agents.map_route_agent import (
    map_route_llm_node,
    map_route_route,
    map_tool_node,
)
from agents.plan_writer_agent import (
    image_tool_node,
    plan_writer_done_node,
    plan_writer_llm_node,
    plan_writer_route,
)
from agents.preference import preference_node, weather_strategy_node
from agents.research_agent import (
    research_done_node,
    research_llm_node,
    research_route,
    research_tool_node,
)
from agents.supervisor import supervisor_node, supervisor_router
from agents.transport_agent import (
    transport_check_node,
    transport_check_router,
    transport_done_node,
    transport_llm_node,
    transport_route,
    transport_tool_node,
)
from graph.state import MultiAgentState


# ────────────────────────────────────────────────────────
# MergeNode — 并发汇合点
# ────────────────────────────────────────────────────────


async def merge_node(state: MultiAgentState) -> dict:
    """
    并发汇合点。
    LangGraph 的 fan-in 机制：当所有发往此节点的路径都到达后才执行。
    此节点本身不做任何操作，只是一个同步栅栏。
    """
    return {}


# ────────────────────────────────────────────────────────
# 图构建函数
# ────────────────────────────────────────────────────────


def build_multi_agent_graph(checkpointer, store, tool_groups: dict):
    """
    构建 Multi-Agent 协作图。

    Args:
        checkpointer: AsyncPostgresSaver 实例（对话断点持久化）
        store: AsyncPostgresStore 实例（长期记忆）
        tool_groups: split_tools() 返回的工具分组 dict
            {
                "research":  [BaseTool, ...],
                "transport": [BaseTool, ...],
                "image":     [BaseTool, ...],
                "map":       [BaseTool, ...],
            }

    Returns:
        编译后的 LangGraph CompiledStateGraph
    """
    builder = StateGraph(MultiAgentState)

    # ════════════════════════════════════════
    # 节点注册
    # ════════════════════════════════════════

    # ── 主干节点 ──
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("chat_agent", chat_agent_node)
    builder.add_node("preference_node", preference_node)
    builder.add_node("weather_strategy", weather_strategy_node)

    # ── TravelPipeline: Research 分支 ──
    builder.add_node(
        "research_llm",
        partial(research_llm_node, tools=tool_groups["research"]),
    )
    builder.add_node(
        "research_tool",
        partial(research_tool_node, tools=tool_groups["research"]),
    )
    builder.add_node("research_done", research_done_node)

    # ── TravelPipeline: Transport 分支 ──
    builder.add_node("transport_check", transport_check_node)
    builder.add_node(
        "transport_llm",
        partial(transport_llm_node, tools=tool_groups["transport"]),
    )
    builder.add_node(
        "transport_tool",
        partial(transport_tool_node, tools=tool_groups["transport"]),
    )
    builder.add_node("transport_done", transport_done_node)

    # ── TravelPipeline: 合并 + 写作 + 地图 ──
    builder.add_node("merge_node", merge_node)
    builder.add_node(
        "plan_writer_llm",
        partial(plan_writer_llm_node, tools=tool_groups["image"]),
    )
    builder.add_node(
        "image_tool",
        partial(image_tool_node, tools=tool_groups["image"]),
    )
    builder.add_node("plan_writer_done", plan_writer_done_node)
    builder.add_node("map_route_llm", map_route_llm_node)
    builder.add_node("map_tool", map_tool_node)

    # ════════════════════════════════════════
    # 边（连接）定义
    # ════════════════════════════════════════

    # ── 入口 ──
    builder.add_edge(START, "supervisor")

    # ── Supervisor 三路分发 ──
    builder.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "chat_agent": "chat_agent",
            "preference_node": "preference_node",
            "weather_strategy": "weather_strategy",
        },
    )

    # ── 闲聊 → 结束 ──
    builder.add_edge("chat_agent", END)

    # ── 偏好卡后中断（interrupt_after），等待用户选择 ──
    # preference_node 执行后图中断，resume 后重新从 supervisor 开始
    # 此时 preferences_done=true → supervisor_router → weather_strategy
    builder.add_edge("preference_node", "supervisor")

    # ── 天气策略 → 并发分叉（fan-out）──
    builder.add_edge("weather_strategy", "research_llm")     # 分叉路径 1
    builder.add_edge("weather_strategy", "transport_check")  # 分叉路径 2

    # ── Research 内部循环 ──
    builder.add_conditional_edges(
        "research_llm",
        research_route,
        {
            "call_tool": "research_tool",
            "done": "research_done",
        },
    )
    builder.add_edge("research_tool", "research_llm")
    builder.add_edge("research_done", "merge_node")

    # ── Transport 判断 + 内部循环 ──
    builder.add_conditional_edges(
        "transport_check",
        transport_check_router,
        {
            "transport_agent": "transport_llm",
            "merge_check": "merge_node",  # 无出发地，跳过直接到合并
        },
    )
    builder.add_conditional_edges(
        "transport_llm",
        transport_route,
        {
            "call_tool": "transport_tool",
            "done": "transport_done",
        },
    )
    builder.add_edge("transport_tool", "transport_llm")
    builder.add_edge("transport_done", "merge_node")

    # ── 合并 → 攻略写作 ──
    builder.add_edge("merge_node", "plan_writer_llm")

    # ── PlanWriter 内部循环 ──
    builder.add_conditional_edges(
        "plan_writer_llm",
        plan_writer_route,
        {
            "call_tool": "image_tool",
            "done": "plan_writer_done",
        },
    )
    builder.add_edge("image_tool", "plan_writer_llm")
    builder.add_edge("plan_writer_done", "map_route_llm")

    # ── MapRoute 内部循环 ──
    builder.add_conditional_edges(
        "map_route_llm",
        map_route_route,
        {
            "call_tool": "map_tool",
            "done": END,
        },
    )
    builder.add_edge("map_tool", "map_route_llm")

    # ════════════════════════════════════════
    # 编译
    # ════════════════════════════════════════
    return builder.compile(
        checkpointer=checkpointer,
        store=store,
        interrupt_after=["preference_node"],  # 偏好卡后中断
    )
