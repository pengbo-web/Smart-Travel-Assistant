"""
工具分组隔离

将 MCP 全量工具列表按职责分组，每个 Agent 只拿到对应的工具子集。
架构级约束：Agent 物理上无法调用不属于自己的工具。
"""

from langchain_core.tools import BaseTool


# 工具分组定义（名称必须与 MCP 返回的 tool.name 完全一致）
TOOL_GROUPS: dict[str, set[str]] = {
    # ResearchAgent 专用：天气 + 景点搜索
    "research": {
        "bailian_web_search",   # 联网搜索景点/美食/攻略
        "query-weather",        # 天气查询（zuimei-getweather MCP）
        "maps_weather",         # 高德天气（备用）
        "maps_text_search",     # 关键词搜索 POI
    },
    # TransportAgent 专用：火车票查询
    "transport": {
        "get-tickets",                  # 查询高铁/火车余票
        "get-stations-code-in-city",    # 查询城市火车站代码
        "get-station-code-of-citys",    # 查询城市 station_code
        "get-station-code-by-names",    # 根据站名查 code
        "get-interline-tickets",        # 中转票查询
        "get-train-route-stations",     # 列车途经站查询
        "get-current-date",             # 获取当前日期
        "relative-date",                # 日期计算
    },
    # PlanWriterAgent 专用：图片搜索
    "image": {
        "search-image",         # geng-search-image MCP 搜索景点图片
    },
    # MapRouteAgent 专用：地图路线规划
    "map": {
        "map_data",             # ★ 本地工具：腾讯地图驾车路线规划
    },
}


def split_tools(all_tools: list[BaseTool]) -> dict[str, list[BaseTool]]:
    """
    将全量工具列表按分组拆分，每个 Agent 只拿到对应的工具子集。

    Args:
        all_tools: MCP 工具 + 本地工具的完整列表

    Returns:
        按分组名分类的工具字典，如:
        {
            "research":  [BaseTool, ...],
            "transport": [BaseTool, ...],
            "image":     [BaseTool, ...],
            "map":       [BaseTool, ...],
        }
    """
    by_name: dict[str, BaseTool] = {tool.name: tool for tool in all_tools}
    result: dict[str, list[BaseTool]] = {}

    for group_name, tool_names in TOOL_GROUPS.items():
        result[group_name] = [
            by_name[name] for name in tool_names if name in by_name
        ]

    # 打印未分配的工具（调试用，帮助发现新增的 MCP 工具）
    assigned = set().union(*TOOL_GROUPS.values())
    unassigned = set(by_name.keys()) - assigned
    if unassigned:
        print(f"[tool_groups] ⚠️ 未分配的工具: {unassigned}")

    return result
