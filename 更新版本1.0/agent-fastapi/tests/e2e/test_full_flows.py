"""
tests/e2e/test_full_flows.py

端到端测试：完整图执行流程

测试策略：
  - 仅 mock LLM 调用节点（supervisor, chat_agent, research_llm,
    transport_llm, plan_writer_llm, map_route_llm）
  - 保留所有路由函数 + done 节点 + 纯逻辑节点
    （preference_node, weather_strategy, transport_check, merge）
  - 使用 MemorySaver + InMemoryStore 替代 PostgreSQL
  - 验证真实图拓扑的完整路由 + 状态流转 + interrupt/resume

覆盖 3 个关键流程：
  1. 闲聊流程: user → supervisor → chat_agent → END
  2. 偏好中断流程: user → supervisor → preference_node → INTERRUPT
  3. 完整旅游流水线: interrupt → resume → weather_strategy →
     research ∥ transport → merge → plan_writer → map_route → END
"""

import pytest
from datetime import date, timedelta
from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from graph.builder import build_multi_agent_graph
from agents.preference import handle_preference_submission


# ════════════════════════════════════════════════════════
# Mock 节点函数（仅替换需要 LLM 调用的节点）
# ════════════════════════════════════════════════════════


async def mock_supervisor_chat(state):
    """模拟 Supervisor: 返回闲聊意图"""
    return {
        "supervisor_result": {
            "intent": "chat",
            "destination": "",
            "travel_days": 0,
        },
    }


async def mock_supervisor_travel(state):
    """
    模拟 Supervisor: 返回旅游规划意图。

    复刻真实 supervisor_node 的条件逻辑：
    - 首次调用（偏好未完成）→ 初始化偏好标记
    - 再次调用（偏好已完成 ← resume 后）→ 仅返回 supervisor_result
    """
    update: dict = {
        "supervisor_result": {
            "intent": "travel_plan",
            "destination": "成都",
            "travel_days": 3,
        },
    }
    if not state.get("preferences_done"):
        update["preferences_done"] = False
        update["transport_done"] = False
        update["research_done"] = False
        update["transport_result"] = ""
    return update


async def mock_chat_agent(state):
    """模拟闲聊节点: 返回固定回复"""
    return {
        "messages": [AIMessage(content="你好！我是旅游助手，有什么可以帮你的吗？")],
    }


async def mock_research_llm(state, tools=None):
    """模拟 ResearchAgent LLM: 直接返回结果，无 tool_calls → 走 'done' 路由"""
    dest = state.get("supervisor_result", {}).get("destination", "未知")
    return {
        "messages": [
            AIMessage(
                content=f"{dest}景点信息：宽窄巷子、武侯祠、锦里。天气：5月平均25℃，多云为主。"
            )
        ],
    }


async def mock_transport_llm(state, tools=None):
    """模拟 TransportAgent LLM: 直接返回结果，无 tool_calls → 走 'done' 路由"""
    dep = state.get("preferences", {}).get("departure", "")
    dest = state.get("supervisor_result", {}).get("destination", "未知")
    return {
        "messages": [
            AIMessage(content=f"{dep}→{dest} G89 高铁 约8小时，二等座 ¥780")
        ],
    }


async def mock_plan_writer_llm(state, tools=None):
    """模拟 PlanWriterAgent LLM: 直接返回攻略，无 tool_calls → 走 'done' 路由"""
    dest = state.get("supervisor_result", {}).get("destination", "未知")
    days = state.get("supervisor_result", {}).get("travel_days", 3)
    return {
        "messages": [
            AIMessage(
                content=f"# {dest}{days}天攻略\n\n## 第一天\n上午：宽窄巷子\n下午：武侯祠\n晚上：锦里"
            )
        ],
    }


async def mock_map_route_llm(state):
    """模拟 MapRouteAgent LLM: 直接返回路线描述，无 tool_calls → 走 'done' 路由"""
    return {
        "messages": [
            AIMessage(
                content="路线规划已完成。第一天：宽窄巷子→武侯祠→锦里，全程约12公里。"
            )
        ],
    }


