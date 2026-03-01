# 智能旅游助手 Multi-Agent 重构 - Copilot 编程指南

## 项目概述

本项目将智能旅游助手从单 Agent 架构重构为 Multi-Agent 协作架构。
架构文档：`docs/MULTI_AGENT_ARCHITECTURE.md`

## 技术栈

- **后端**: FastAPI + LangGraph + Python 3.13+
- **LLM**: qwen3-max (DashScope OpenAI Compatible), qwen-max (ChatTongyi)
- **MCP**: MultiServerMCPClient (WebSearch, AmapMaps, ChinaRailway, Weather, Image)
- **数据库**: PostgreSQL (AsyncPostgresSaver + AsyncPostgresStore)
- **前端**: UniApp (Vue3 + TypeScript + Pinia)
- **通信**: WebSocket 流式传输

## 项目根目录

```
D:\mcpdemo\智能旅游助手\更新版本1.0\agent-fastapi
```

## 编码规范

1. 所有函数签名必须有**类型提示**
2. Docstring 使用 Google 风格，**中文注释**
3. API Key 从 `os.getenv("API_KEY")` 读取，不硬编码
4. Agent 节点遵循统一的 ReAct 三件套模式：`xxx_llm_node`, `xxx_tool_node`, `xxx_route`
5. 工具执行使用 `asyncio.gather` 实现真正并发
6. 错误处理：LLM 调用和工具执行必须 try/except

## 开发工作流

使用以下 Agent Skills 驱动开发。说"下一阶段"或"继续开发"触发完整流水线。

## Skills 注册

<skills>
<skill>
<name>dev-workflow</name>
<description>开发工作流程的主协调器。当用户说"下一阶段"、"继续开发"、"next task"或要求继续开发时使用。按顺序执行 spec-reader → progress-tracker → implement → testing-stage → checkpoint，每次完成一个子任务。</description>
<file>.github/skills/dev-workflow/SKILL.md</file>
</skill>
<skill>
<name>spec-reader</name>
<description>读取 Multi-Agent 架构文档并导航到指定章节。所有基于架构文档的操作的基础。当用户说"读取规范"、"查看架构"、"read spec"或在任何依赖架构文档的任务之前使用。</description>
<file>.github/skills/spec-reader/SKILL.md</file>
</skill>
<skill>
<name>progress-tracker</name>
<description>从架构文档的进度表中识别下一个开发任务，并验证声明的进度是否与实际代码库状态匹配。当用户说"检查进度"、"status"、"下一个任务"时使用。</description>
<file>.github/skills/progress-tracker/SKILL.md</file>
</skill>
<skill>
<name>implement</name>
<description>从架构文档中读取设计规范，按任务实现代码。当用户要求实现功能、写代码时使用。首先读取架构文档相关章节获取代码模板和接口定义，然后编写生产就绪代码。</description>
<file>.github/skills/implement/SKILL.md</file>
</skill>
<skill>
<name>testing-stage</name>
<description>在 implement 阶段完成后验证实现。根据任务性质确定测试类型（导入验证/单测/集成/手动），运行验证命令并报告结果。当用户说"运行测试"、"验证"时使用。</description>
<file>.github/skills/testing-stage/SKILL.md</file>
</skill>
<skill>
<name>checkpoint</name>
<description>总结已完成工作，更新架构文档中的进度跟踪，并为下一次迭代做准备。当用户说"checkpoint"、"保存进度"、"任务完成"时使用。</description>
<file>.github/skills/checkpoint/SKILL.md</file>
</skill>
</skills>
