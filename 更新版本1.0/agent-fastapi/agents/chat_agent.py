"""
ChatAgent — 闲聊处理

职责: 作为通用 LLM，流式回复非旅游类问题
模型: qwen3-max（通用能力，无 SystemPrompt）
工具: 无
"""

import os

from langchain_openai import ChatOpenAI

from graph.state import MultiAgentState


async def chat_agent_node(state: MultiAgentState) -> dict:
    """
    闲聊节点：直接调用通用 LLM，无工具绑定、无 SystemPrompt。
    就像直接和大模型对话一样。
    """
    llm = ChatOpenAI(
        model="qwen3-max",
        api_key=os.getenv("API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    response = await llm.ainvoke(state["messages"])
    return {"messages": [response]}