# ════════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════════

EMPTY_TOOLS = {"research": [], "transport": [], "image": [], "map": []}

# 6 个 LLM 节点的 patch 目标路径（在 graph.builder 模块中）
TRAVEL_PATCHES = {
    "graph.builder.supervisor_node": mock_supervisor_travel,
    "graph.builder.research_llm_node": mock_research_llm,
    "graph.builder.transport_llm_node": mock_transport_llm,
    "graph.builder.plan_writer_llm_node": mock_plan_writer_llm,
    "graph.builder.map_route_llm_node": mock_map_route_llm,
}


def _build_graph():
    """构建图实例（使用内存后端）"""
    return build_multi_agent_graph(MemorySaver(), InMemoryStore(), EMPTY_TOOLS)


# ════════════════════════════════════════════════════════
# 测试 1: 闲聊流程 E2E
# ════════════════════════════════════════════════════════


class TestChatFlowE2E:
    """
    E2E: 闲聊流程
    user message → supervisor(chat) → chat_agent → END

    仅 mock 2 个节点: supervisor_node, chat_agent_node
    """

    @pytest.mark.asyncio
    @patch("graph.builder.supervisor_node", new=mock_supervisor_chat)
    @patch("graph.builder.chat_agent_node", new=mock_chat_agent)
    async def test_chat_returns_ai_response(self):
        """闲聊消息成功通过图返回 AI 回复"""
        graph = _build_graph()
        config = {"configurable": {"thread_id": "e2e-chat-001"}}

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="你好")]},
            config=config,
        )

        messages = result["messages"]
        assert len(messages) >= 2  # user + ai
        last_ai = messages[-1]
        assert isinstance(last_ai, AIMessage)
        assert "旅游助手" in last_ai.content

    @pytest.mark.asyncio
    @patch("graph.builder.supervisor_node", new=mock_supervisor_chat)
    @patch("graph.builder.chat_agent_node", new=mock_chat_agent)
    async def test_chat_state_correct(self):
        """闲聊后 state 包含正确的 supervisor_result"""
        graph = _build_graph()
        config = {"configurable": {"thread_id": "e2e-chat-002"}}

        await graph.ainvoke(
            {"messages": [HumanMessage(content="今天天气怎么样")]},
            config=config,
        )

        state = await graph.aget_state(config)
        sr = state.values.get("supervisor_result")
        assert sr is not None
        assert sr["intent"] == "chat"

    @pytest.mark.asyncio
    @patch("graph.builder.supervisor_node", new=mock_supervisor_chat)
    @patch("graph.builder.chat_agent_node", new=mock_chat_agent)
    async def test_chat_graph_completed(self):
        """闲聊后图完成执行（无后续节点）"""
        graph = _build_graph()
        config = {"configurable": {"thread_id": "e2e-chat-003"}}

        await graph.ainvoke(
            {"messages": [HumanMessage(content="你好")]},
            config=config,
        )

        state = await graph.aget_state(config)
        assert not state.next, "闲聊流程应到达 END"


# ════════════════════════════════════════════════════════
# 测试 2: 偏好中断流程 E2E
# ════════════════════════════════════════════════════════


