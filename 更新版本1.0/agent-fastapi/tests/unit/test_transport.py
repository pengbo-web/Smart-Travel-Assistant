"""
tests/unit/test_transport.py

测试 TransportAgent 纯逻辑：
- transport_check_node — 判断是否需要执行交通查询
- transport_check_router — 路由逻辑
"""

import pytest

from agents.transport_agent import transport_check_node, transport_check_router


class TestTransportCheckNode:
    """测试交通检查节点"""

    @pytest.mark.asyncio
    async def test_no_departure_skips(self):
        """无出发地 → 直接标记完成"""
        state = {"preferences": {"departure": ""}}
        result = await transport_check_node(state)
        assert result["transport_done"] is True
        assert result["transport_result"] == ""

    @pytest.mark.asyncio
    async def test_whitespace_departure_skips(self):
        """空白出发地 → 跳过"""
        state = {"preferences": {"departure": "   "}}
        result = await transport_check_node(state)
        assert result["transport_done"] is True

    @pytest.mark.asyncio
    async def test_with_departure_continues(self):
        """有出发地 → 返回空 dict 继续执行"""
        state = {"preferences": {"departure": "北京"}}
        result = await transport_check_node(state)
        assert result == {}

    @pytest.mark.asyncio
    async def test_missing_preferences_skips(self):
        """无 preferences 键 → 跳过"""
        state = {}
        result = await transport_check_node(state)
        assert result["transport_done"] is True

    @pytest.mark.asyncio
    async def test_missing_departure_key_skips(self):
        """preferences 中无 departure 键 → 跳过"""
        state = {"preferences": {"travelers": "情侣"}}
        result = await transport_check_node(state)
        assert result["transport_done"] is True


class TestTransportCheckRouter:
    """测试交通检查路由"""

    def test_done_routes_to_merge(self):
        """transport_done=True → merge_check"""
        state = {"transport_done": True}
        assert transport_check_router(state) == "merge_check"

    def test_not_done_routes_to_agent(self):
        """transport_done=False → transport_agent"""
        state = {"transport_done": False}
        assert transport_check_router(state) == "transport_agent"

    def test_no_done_key_routes_to_agent(self):
        """无 transport_done 键 → 视为未完成"""
        state = {}
        assert transport_check_router(state) == "transport_agent"
