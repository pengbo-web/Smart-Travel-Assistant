"""
MapRouteAgent — 路线规划 Agent

职责: 从攻略中提取景点经纬度，按天调用腾讯地图生成驾车路线
模型: qwen3-max
工具: map_data ★（唯一持有此工具的 Agent）
内部循环: map_route_llm → map_tool_node → map_route_llm（每天一次）→ END
"""

import asyncio
import json
import os
from typing import Any, cast

import requests
from langchain.tools import tool
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from graph.state import MultiAgentState

# ────────────────────────────────────────────────────────
# map_data 本地工具（从 state_graph.py 迁移，完全保持原逻辑）
# ────────────────────────────────────────────────────────

QQ_MAP_KEY = os.getenv("QQ_MAP_KEY", "")


@tool
def map_data(
    from_location: str,
    to_location: str,
    day: str,
    markers: list[Any],
    waypoints: str | None = None,
) -> Any:
    """
    根据旅游攻略内容调用腾讯地图获取景点驾车路线；
    例如旅游攻略内容如下：第一天：上午大理古城(表示起点)，下午洱海(表示途经点)，晚上双廊古城(表示终点)；
    参数：
        from_location: 起点经纬度（对应 order=1 的景点），例如 "25.812655,100.230119"
        to_location:   终点经纬度（对应 order 最大的景点），例如 "25.700801,100.170478"
        day: 第几天，例如"第一天"
        waypoints: 可选，途经点经纬度，按 order 顺序用分号拼接："25.911703,100.203224;25.901234,100.203999"
        markers: 景点标记点列表，必须按 order 升序排列，结构如下：
        [{
          id: 1001,
          order: 1,
          latitude: 25.812655,
          longitude: 100.203224,
          content: '大理古城'
        }, {
          id: 1002,
          order: 2,
          latitude: 25.700801,
          longitude: 100.170478,
          content: '洱海'
        }]
          id: 每个景点的唯一标识，随机数生成不重复，数字类型
          order: ★ 推荐游览顺序编号，从 1 开始递增，前端将据此显示编号圆圈
          latitude/longitude: 景点经纬度，数字类型
          content: 景点名称，字符串类型

    注意：
        起点，终点，途经点经纬度必须先调用 bailian_web_search 工具获取得到，
        此工具只负责请求腾讯地图接口。
        该工具接受某一天的路线经纬度，并返回路线规划。
        如果需要多天规划，请模型多次调用本工具，并在最后整合全部结果输出。
    """
    url = "https://apis.map.qq.com/ws/direction/v1/driving/"
    params: dict[str, str] = {
        "from": from_location,
        "to": to_location,
        "key": QQ_MAP_KEY,
    }
    if waypoints:
        params["waypoints"] = waypoints

    res = requests.get(url, params=params)
    data = res.json()
    routes = data.get("result", {}).get("routes", [])
    if not routes:
        return json.dumps(
            {"points": [], "type": "route_polyline", "day": day, "marker": []}
        )

    polyline = routes[0].get("polyline", [])
    if not polyline:
        return json.dumps(
            {"points": [], "type": "route_polyline", "day": day, "marker": []}
        )

    # 差分解压
    kr = 1000000.0
    for item in range(2, len(polyline)):
        polyline[item] = polyline[item - 2] + polyline[item] / kr

    points = []
    for item in range(0, len(polyline), 2):
        points.append({"latitude": polyline[item], "longitude": polyline[item + 1]})

    return json.dumps(
        {"points": points, "type": "route_polyline", "day": day, "marker": markers}
    )


# ────────────────────────────────────────────────────────
# Agent 节点函数
# ────────────────────────────────────────────────────────


def _load_prompt(path: str) -> str:
    """读取 Prompt 模板文件"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _create_map_route_llm() -> ChatOpenAI:
    """创建 MapRouteAgent 专用的 LLM（绑定 map_data 工具）"""
    llm = ChatOpenAI(
        model="qwen3-max",
        api_key=os.getenv("API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    return llm.bind_tools([map_data])


async def map_route_llm_node(state: MultiAgentState) -> dict:
    """
    MapRouteAgent 的 LLM 推理节点。

    将 plan_content（攻略全文）注入 Prompt，
    让 LLM 逐天提取景点并调用 map_data。
    """
    prompt_text = _load_prompt("prompts/map_route.txt").format(
        plan_content=state.get("plan_content", "（暂无攻略内容）"),
    )

    llm_with_tools = _create_map_route_llm()

    messages = [SystemMessage(content=prompt_text)] + state["messages"][-1:]
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


async def map_tool_node(state: MultiAgentState) -> dict:
    """
    MapRouteAgent 的工具执行节点。

    仅处理 map_data 工具调用。每天一次调用，
    返回包含 polyline 和 markers 的路线 JSON。
    """
    last_message = cast(AIMessage, state["messages"][-1])

    tasks = []
    for tc in last_message.tool_calls:
        if tc["name"] == "map_data":
            tasks.append(map_data.ainvoke(tc["args"]))
        else:
            async def _err(name=tc["name"]):
                return f"工具 {name} 不在 map 工具组中"
            tasks.append(_err())

    results = await asyncio.gather(*tasks, return_exceptions=True)

    tool_messages = []
    for tc, result in zip(last_message.tool_calls, results):
        if isinstance(result, Exception):
            content = f"地图路线请求失败: {repr(result)}"
        else:
            content = str(result)
        tool_messages.append(
            ToolMessage(content=content, tool_call_id=tc["id"])
        )
    return {"messages": tool_messages}


def map_route_route(state: MultiAgentState) -> str:
    """
    MapRoute 内部路由函数。

    检查最后一条 AI 消息是否包含工具调用：
    - 有工具调用 → 'call_tool'（继续下一天路线）
    - 无工具调用 → 'done'（所有天的路线已完成）
    """
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "call_tool"
    return "done"
