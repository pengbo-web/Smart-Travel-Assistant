"""
tests/integration/test_helpers.py

集成测试：跨模块 helper 函数
- research_agent._extract_month
- graph.state TypedDict 结构验证
- PREFERENCE_CARD 与 PreferenceSubmit schema 字段对齐
"""

import pytest

from agents.research_agent import _extract_month
from agents.preference import PREFERENCE_CARD
from schemas.chat import (
    PreferenceSubmit,
    VALID_TRAVELERS,
    VALID_PACE,
    VALID_STYLE,
    VALID_BUDGET,
)


# ── _extract_month ──


class TestExtractMonth:
    """测试月份提取函数"""

    def test_normal_date(self):
        assert _extract_month("2026-05-01") == "5"

    def test_january(self):
        assert _extract_month("2026-01-15") == "1"

    def test_december(self):
        assert _extract_month("2025-12-25") == "12"

    def test_empty_string(self):
        assert _extract_month("") == ""

    def test_invalid_format(self):
        assert _extract_month("not-a-date") == ""

    def test_partial_date(self):
        """只有年月，无日"""
        assert _extract_month("2026-08") == "8"

    def test_leading_zero_stripped(self):
        """月份 '03' → '3' (int → str)"""
        assert _extract_month("2026-03-01") == "3"


# ── PREFERENCE_CARD 与 Schema 对齐 ──


class TestPreferenceCardSchemaAlignment:
    """
    验证偏好卡片前端配置与后端 Pydantic 校验的一致性。
    面试亮点：证明前后端契约的测试覆盖。
    """

    def test_card_travelers_match_schema(self):
        """PREFERENCE_CARD.travelers 选项 == VALID_TRAVELERS"""
        field = next(f for f in PREFERENCE_CARD["fields"] if f["key"] == "travelers")
        assert set(field["options"]) == VALID_TRAVELERS

    def test_card_pace_match_schema(self):
        """PREFERENCE_CARD.pace 选项 == VALID_PACE"""
        field = next(f for f in PREFERENCE_CARD["fields"] if f["key"] == "pace")
        assert set(field["options"]) == VALID_PACE

    def test_card_style_match_schema(self):
        """PREFERENCE_CARD.style 选项 == VALID_STYLE"""
        field = next(f for f in PREFERENCE_CARD["fields"] if f["key"] == "style")
        assert set(field["options"]) == VALID_STYLE

    def test_card_budget_match_schema(self):
        """PREFERENCE_CARD.budget 选项 == VALID_BUDGET"""
        field = next(f for f in PREFERENCE_CARD["fields"] if f["key"] == "budget")
        assert set(field["options"]) == VALID_BUDGET

    def test_card_fields_all_in_schema(self):
        """卡片的所有字段 key 都能作为 PreferenceSubmit 的字段"""
        card_keys = {f["key"] for f in PREFERENCE_CARD["fields"]}
        schema_keys = set(PreferenceSubmit.model_fields.keys())
        assert card_keys == schema_keys

    def test_schema_accepts_all_card_defaults(self):
        """
        使用 PREFERENCE_CARD 中每个单选的第一个选项，
        构造一个合法的 PreferenceSubmit 实例。
        """
        data = {}
        for field in PREFERENCE_CARD["fields"]:
            if field.get("multi"):
                data[field["key"]] = [field["options"][0]]
            elif "options" in field:
                data[field["key"]] = field["options"][0]
            else:
                data[field["key"]] = ""  # text/date 选填

        obj = PreferenceSubmit(**data)
        assert obj.travelers in VALID_TRAVELERS


# ── MultiAgentState 结构 ──


class TestStateStructure:
    """验证 MultiAgentState TypedDict 的字段完整性"""

    def test_state_has_all_required_fields(self):
        """MultiAgentState 包含全部 10 个字段"""
        from graph.state import MultiAgentState
        expected_keys = {
            "messages",
            "supervisor_result",
            "preferences",
            "preferences_done",
            "weather_strategy",
            "research_result",
            "research_done",
            "transport_result",
            "transport_done",
            "plan_content",
        }
        assert set(MultiAgentState.__annotations__.keys()) == expected_keys

    def test_preferences_has_six_fields(self):
        """Preferences TypedDict 包含 6 个字段"""
        from graph.state import Preferences
        expected = {"travelers", "pace", "style", "budget", "departure", "travel_date"}
        assert set(Preferences.__annotations__.keys()) == expected

    def test_supervisor_result_has_three_fields(self):
        """SupervisorResult TypedDict 包含 3 个字段"""
        from graph.state import SupervisorResult
        expected = {"intent", "destination", "travel_days"}
        assert set(SupervisorResult.__annotations__.keys()) == expected
