from typing import Any, cast
from tool import client  # type: ignore
from langchain_community.chat_models.tongyi import ChatTongyi

# from langchain_community.chat_models.zhipuai import ChatZhipuAI

# uv add langchain-openai
from langchain_openai.chat_models import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY: Any = os.getenv("API_KEY")
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
QQ_MAP_KEY = os.getenv("QQ_MAP_KEY")
DEEP_SEEK_API_KEY: Any = os.getenv("DEEP_SEEK_API_KEY")

# 模型参数传递qwen2.5-14b-instruct-1m
# ChatTongyi使用这个方式不可以调用通义千问3
# tontyi = ChatTongyi(model="qwen3-max", api_key=API_KEY, streaming=True)  # type: ignore
# tontyi = ChatZhipuAI(model="glm-4.6", api_key=ZHIPU_API_KEY, streaming=True)
# 工具调用上通义千问3模型能力要比其他模型强大
tontyi = ChatOpenAI(
    model="qwen3-max",
    api_key=API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)
# 获取经纬度接口专用
tongyi_max = ChatTongyi(model="qwen-max", api_key=API_KEY)  # type: ignore

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict, Annotated
from langgraph.graph import add_messages, StateGraph, START, END  # type: ignore
from langchain_core.tools import BaseTool
from langchain_core.runnables import Runnable
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
import asyncio
from fastapi import WebSocket, Request
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from functools import partial
from langchain.tools import tool
import requests
import json