class TestPreferenceInterruptE2E:
    """
    E2E: 旅游请求触发偏好卡中断
    user → supervisor(travel_plan) → preference_node → INTERRUPT

    仅 mock 1 个节点: supervisor_node
    preference_node 使用真实代码（纯逻辑，无 LLM）
    """

    @pytest.mark.asyncio
    @patch("graph.builder.supervisor_node", new=mock_supervisor_travel)
    async def test_graph_interrupts_at_preference(self):
        """旅游请求后图在 preference_node 中断"""
        graph = _build_graph()
        config = {"configurable": {"thread_id": "e2e-pref-001"}}

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="帮我制定3天成都旅游攻略")]},
            config=config,
        )

        # 验证图已中断
        state = await graph.aget_state(config)
        assert state.next, "图应在 preference_node 后中断"

    @pytest.mark.asyncio
    @patch("graph.builder.supervisor_node", new=mock_supervisor_travel)
    async def test_preference_card_message_sent(self):
        """中断时消息历史包含偏好卡片"""
        graph = _build_graph()
        config = {"configurable": {"thread_id": "e2e-pref-002"}}

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="帮我制定3天成都旅游攻略")]},
            config=config,
        )

        preference_msgs = [
            m
            for m in result["messages"]
            if isinstance(m, AIMessage)
            and m.additional_kwargs.get("type") == "preference_card"
        ]
        assert len(preference_msgs) == 1, "应有一条偏好卡片消息"

    @pytest.mark.asyncio
    @patch("graph.builder.supervisor_node", new=mock_supervisor_travel)
    async def test_preference_card_contains_fields(self):
        """偏好卡片 JSON 包含 question 和 fields"""
        import json

        graph = _build_graph()
        config = {"configurable": {"thread_id": "e2e-pref-003"}}

        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="去成都玩")]},
            config=config,
        )

        card_msg = next(
            m
            for m in result["messages"]
            if isinstance(m, AIMessage)
            and m.additional_kwargs.get("type") == "preference_card"
        )
        card = json.loads(card_msg.content)
        assert "question" in card
        assert len(card["fields"]) == 6


# ════════════════════════════════════════════════════════
# 测试 3: 完整旅游规划流水线 E2E
# ════════════════════════════════════════════════════════


