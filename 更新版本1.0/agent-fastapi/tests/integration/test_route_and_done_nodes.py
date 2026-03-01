"""
tests/integration/test_route_and_done_nodes.py

集成测试：路由函数 + done 节点
使用真实 LangChain 消息对象验证路由逻辑和状态提取。
"""

import pytest
from typing import cast

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agents.research_agent import research_route, research_done_node
from agents.transport_agent import transport_route, transport_done_node
from agents.plan_writer_agent import plan_writer_route, plan_writer_done_node
from agents.map_route_agent import map_route_route


# ════════════════════════════════════════════════════════
# 路由函数测试（使用真实 AIMessage 对象）
# ════════════════════════════════════════════════════════


class TestResearchRoute:
    """测试 research_route 与真实 AIMessage 交互"""

    def test_with_tool_calls_returns_call_tool(self, ai_message_with_tool_calls):
        """AI 消息包含 tool_calls → 'call_tool'"""
        state = {"messages": [ai_message_with_tool_calls]}
        assert research_route(state) == "call_tool"

    def test_without_tool_calls_returns_done(self, ai_message_without_tool_calls):
        """AI 消息无 tool_calls → 'done'"""
        state = {"messages": [ai_message_without_tool_calls]}
        assert research_route(state) == "done"

    def test_empty_tool_calls_returns_done(self):
        """tool_calls 为空列表 → 'done'"""
        msg = AIMessage(content="搜索完毕", tool_calls=[])
        state = {"messages": [msg]}
        assert research_route(state) == "done"


class TestTransportRoute:
    """测试 transport_route 与真实 AIMessage 交互"""

    def test_with_tool_calls(self):
        """带 tool_calls → 'call_tool'"""
        msg = AIMessage(
            content="",
            tool_calls=[{
                "name": "get-tickets",
                "args": {"from": "北京", "to": "成都"},
                "id": "call_t01",
                "type": "tool_call",
            }],
        )
        state = {"messages": [msg]}
        assert transport_route(state) == "call_tool"

    def test_without_tool_calls(self, ai_message_without_tool_calls):
        """无 tool_calls → 'done'"""
        state = {"messages": [ai_message_without_tool_calls]}
        assert transport_route(state) == "done"


class TestPlanWriterRoute:
    """测试 plan_writer_route 与真实 AIMessage 交互"""

    def test_with_image_tool_call(self):
        """请求搜索图片 → 'call_tool'"""
        msg = AIMessage(
            content="",
            tool_calls=[{
                "name": "search-image",
                "args": {"query": "宽窄巷子"},
                "id": "call_img01",
                "type": "tool_call",
            }],
        )
        state = {"messages": [msg]}
        assert plan_writer_route(state) == "call_tool"

    def test_final_plan_text(self, ai_message_without_tool_calls):
        """生成纯文本攻略 → 'done'"""
        state = {"messages": [ai_message_without_tool_calls]}
        assert plan_writer_route(state) == "done"

    def test_multiple_tool_calls(self):
        """多个图片搜索 → 'call_tool'"""
        msg = AIMessage(
            content="",
            tool_calls=[
                {"name": "search-image", "args": {"query": "宽窄巷子"}, "id": "c1", "type": "tool_call"},
                {"name": "search-image", "args": {"query": "武侯祠"}, "id": "c2", "type": "tool_call"},
            ],
        )
        state = {"messages": [msg]}
        assert plan_writer_route(state) == "call_tool"


class TestMapRouteRoute:
    """测试 map_route_route"""

    def test_with_map_tool_call(self):
        """调用 map_data → 'call_tool'"""
        msg = AIMessage(
            content="",
            tool_calls=[{
                "name": "map_data",
                "args": {
                    "from_location": "30.572,104.066",
                    "to_location": "30.652,104.082",
                    "day": "第一天",
                    "markers": [],
                },
                "id": "call_map01",
                "type": "tool_call",
            }],
        )
        state = {"messages": [msg]}
        assert map_route_route(state) == "call_tool"

    def test_no_more_map_calls(self, ai_message_without_tool_calls):
        """地图规划完毕 → 'done'（到 END）"""
        state = {"messages": [ai_message_without_tool_calls]}
        assert map_route_route(state) == "done"


# ════════════════════════════════════════════════════════
# Done 节点测试（使用真实 AIMessage 对象）
# ════════════════════════════════════════════════════════


class TestResearchDoneNode:
    """测试 research_done_node 提取 research_result"""

    @pytest.mark.asyncio
    async def test_extracts_content(self):
        """正确提取最后一条 AI 消息内容"""
        content = "成都5月天气：平均25℃，多云。推荐景点：宽窄巷子、武侯祠、锦里、都江堰。"
        state = {
            "messages": [
                HumanMessage(content="查查成都的信息"),
                AIMessage(content=content),
            ]
        }
        result = await research_done_node(state)
        assert result["research_result"] == content
        assert result["research_done"] is True

    @pytest.mark.asyncio
    async def test_with_tool_result_in_history(self):
        """消息历史中包含 ToolMessage，done 节点仍取最后一条 AIMessage"""
        state = {
            "messages": [
                HumanMessage(content="查天气"),
                AIMessage(content="", tool_calls=[{
                    "name": "query-weather", "args": {}, "id": "c1", "type": "tool_call"
                }]),
                ToolMessage(content="成都 25℃ 多云", tool_call_id="c1"),
                AIMessage(content="成都近期天气以多云为主，气温约25℃。"),
            ]
        }
        result = await research_done_node(state)
        assert "25℃" in result["research_result"]
        assert result["research_done"] is True


class TestTransportDoneNode:
    """测试 transport_done_node 提取 transport_result"""

    @pytest.mark.asyncio
    async def test_extracts_content(self):
        """正确提取交通查询结果"""
        content = "北京→成都 G89 高铁 约8小时，二等座 ¥780"
        state = {
            "messages": [
                HumanMessage(content="查交通"),
                AIMessage(content=content),
            ]
        }
        result = await transport_done_node(state)
        assert result["transport_result"] == content
        assert result["transport_done"] is True


class TestPlanWriterDoneNode:
    """测试 plan_writer_done_node 提取 plan_content"""

    @pytest.mark.asyncio
    async def test_extracts_plan_content(self):
        """正确提取攻略全文"""
        plan = "# 成都3天攻略\n\n## 第一天\n上午：宽窄巷子\n下午：武侯祠\n晚上：锦里"
        state = {
            "messages": [
                HumanMessage(content="做攻略"),
                AIMessage(content=plan),
            ]
        }
        result = await plan_writer_done_node(state)
        assert result["plan_content"] == plan

    @pytest.mark.asyncio
    async def test_plan_content_after_image_search(self):
        """经过图片搜索循环后，最后的 AI 消息是完整攻略"""
        plan = "# 成都3天美食+文化之旅\n\n![宽窄巷子](https://example.com/img.jpg)\n\n## 第一天..."
        state = {
            "messages": [
                HumanMessage(content="做攻略"),
                AIMessage(content="", tool_calls=[{
                    "name": "search-image", "args": {"query": "宽窄巷子"},
                    "id": "c1", "type": "tool_call"
                }]),
                ToolMessage(content="https://example.com/img.jpg", tool_call_id="c1"),
                AIMessage(content=plan),
            ]
        }
        result = await plan_writer_done_node(state)
        assert result["plan_content"] == plan
