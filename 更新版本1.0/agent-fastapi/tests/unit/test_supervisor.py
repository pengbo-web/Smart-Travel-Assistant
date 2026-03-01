"""
tests/unit/test_supervisor.py

测试 Supervisor 相关纯逻辑：
- SupervisorOutput Pydantic 模型
- supervisor_router 路由函数
"""

import pytest
from pydantic import ValidationError

from agents.supervisor import SupervisorOutput, supervisor_router


# ── SupervisorOutput Pydantic Model ──


class TestSupervisorOutput:
    """验证 SupervisorOutput 结构化输出模型"""

    def test_travel_plan_intent(self):
        """合法的 travel_plan 意图"""
        obj = SupervisorOutput(
            intent="travel_plan",
            destination="成都",
            travel_days=5,
            reason="用户想去成都旅游",
        )
        assert obj.intent == "travel_plan"
        assert obj.destination == "成都"
        assert obj.travel_days == 5

    def test_chat_intent(self):
        """合法的 chat 意图"""
        obj = SupervisorOutput(
            intent="chat",
            destination="",
            travel_days=0,
            reason="用户在闲聊",
        )
        assert obj.intent == "chat"

    def test_default_travel_days(self):
        """travel_days 默认值为 3"""
        obj = SupervisorOutput(
            intent="travel_plan",
            destination="北京",
            reason="想去北京",
        )
        assert obj.travel_days == 3

    def test_invalid_intent(self):
        """无效的 intent 值 → ValidationError"""
        with pytest.raises(ValidationError):
            SupervisorOutput(
                intent="invalid_intent",
                destination="北京",
                reason="test",
            )


# ── supervisor_router ──


class TestSupervisorRouter:
    """测试 Supervisor 路由逻辑"""

    def test_chat_intent_routes_to_chat(self):
        """chat 意图 → chat_agent"""
        state = {
            "supervisor_result": {"intent": "chat", "destination": "", "travel_days": 0},
            "preferences_done": False,
        }
        assert supervisor_router(state) == "chat_agent"

    def test_travel_plan_preferences_not_done(self):
        """travel_plan + 偏好未完成 → preference_node"""
        state = {
            "supervisor_result": {"intent": "travel_plan", "destination": "西安", "travel_days": 3},
            "preferences_done": False,
        }
        assert supervisor_router(state) == "preference_node"

    def test_travel_plan_preferences_done(self):
        """travel_plan + 偏好已完成 → weather_strategy"""
        state = {
            "supervisor_result": {"intent": "travel_plan", "destination": "西安", "travel_days": 3},
            "preferences_done": True,
        }
        assert supervisor_router(state) == "weather_strategy"

    def test_travel_plan_no_preferences_done_key(self):
        """travel_plan + state 中无 preferences_done 键 → preference_node"""
        state = {
            "supervisor_result": {"intent": "travel_plan", "destination": "杭州", "travel_days": 2},
        }
        assert supervisor_router(state) == "preference_node"