class TestFullTravelPipelineE2E:
    """
    E2E: 完整旅游规划流水线（interrupt → resume → 全流程）

    Mock 5 个 LLM 节点，保留全部路由函数 + 纯逻辑节点：
      supervisor_router, preference_node, weather_strategy_node,
      transport_check_node, transport_check_router,
      research_route, transport_route, plan_writer_route, map_route_route,
      research_done_node, transport_done_node, plan_writer_done_node, merge_node
    """

    @pytest.mark.asyncio
    async def test_full_pipeline_no_departure(self):
        """
        无出发地流程 — transport 被跳过

        流程：preference(interrupt) → resume →
              weather_strategy(historical) →
              research(done) ∥ transport_check(skip→merge) →
              merge → plan_writer(done) → map_route(done) → END

        验证点：
          - weather_strategy = "historical"（30天后）
          - transport_done = True, transport_result = ""
          - research_done = True, research_result 非空
          - plan_content 包含目的地
          - 图到达 END
        """
        with (
            patch("graph.builder.supervisor_node", new=mock_supervisor_travel),
            patch("graph.builder.research_llm_node", new=mock_research_llm),
            patch("graph.builder.transport_llm_node", new=mock_transport_llm),
            patch("graph.builder.plan_writer_llm_node", new=mock_plan_writer_llm),
            patch("graph.builder.map_route_llm_node", new=mock_map_route_llm),
        ):
            graph = _build_graph()
            config = {"configurable": {"thread_id": "e2e-full-001"}}

            # ── Step 1: 首次调用 → 偏好中断 ──
            await graph.ainvoke(
                {"messages": [HumanMessage(content="帮我制定3天成都旅游攻略")]},
                config=config,
            )

            # ── Step 2: 提交偏好（无出发地） ──
            travel_date = (date.today() + timedelta(days=30)).isoformat()
            preferences = {
                "travelers": "情侣",
                "pace": "舒适游",
                "style": ["自然风光", "历史文化"],
                "budget": "灵活",
                "departure": "",  # ★ 无出发地
                "travel_date": travel_date,
            }
            state_update = await handle_preference_submission(preferences)
            await graph.aupdate_state(config, state_update)

            # ── Step 3: Resume → 执行完整流水线 ──
            await graph.ainvoke(None, config=config)

            # ── 验证最终状态 ──
            final_state = await graph.aget_state(config)
            vals = final_state.values

            assert vals.get("preferences_done") is True
            assert vals.get("weather_strategy") == "historical"
            assert vals.get("research_done") is True
            assert "成都" in vals.get("research_result", "")
            assert vals.get("transport_done") is True
            assert vals.get("transport_result") == ""  # 跳过交通
            assert "成都" in vals.get("plan_content", "")
            assert "攻略" in vals.get("plan_content", "")
            assert not final_state.next  # 到达 END

    @pytest.mark.asyncio
    async def test_full_pipeline_with_departure(self):
        """
        有出发地流程 — transport 正常执行

        流程：preference(interrupt) → resume →
              weather_strategy(realtime) →
              research(done) ∥ transport_check→transport_llm(done)→transport_done →
              merge → plan_writer(done) → map_route(done) → END

        验证点：
          - weather_strategy = "realtime"（5天内）
          - transport_result 包含出发地和目的地
          - research/plan/map 全部完成
          - 图到达 END
        """
        with (
            patch("graph.builder.supervisor_node", new=mock_supervisor_travel),
            patch("graph.builder.research_llm_node", new=mock_research_llm),
            patch("graph.builder.transport_llm_node", new=mock_transport_llm),
            patch("graph.builder.plan_writer_llm_node", new=mock_plan_writer_llm),
            patch("graph.builder.map_route_llm_node", new=mock_map_route_llm),
        ):
            graph = _build_graph()
            config = {"configurable": {"thread_id": "e2e-full-002"}}

            # ── Step 1: 触发偏好中断 ──
            await graph.ainvoke(
                {"messages": [HumanMessage(content="帮我制定3天成都旅游攻略")]},
                config=config,
            )

            # ── Step 2: 提交偏好（有出发地） ──
            travel_date = (date.today() + timedelta(days=5)).isoformat()
            preferences = {
                "travelers": "家庭",
                "pace": "特种兵",
                "style": ["城市漫步", "特色体验"],
                "budget": "节俭",
                "departure": "北京",  # ★ 有出发地
                "travel_date": travel_date,
            }
            state_update = await handle_preference_submission(preferences)
            await graph.aupdate_state(config, state_update)

            # ── Step 3: Resume ──
            await graph.ainvoke(None, config=config)

            # ── 验证 ──
            final_state = await graph.aget_state(config)
            vals = final_state.values

            assert vals.get("weather_strategy") == "realtime"
            assert vals.get("research_done") is True
            assert vals.get("transport_done") is True
            assert "北京" in vals.get("transport_result", "")
            assert "成都" in vals.get("transport_result", "")
            assert vals.get("plan_content") is not None
            assert len(vals["plan_content"]) > 0
            assert not final_state.next

    @pytest.mark.asyncio
    async def test_message_history_accumulated(self):
        """
        验证完整流程中消息历史被正确追加

        检查 messages 包含：
          - 用户原始消息（HumanMessage）
          - 偏好卡片（AIMessage with type=preference_card）
          - 各 Agent 产出的 AIMessage
        """
        with (
            patch("graph.builder.supervisor_node", new=mock_supervisor_travel),
            patch("graph.builder.research_llm_node", new=mock_research_llm),
            patch("graph.builder.transport_llm_node", new=mock_transport_llm),
            patch("graph.builder.plan_writer_llm_node", new=mock_plan_writer_llm),
            patch("graph.builder.map_route_llm_node", new=mock_map_route_llm),
        ):
            graph = _build_graph()
            config = {"configurable": {"thread_id": "e2e-full-003"}}

            # Step 1
            await graph.ainvoke(
                {"messages": [HumanMessage(content="帮我制定成都攻略")]},
                config=config,
            )

            # Step 2: 无出发地，跳过 transport
            preferences = {
                "travelers": "一个人",
                "pace": "无偏好",
                "style": ["自然风光"],
                "budget": "灵活",
                "departure": "",
                "travel_date": "",
            }
            state_update = await handle_preference_submission(preferences)
            await graph.aupdate_state(config, state_update)

            # Step 3
            await graph.ainvoke(None, config=config)

            # ── 验证消息历史 ──
            final_state = await graph.aget_state(config)
            messages = final_state.values.get("messages", [])

            # 至少 4 条: user + preference_card + research + plan + map_route
            assert len(messages) >= 4, f"消息历史应至少4条，实际 {len(messages)}"

            # 第一条是用户消息
            assert isinstance(messages[0], HumanMessage)
            assert "成都" in messages[0].content

            # 包含偏好卡片
            has_preference = any(
                isinstance(m, AIMessage)
                and m.additional_kwargs.get("type") == "preference_card"
                for m in messages
            )
            assert has_preference, "消息历史应包含偏好卡片"

            # 包含攻略文本
            has_plan = any(
                isinstance(m, AIMessage) and "攻略" in (m.content or "")
                for m in messages
            )
            assert has_plan, "消息历史应包含攻略文本"

    @pytest.mark.asyncio
    async def test_weather_strategy_extended(self):
        """
        验证 extended 天气策略（出行日期 8-15 天）在完整流水线中正确计算
        """
        with (
            patch("graph.builder.supervisor_node", new=mock_supervisor_travel),
            patch("graph.builder.research_llm_node", new=mock_research_llm),
            patch("graph.builder.transport_llm_node", new=mock_transport_llm),
            patch("graph.builder.plan_writer_llm_node", new=mock_plan_writer_llm),
            patch("graph.builder.map_route_llm_node", new=mock_map_route_llm),
        ):
            graph = _build_graph()
            config = {"configurable": {"thread_id": "e2e-full-004"}}

            await graph.ainvoke(
                {"messages": [HumanMessage(content="去成都玩")]},
                config=config,
            )

            # 10 天后出发 → extended
            travel_date = (date.today() + timedelta(days=10)).isoformat()
            preferences = {
                "travelers": "朋友",
                "pace": "舒适游",
                "style": ["特色体验"],
                "budget": "奢侈",
                "departure": "",
                "travel_date": travel_date,
            }
            state_update = await handle_preference_submission(preferences)
            await graph.aupdate_state(config, state_update)

            await graph.ainvoke(None, config=config)

            final_state = await graph.aget_state(config)
            assert final_state.values.get("weather_strategy") == "extended"
            assert not final_state.next

    @pytest.mark.asyncio
    async def test_preferences_stored_in_state(self):
        """
        验证用户提交的偏好数据被完整保存到 state.preferences
        """
        with (
            patch("graph.builder.supervisor_node", new=mock_supervisor_travel),
            patch("graph.builder.research_llm_node", new=mock_research_llm),
            patch("graph.builder.transport_llm_node", new=mock_transport_llm),
            patch("graph.builder.plan_writer_llm_node", new=mock_plan_writer_llm),
            patch("graph.builder.map_route_llm_node", new=mock_map_route_llm),
        ):
            graph = _build_graph()
            config = {"configurable": {"thread_id": "e2e-full-005"}}

            await graph.ainvoke(
                {"messages": [HumanMessage(content="成都3天游")]},
                config=config,
            )

            preferences = {
                "travelers": "情侣",
                "pace": "特种兵",
                "style": ["自然风光", "城市漫步"],
                "budget": "灵活",
                "departure": "上海",
                "travel_date": "2026-06-01",
            }
            state_update = await handle_preference_submission(preferences)
            await graph.aupdate_state(config, state_update)

            await graph.ainvoke(None, config=config)

            final_state = await graph.aget_state(config)
            stored_prefs = final_state.values.get("preferences", {})
            assert stored_prefs["travelers"] == "情侣"
            assert stored_prefs["pace"] == "特种兵"
            assert set(stored_prefs["style"]) == {"自然风光", "城市漫步"}
            assert stored_prefs["budget"] == "灵活"
            assert stored_prefs["departure"] == "上海"