# 定义地图返回数据
@tool
def map_data(
    from_location: str,
    to_location: str,
    day: str,
    markers: list[Any],
    waypoints: str | None = None,
) -> Any:
    """
    根据旅游攻略内容调用腾讯地图获取景点经纬度位置；
    例如旅游攻略内容如下：第一天：上午大理古城(表示起点)，下午洱海(表示途经点).....，晚上双廊古城(表示终点)；
    参数：
        from_location: 起点经纬度，例如 "25.812655,100.230119"
        to_location:   终点经纬度，例如 "25.700801,100.170478"
        day:第几天，例如"第一天"
        waypoints: 可选，途经点经纬度，多个用分号拼接："25.911703,100.203224;25.901234,100.203999"
        markers: 景点标记点；生成的marker字段列表结构如下：
        [{
          id:12,
          latitude:25.812655,
          longitude:100.203224,
          content:'大理古城'
        },{
          id:13,
          latitude:25.700801,
          longitude:100.170478,
          content:'洱海'
        },//]
          id表示对应每个景点的id，随机数生成不重复，可使用时间戳，数字类型，
          latitude和longitude表示对应每个景点的经纬度，数字类型
          content表示对应每个景点名称,字符串类型

    注意：
        起点，终点，途经点经纬度必须先调用 bailian_web_search 工具获取得到，
        此工具只负责请求腾讯地图接口。
        该工具接受某一天的路线经纬度，并返回路线规划。
        如果需要多天规划，请模型多次调用本工具，并在最后整合全部结果输出。
    """
    url = "https://apis.map.qq.com/ws/direction/v1/driving/"
    params = {
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
    # 取routes[0].polyline
    polyline = routes[0].get("polyline", [])
    if not polyline:
        return json.dumps(
            {"points": [], "type": "route_polyline", "day": day, "marker": []}
        )
    kr = 1000000.0
    # 差分解压
    for item in range(2, len(polyline)):
        polyline[item] = polyline[item - 2] + polyline[item] / kr
    points = []
    for item in range(0, len(polyline), 2):
        points.append({"latitude": polyline[item], "longitude": polyline[item + 1]})
    return json.dumps(
        {"points": points, "type": "route_polyline", "day": day, "marker": markers}
    )


# 工具类型
class ToolInfo(TypedDict):
    tools_by_name: dict[str, BaseTool]
    llm_with_tools: Runnable[LanguageModelInput, BaseMessage]
    all_tools: list[BaseTool]


# 获取全局缓存的工具数据:websocket专用
def get_tool_list_ws(websocket: WebSocket) -> ToolInfo:
    tool_info: ToolInfo | None = getattr(websocket.app.state, "tool_cache", None)
    if tool_info is None:
        raise RuntimeError("工具数据未找到")
    return tool_info


# 获取全局缓存的工具数据:http接口专用
def get_tool_list(request: Request) -> ToolInfo:
    tool_info: ToolInfo | None = getattr(request.app.state, "tool_cache", None)
    if tool_info is None:
        raise RuntimeError("工具数据未找到")
    return tool_info


# 定义状态
class AgentState(TypedDict):
    # 对话的数据类型：用户消息+模型回复+工具+提示次
    messages: Annotated[list[BaseMessage], add_messages]


# 定义模型节点
async def call_llm(state: AgentState, prompt: str, tool_info: ToolInfo):
    # 让模型决定是否需要调用工具，并且将结果更新到状态里
    llm_with_tools = tool_info["llm_with_tools"]
    messages = [SystemMessage(content=prompt)] + state["messages"]
    # print("模型决定是否需要调用工具==messages", messages)
    response = await llm_with_tools.ainvoke(messages)
    # print("模型决定是否需要调用工具==response", response)
    return {"messages": [response]}


# 定义工具节点
semaphore = asyncio.Semaphore(1)  # 每次只发 1 个请求


async def safe_ainvoke(tool: Any, args: Any):
    async with semaphore:
        return await tool.ainvoke(args)


async def call_tool(state: AgentState, tool_info: ToolInfo) -> Any:
    """
    # 执行工具调用，然后将结果更新到状态里
    tools_by_name = tool_info["tools_by_name"]
    # # 取对话里的最后一条
    last_message = cast(AIMessage, state["messages"][-1])
    # print("执行工具调用=============last_message", last_message)
    tasks = [
        tools_by_name[tool_call["name"]].ainvoke(tool_call["args"])
        for tool_call in last_message.tool_calls
    ]
    # print("执行工具调用=============tasks", tasks)
    # 并发执行所有工具，业就是让模型一次性执行多个工具，
    results = await asyncio.gather(*tasks)
    # print("执行工具调用=============results", results)
    tool_messages = [
        ToolMessage(content=str(result), tool_call_id=tool_call["id"])
        for result, tool_call in zip(results, last_message.tool_calls)
    ]
    return {"messages": tool_messages}
    """
    tools_by_name = tool_info["tools_by_name"]
    last_message = cast(AIMessage, state["messages"][-1])

    tasks = [
        safe_ainvoke(tools_by_name[tool_call["name"]], tool_call["args"])
        for tool_call in last_message.tool_calls
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    tool_messages = []
    for tool_call, result in zip(last_message.tool_calls, results):
        content = (
            f"工具执行失败: {repr(result)}"
            if isinstance(result, Exception)
            else str(result)
        )
        tool_messages.append(ToolMessage(content=content, tool_call_id=tool_call["id"]))
    return {"messages": tool_messages}


# 定义结束逻辑
def route_logic(state: AgentState):
    # 根据大模型的回复决定是否需要调用工具
    last_message = cast(AIMessage, state["messages"][-1])
    if last_message.tool_calls:
        return "call_tool"
    else:
        return "end"


# 构建并编译代理程序,构建执行顺序
def state_graph(
    checkpointer: AsyncPostgresSaver,
    store: AsyncPostgresStore,
    prompt: str,
    tool_info: ToolInfo,
):
    # 初始化构建器
    builder = StateGraph(AgentState)
    # 定义节点
    builder.add_node("call_llm", partial(call_llm, prompt=prompt, tool_info=tool_info))  # type: ignore
    builder.add_node("call_tool", partial(call_tool, tool_info=tool_info))  # type: ignore
    # 定义边，其实叫做连接节点
    builder.add_edge(START, "call_llm")
    # 循环边，如果有工具，需要再次交给大模型去处理再返回
    builder.add_edge("call_tool", "call_llm")
    # 定义条件分支，就是类似if，else
    builder.add_conditional_edges(
        "call_llm", route_logic, {"call_tool": "call_tool", "end": END}
    )
    agent_graph = builder.compile(
        checkpointer=checkpointer,
        store=store,
    )
    return agent_graph
