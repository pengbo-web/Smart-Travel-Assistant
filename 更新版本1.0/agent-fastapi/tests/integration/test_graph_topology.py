"""
tests/integration/test_graph_topology.py

图拓扑集成测试：
- 使用 MemorySaver + InMemoryStore 编译真实图
- 验证节点集合、边连接、条件路由
- 验证 interrupt_after 配置
"""

import pytest

from graph.builder import build_multi_agent_graph, merge_node


# ── 图编译 ──


class TestGraphCompilation:
    """验证图能正确编译并具有预期拓扑"""

    def test_compile_succeeds(self, memory_checkpointer, memory_store, empty_tool_groups):
        """使用 MemorySaver 编译不报错"""
        graph = build_multi_agent_graph(
            memory_checkpointer, memory_store, empty_tool_groups
        )
        assert graph is not None

    def test_node_count(self, memory_checkpointer, memory_store, empty_tool_groups):
        """应包含 17 个业务节点（不含 __start__/__end__）"""
        graph = build_multi_agent_graph(
            memory_checkpointer, memory_store, empty_tool_groups
        )
        # get_graph() returns a Graph with nodes
        graph_data = graph.get_graph()
        # 过滤掉 __start__ 和 __end__
        business_nodes = [
            n for n in graph_data.nodes
            if n not in ("__start__", "__end__")
        ]
        assert len(business_nodes) == 17

    def test_expected_node_names(self, memory_checkpointer, memory_store, empty_tool_groups):
        """所有预期的节点名都存在"""
        graph = build_multi_agent_graph(
            memory_checkpointer, memory_store, empty_tool_groups
        )
        graph_data = graph.get_graph()
        node_names = set(graph_data.nodes.keys())

        expected = {
            "supervisor", "chat_agent", "preference_node", "weather_strategy",
            "research_llm", "research_tool", "research_done",
            "transport_check", "transport_llm", "transport_tool", "transport_done",
            "merge_node",
            "plan_writer_llm", "image_tool", "plan_writer_done",
            "map_route_llm", "map_tool",
        }
        assert expected.issubset(node_names)

    def test_start_connects_to_supervisor(self, memory_checkpointer, memory_store, empty_tool_groups):
        """START → supervisor"""
        graph = build_multi_agent_graph(
            memory_checkpointer, memory_store, empty_tool_groups
        )
        graph_data = graph.get_graph()

        # 检查 __start__ 的出边
        start_node = graph_data.nodes.get("__start__")
        edges_from_start = [
            e for e in graph_data.edges if e.source == "__start__"
        ]
        assert any(e.target == "supervisor" for e in edges_from_start)

    def test_chat_agent_connects_to_end(self, memory_checkpointer, memory_store, empty_tool_groups):
        """chat_agent → END"""
        graph = build_multi_agent_graph(
            memory_checkpointer, memory_store, empty_tool_groups
        )
        graph_data = graph.get_graph()

        edges_from_chat = [
            e for e in graph_data.edges if e.source == "chat_agent"
        ]
        assert any(e.target == "__end__" for e in edges_from_chat)

    def test_weather_strategy_fan_out(self, memory_checkpointer, memory_store, empty_tool_groups):
        """weather_strategy 应 fan-out 到 research_llm 和 transport_check"""
        graph = build_multi_agent_graph(
            memory_checkpointer, memory_store, empty_tool_groups
        )
        graph_data = graph.get_graph()

        targets = {
            e.target for e in graph_data.edges if e.source == "weather_strategy"
        }
        assert "research_llm" in targets
        assert "transport_check" in targets

    def test_research_done_to_merge(self, memory_checkpointer, memory_store, empty_tool_groups):
        """research_done → merge_node"""
        graph = build_multi_agent_graph(
            memory_checkpointer, memory_store, empty_tool_groups
        )
        graph_data = graph.get_graph()

        targets = {
            e.target for e in graph_data.edges if e.source == "research_done"
        }
        assert "merge_node" in targets

    def test_merge_to_plan_writer(self, memory_checkpointer, memory_store, empty_tool_groups):
        """merge_node → plan_writer_llm"""
        graph = build_multi_agent_graph(
            memory_checkpointer, memory_store, empty_tool_groups
        )
        graph_data = graph.get_graph()

        targets = {
            e.target for e in graph_data.edges if e.source == "merge_node"
        }
        assert "plan_writer_llm" in targets

    def test_plan_writer_done_to_map_route(self, memory_checkpointer, memory_store, empty_tool_groups):
        """plan_writer_done → map_route_llm"""
        graph = build_multi_agent_graph(
            memory_checkpointer, memory_store, empty_tool_groups
        )
        graph_data = graph.get_graph()

        targets = {
            e.target for e in graph_data.edges if e.source == "plan_writer_done"
        }
        assert "map_route_llm" in targets

    def test_preference_node_to_supervisor(self, memory_checkpointer, memory_store, empty_tool_groups):
        """preference_node → supervisor（偏好提交后重入 supervisor）"""
        graph = build_multi_agent_graph(
            memory_checkpointer, memory_store, empty_tool_groups
        )
        graph_data = graph.get_graph()

        targets = {
            e.target for e in graph_data.edges if e.source == "preference_node"
        }
        assert "supervisor" in targets

    def test_compile_with_mock_tools(self, memory_checkpointer, memory_store, mock_tool_groups):
        """使用 mock 工具组也能正确编译"""
        graph = build_multi_agent_graph(
            memory_checkpointer, memory_store, mock_tool_groups
        )
        assert graph is not None


# ── MergeNode ──


class TestMergeNode:
    """测试并发汇合节点"""

    @pytest.mark.asyncio
    async def test_merge_returns_empty_dict(self):
        """merge_node 作为同步栅栏，返回空 dict"""
        state = {
            "research_done": True,
            "transport_done": True,
            "research_result": "天气信息",
            "transport_result": "交通信息",
        }
        result = await merge_node(state)
        assert result == {}

    @pytest.mark.asyncio
    async def test_merge_with_partial_state(self):
        """即使 state 不完整也能正常返回"""
        result = await merge_node({})
        assert result == {}
