"""
tests/unit/test_preference.py

测试偏好处理逻辑：
- handle_preference_submission() 状态更新
- weather_strategy_node() 日期策略计算
- PREFERENCE_CARD 配置结构
- preference_node() 返回值格式
"""

import json
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from agents.preference import (
    PREFERENCE_CARD,
    handle_preference_submission,
    preference_node,
    weather_strategy_node,
)


# ── PREFERENCE_CARD 配置 ──


class TestPreferenceCard:
    """验证偏好卡片配置的完整性"""

    def test_has_question(self):
        assert "question" in PREFERENCE_CARD
        assert isinstance(PREFERENCE_CARD["question"], str)

    def test_has_six_fields(self):
        assert len(PREFERENCE_CARD["fields"]) == 6

    def test_field_keys(self):
        keys = [f["key"] for f in PREFERENCE_CARD["fields"]]
        assert keys == ["travelers", "pace", "style", "budget", "departure", "travel_date"]

    def test_multi_select_only_style(self):
        """只有 style 是多选"""
        for field in PREFERENCE_CARD["fields"]:
            if field["key"] == "style":
                assert field.get("multi") is True
            elif "multi" in field:
                assert field["multi"] is False

    def test_text_fields_have_placeholder(self):
        """departure 和 travel_date 是文本输入，必须有 placeholder"""
        text_fields = [f for f in PREFERENCE_CARD["fields"] if f.get("type") in ("text", "date")]
        assert len(text_fields) == 2
        for f in text_fields:
            assert "placeholder" in f


# ── handle_preference_submission() ──


class TestHandlePreferenceSubmission:
    """测试偏好提交的状态更新逻辑"""

    @pytest.mark.asyncio
    async def test_with_departure(self, sample_preferences):
        """有出发地 → transport_done=False"""
        result = await handle_preference_submission(sample_preferences)

        assert result["preferences"] == sample_preferences
        assert result["preferences_done"] is True
        assert result["transport_done"] is False  # 有出发地，需查交通
        assert result["transport_result"] == ""

    @pytest.mark.asyncio
    async def test_without_departure(self, minimal_preferences):
        """无出发地 → transport_done=True，跳过交通查询"""
        result = await handle_preference_submission(minimal_preferences)

        assert result["preferences_done"] is True
        assert result["transport_done"] is True  # 无出发地，直接跳过

    @pytest.mark.asyncio
    async def test_whitespace_departure(self):
        """departure 是空白字符 → 视为无出发地"""
        prefs = {
            "travelers": "朋友",
            "pace": "舒适游",
            "style": ["自然风光"],
            "budget": "灵活",
            "departure": "   ",  # 纯空白
        }
        result = await handle_preference_submission(prefs)
        assert result["transport_done"] is True

    @pytest.mark.asyncio
    async def test_missing_departure_key(self):
        """没有 departure 键 → 视为无出发地"""
        prefs = {
            "travelers": "家庭",
            "pace": "特种兵",
            "style": ["特色体验"],
            "budget": "节俭",
        }
        result = await handle_preference_submission(prefs)
        assert result["transport_done"] is True


# ── weather_strategy_node() ──


class TestWeatherStrategyNode:
    """测试天气策略计算的各个分支"""

    @pytest.mark.asyncio
    async def test_no_date_returns_realtime(self):
        """未填日期 → realtime"""
        state = {"preferences": {"travel_date": ""}}
        result = await weather_strategy_node(state)
        assert result["weather_strategy"] == "realtime"

    @pytest.mark.asyncio
    async def test_empty_preferences_returns_realtime(self):
        """preferences 为空 dict → realtime"""
        state = {"preferences": {}}
        result = await weather_strategy_node(state)
        assert result["weather_strategy"] == "realtime"

    @pytest.mark.asyncio
    async def test_no_preferences_key_returns_realtime(self):
        """state 无 preferences 键 → realtime"""
        state = {}
        result = await weather_strategy_node(state)
        assert result["weather_strategy"] == "realtime"

    @pytest.mark.asyncio
    async def test_within_7_days_returns_realtime(self):
        """出行日期在 7 天内 → realtime"""
        travel_date = (date.today() + timedelta(days=3)).isoformat()
        state = {"preferences": {"travel_date": travel_date}}
        result = await weather_strategy_node(state)
        assert result["weather_strategy"] == "realtime"

    @pytest.mark.asyncio
    async def test_exactly_7_days_returns_realtime(self):
        """出行日期恰好在第 7 天 → realtime（<=7）"""
        travel_date = (date.today() + timedelta(days=7)).isoformat()
        state = {"preferences": {"travel_date": travel_date}}
        result = await weather_strategy_node(state)
        assert result["weather_strategy"] == "realtime"

    @pytest.mark.asyncio
    async def test_8_to_15_days_returns_extended(self):
        """出行日期在 8-15 天 → extended"""
        travel_date = (date.today() + timedelta(days=10)).isoformat()
        state = {"preferences": {"travel_date": travel_date}}
        result = await weather_strategy_node(state)
        assert result["weather_strategy"] == "extended"

    @pytest.mark.asyncio
    async def test_exactly_15_days_returns_extended(self):
        """出行日期恰好在第 15 天 → extended（<=15）"""
        travel_date = (date.today() + timedelta(days=15)).isoformat()
        state = {"preferences": {"travel_date": travel_date}}
        result = await weather_strategy_node(state)
        assert result["weather_strategy"] == "extended"

    @pytest.mark.asyncio
    async def test_over_15_days_returns_historical(self):
        """出行日期超过 15 天 → historical"""
        travel_date = (date.today() + timedelta(days=30)).isoformat()
        state = {"preferences": {"travel_date": travel_date}}
        result = await weather_strategy_node(state)
        assert result["weather_strategy"] == "historical"

    @pytest.mark.asyncio
    async def test_invalid_date_format_fallback(self):
        """无效日期格式 → 兜底 realtime"""
        state = {"preferences": {"travel_date": "not-a-date"}}
        result = await weather_strategy_node(state)
        assert result["weather_strategy"] == "realtime"

    @pytest.mark.asyncio
    async def test_past_date_returns_realtime(self):
        """过去的日期 delta < 0 → realtime（<=7 分支覆盖）"""
        travel_date = (date.today() - timedelta(days=5)).isoformat()
        state = {"preferences": {"travel_date": travel_date}}
        result = await weather_strategy_node(state)
        assert result["weather_strategy"] == "realtime"


# ── preference_node() ──


class TestPreferenceNode:
    """测试偏好节点返回的消息格式"""

    @pytest.mark.asyncio
    async def test_returns_ai_message(self):
        """返回包含 AIMessage 的 dict"""
        state = {"messages": []}
        result = await preference_node(state)

        assert "messages" in result
        assert len(result["messages"]) == 1

        msg = result["messages"][0]
        assert msg.additional_kwargs.get("type") == "preference_card"

    @pytest.mark.asyncio
    async def test_message_content_is_valid_json(self):
        """AIMessage.content 是合法 JSON"""
        state = {"messages": []}
        result = await preference_node(state)
        msg = result["messages"][0]

        card = json.loads(msg.content)
        assert "question" in card
        assert "fields" in card
