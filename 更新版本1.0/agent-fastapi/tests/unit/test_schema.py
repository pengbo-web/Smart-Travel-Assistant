"""
tests/unit/test_schema.py

测试 Pydantic Schema 校验：
- PreferenceSubmit 合法/非法输入
- GetConversationValidate
"""

import pytest
from pydantic import ValidationError

from schemas.chat import (
    GetConversationValidate,
    PreferenceSubmit,
    VALID_BUDGET,
    VALID_PACE,
    VALID_STYLE,
    VALID_TRAVELERS,
)


# ── PreferenceSubmit ──


class TestPreferenceSubmit:
    """验证偏好提交的 Pydantic 校验逻辑"""

    def test_valid_full_input(self, sample_preferences):
        """完整合法输入通过校验"""
        obj = PreferenceSubmit(**sample_preferences)
        assert obj.travelers == "情侣"
        assert obj.pace == "舒适游"
        assert obj.style == ["自然风光", "历史文化"]
        assert obj.budget == "灵活"
        assert obj.departure == "上海"
        assert obj.travel_date == "2026-05-01"

    def test_valid_minimal_input(self):
        """只填必填字段（departure/travel_date 默认空字符串）"""
        obj = PreferenceSubmit(
            travelers="一个人",
            pace="特种兵",
            style=["城市漫步"],
            budget="节俭",
        )
        assert obj.departure == ""
        assert obj.travel_date == ""

    def test_invalid_travelers(self):
        """无效的 travelers 值 → ValidationError"""
        with pytest.raises(ValidationError, match="travelers"):
            PreferenceSubmit(
                travelers="机器人",
                pace="舒适游",
                style=["自然风光"],
                budget="灵活",
            )

    def test_invalid_pace(self):
        """无效的 pace 值"""
        with pytest.raises(ValidationError, match="pace"):
            PreferenceSubmit(
                travelers="情侣",
                pace="极限挑战",
                style=["自然风光"],
                budget="灵活",
            )

    def test_invalid_style_option(self):
        """style 包含无效选项"""
        with pytest.raises(ValidationError, match="style"):
            PreferenceSubmit(
                travelers="情侣",
                pace="舒适游",
                style=["自然风光", "星际旅行"],
                budget="灵活",
            )

    def test_empty_style(self):
        """style 为空列表 → 校验失败"""
        with pytest.raises(ValidationError, match="style"):
            PreferenceSubmit(
                travelers="情侣",
                pace="舒适游",
                style=[],
                budget="灵活",
            )

    def test_invalid_budget(self):
        """无效的 budget 值"""
        with pytest.raises(ValidationError, match="budget"):
            PreferenceSubmit(
                travelers="情侣",
                pace="舒适游",
                style=["自然风光"],
                budget="天价",
            )

    def test_invalid_travel_date_format(self):
        """travel_date 非 YYYY-MM-DD 格式"""
        with pytest.raises(ValidationError, match="travel_date"):
            PreferenceSubmit(
                travelers="情侣",
                pace="舒适游",
                style=["自然风光"],
                budget="灵活",
                travel_date="2026/05/01",  # 错误格式
            )

    def test_missing_required_field(self):
        """缺少必填字段 → ValidationError"""
        with pytest.raises(ValidationError):
            PreferenceSubmit(
                travelers="情侣",
                # pace 缺失
                style=["自然风光"],
                budget="灵活",
            )

    def test_all_valid_travelers_options(self):
        """所有合法 travelers 选项都能通过"""
        for t in VALID_TRAVELERS:
            obj = PreferenceSubmit(
                travelers=t, pace="舒适游", style=["自然风光"], budget="灵活"
            )
            assert obj.travelers == t

    def test_all_valid_pace_options(self):
        """所有合法 pace 选项都能通过"""
        for p in VALID_PACE:
            obj = PreferenceSubmit(
                travelers="情侣", pace=p, style=["自然风光"], budget="灵活"
            )
            assert obj.pace == p

    def test_all_valid_style_options(self):
        """所有合法 style 选项都能通过（逐一单选）"""
        for s in VALID_STYLE:
            obj = PreferenceSubmit(
                travelers="情侣", pace="舒适游", style=[s], budget="灵活"
            )
            assert s in obj.style

    def test_all_valid_budget_options(self):
        """所有合法 budget 选项都能通过"""
        for b in VALID_BUDGET:
            obj = PreferenceSubmit(
                travelers="情侣", pace="舒适游", style=["自然风光"], budget=b
            )
            assert obj.budget == b

    def test_multi_select_style(self):
        """style 可多选"""
        obj = PreferenceSubmit(
            travelers="情侣",
            pace="舒适游",
            style=["自然风光", "城市漫步", "历史文化", "特色体验"],
            budget="灵活",
        )
        assert len(obj.style) == 4


# ── GetConversationValidate ──


class TestGetConversationValidate:
    """验证会话 ID 校验"""

    def test_valid_session_id(self):
        obj = GetConversationValidate(sessionId="abc-123")
        assert obj.sessionId == "abc-123"

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError, match="sessionId"):
            GetConversationValidate(sessionId="")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValidationError, match="sessionId"):
            GetConversationValidate(sessionId="   ")
