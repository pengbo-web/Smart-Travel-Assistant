"""
tests/integration/conftest.py

集成测试公共 fixtures：
- MemorySaver / InMemoryStore（替代 PostgreSQL）
- 空 tool_groups + mock tool_groups
- 预构建的 compiled graph
"""

import pytest
from unittest.mock import MagicMock

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from langchain_core.messages import AIMessage, HumanMessage


@pytest.fixture
def memory_checkpointer():
    """内存 checkpointer，替代 AsyncPostgresSaver"""
    return MemorySaver()


@pytest.fixture
def memory_store():
    """内存 store，替代 AsyncPostgresStore"""
    return InMemoryStore()


def _make_mock_tool(name: str) -> MagicMock:
    """创建一个 mock BaseTool"""
    tool = MagicMock()
    tool.name = name
    return tool


@pytest.fixture
def empty_tool_groups() -> dict[str, list]:
    """空工具组（仅用于图编译验证）"""
    return {
        "research": [],
        "transport": [],
        "image": [],
        "map": [],
    }


@pytest.fixture
def mock_tool_groups() -> dict[str, list]:
    """带 mock 工具的工具组"""
    return {
        "research": [_make_mock_tool("bailian_web_search"), _make_mock_tool("query-weather")],
        "transport": [_make_mock_tool("get-tickets"), _make_mock_tool("get-current-date")],
        "image": [_make_mock_tool("search-image")],
        "map": [_make_mock_tool("map_data")],
    }


@pytest.fixture
def travel_plan_state() -> dict:
    """一个携带 travel_plan 意图的完整 state snapshot"""
    return {
        "messages": [HumanMessage(content="帮我制定3天成都旅游攻略")],
        "supervisor_result": {
            "intent": "travel_plan",
            "destination": "成都",
            "travel_days": 3,
        },
        "preferences": {
            "travelers": "情侣",
            "pace": "舒适游",
            "style": ["自然风光", "历史文化"],
            "budget": "灵活",
            "departure": "北京",
            "travel_date": "2026-05-01",
        },
        "preferences_done": True,
        "weather_strategy": "historical",
        "research_result": "成都天气晴好，推荐景点：宽窄巷子、武侯祠、锦里",
        "research_done": True,
        "transport_result": "北京→成都 G89 高铁 8小时",
        "transport_done": True,
        "plan_content": "# 成都3天攻略\n第一天：宽窄巷子...",
    }


@pytest.fixture
def chat_state() -> dict:
    """一个闲聊意图的 state snapshot"""
    return {
        "messages": [HumanMessage(content="你好，今天天气怎么样？")],
        "supervisor_result": {
            "intent": "chat",
            "destination": "",
            "travel_days": 0,
        },
    }


@pytest.fixture
def ai_message_with_tool_calls() -> AIMessage:
    """带 tool_calls 的 AI 消息"""
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "bailian_web_search",
                "args": {"query": "成都景点"},
                "id": "call_001",
                "type": "tool_call",
            }
        ],
    )


@pytest.fixture
def ai_message_without_tool_calls() -> AIMessage:
    """不带 tool_calls 的 AI 消息（纯文本回复）"""
    return AIMessage(content="这是一段旅游攻略文本，包含宽窄巷子等景点信息。")
