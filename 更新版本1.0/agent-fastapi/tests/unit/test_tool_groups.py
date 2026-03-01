"""
tests/unit/test_tool_groups.py

测试工具分组逻辑：
- TOOL_GROUPS 配置完整性
- split_tools() 分组正确性
- 未分配工具检测
"""

from unittest.mock import MagicMock

import pytest

from graph.tool_groups import TOOL_GROUPS, split_tools


# ── TOOL_GROUPS 配置 ──


class TestToolGroupsConfig:
    """验证 TOOL_GROUPS 常量的结构与完整性"""

    def test_has_all_four_groups(self):
        """必须包含 4 个分组: research, transport, image, map"""
        expected = {"research", "transport", "image", "map"}
        assert set(TOOL_GROUPS.keys()) == expected

    def test_research_tools_count(self):
        """research 组应有 4 个工具"""
        assert len(TOOL_GROUPS["research"]) == 4

    def test_transport_tools_count(self):
        """transport 组应有 8 个工具"""
        assert len(TOOL_GROUPS["transport"]) == 8

    def test_image_tools_count(self):
        """image 组应有 1 个工具"""
        assert len(TOOL_GROUPS["image"]) == 1

    def test_map_tools_count(self):
        """map 组应有 1 个工具"""
        assert len(TOOL_GROUPS["map"]) == 1

    def test_no_duplicate_tools_across_groups(self):
        """工具名不应在多个分组中重复出现"""
        all_tools = []
        for names in TOOL_GROUPS.values():
            all_tools.extend(names)
        assert len(all_tools) == len(set(all_tools)), "存在跨组重复工具"

    def test_map_data_in_map_group(self):
        """本地工具 map_data 在 map 组"""
        assert "map_data" in TOOL_GROUPS["map"]

    def test_search_image_in_image_group(self):
        """search-image 在 image 组"""
        assert "search-image" in TOOL_GROUPS["image"]


# ── split_tools() 函数 ──


def _make_mock_tool(name: str) -> MagicMock:
    """创建一个 mock BaseTool，仅设 .name"""
    tool = MagicMock()
    tool.name = name
    return tool


class TestSplitTools:
    """测试 split_tools() 分组函数"""

    def test_basic_split(self):
        """提供部分工具，验证正确分组"""
        tools = [
            _make_mock_tool("bailian_web_search"),
            _make_mock_tool("query-weather"),
            _make_mock_tool("get-tickets"),
            _make_mock_tool("search-image"),
            _make_mock_tool("map_data"),
        ]
        result = split_tools(tools)

        assert len(result["research"]) == 2
        assert len(result["transport"]) == 1
        assert len(result["image"]) == 1
        assert len(result["map"]) == 1

    def test_empty_tools(self):
        """空列表应返回 4 个空列表"""
        result = split_tools([])
        for group_name in TOOL_GROUPS:
            assert result[group_name] == []

    def test_all_tools_split(self):
        """提供全量工具名，所有工具都被分配"""
        all_names = set()
        for names in TOOL_GROUPS.values():
            all_names |= names
        tools = [_make_mock_tool(n) for n in all_names]

        result = split_tools(tools)

        total = sum(len(v) for v in result.values())
        assert total == len(all_names)

    def test_unassigned_tool_warning(self, capsys):
        """未分配的工具应打印警告"""
        tools = [
            _make_mock_tool("bailian_web_search"),
            _make_mock_tool("unknown_mystery_tool"),
        ]
        split_tools(tools)
        captured = capsys.readouterr()
        assert "未分配的工具" in captured.out
        assert "unknown_mystery_tool" in captured.out

    def test_no_warning_when_all_assigned(self, capsys):
        """所有工具都已分配时不应有警告"""
        tools = [_make_mock_tool("bailian_web_search")]
        split_tools(tools)
        captured = capsys.readouterr()
        assert "未分配的工具" not in captured.out

    def test_result_keys_match_groups(self):
        """返回的 dict keys 与 TOOL_GROUPS keys 一致"""
        result = split_tools([])
        assert set(result.keys()) == set(TOOL_GROUPS.keys())
