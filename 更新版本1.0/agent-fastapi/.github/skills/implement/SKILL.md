---
name: implement
description: 从架构文档中读取设计规范，按任务实现代码。首先读取架构文档相关章节，提取接口定义和代码模板，然后编写生产就绪代码。当用户要求实现功能、写代码时使用。dev-workflow 流水线的阶段 3。
metadata:
  category: implementation
  triggers: "implement, write code, 实现, 写代码, 开始编码"
allowed-tools: Read Write Bash(python:*) Bash(pytest:*)
---

# Implement from Spec（从架构文档实现）

你是智能旅游助手的**首席开发工程师**。当收到任务后，你必须遵循此工作流程实现代码。

> **前置条件**: 此技能依赖 `spec-reader` 读取架构文档。
> 架构文档位于: `docs/MULTI_AGENT_ARCHITECTURE.md`

---

## 步骤 1: 架构文档检索

### 1.1 定位目标章节

根据任务 ID，使用 spec-reader 的章节索引定位需要阅读的章节：

| 任务类型 | 需要阅读 |
|---------|---------|
| 状态/工具相关 (P1-01, P1-02) | §3 共享状态 + §4 工具分组 |
| Agent 实现 (P1-03~05, P2-01~03, P3-01) | §5 对应的 Agent 小节 |
| 图结构 (P1-06, P2-04, P3-02) | §6 图结构组装 |
| 服务层/入口 (P1-07, P1-08, P2-05) | §7 WebSocket + §9 迁移指南 |
| 前端 (P2-07, P2-08) | §8 前端适配 |

### 1.2 提取设计要素

从**架构文档对应章节**提取：
- **代码模板**: 文档中的 Python/TypeScript 代码块
- **接口定义**: 函数签名、TypedDict 定义、Pydantic Model
- **工具绑定**: 该 Agent 持有哪些工具（§4 隔离表）
- **路由逻辑**: 条件边的判断函数
- **Prompt 内容**: 完整的 Prompt 文本（需要创建为独立文件）

### 1.3 提取设计原则

本项目的核心设计原则（从 §1.2 提取）：

| 原则 | 含义 | 检查点 |
|------|------|-------|
| 工具隔离 | Agent 只持有职责相关工具 | `split_tools()` 分组正确 |
| 结构化路由 | Pydantic 输出分类意图 | `SupervisorOutput` 无歧义 |
| 真正并发 | `asyncio.gather` 替代 Semaphore | 无 `Semaphore(1)` |
| Human-in-the-Loop | `interrupt_after` 实现偏好收集 | 图中断/恢复正常 |
| 优雅降级 | 天气策略三级降级 | `weather_strategy_node` 逻辑完整 |
| 连接池复用 | lifespan 初始化全局连接 | 不在请求中创建连接 |

---

## 步骤 2: 技术规划

**在写任何代码之前**，确认以下事项：

### 2.1 文件策略

列出需要创建或修改的文件（与任务 §10 进度表的"修改的文件"列交叉检查）。

### 2.2 依赖检查

检查现有 `pyproject.toml` 中是否包含所需依赖：
```bash
cd D:\mcpdemo\智能旅游助手\更新版本1.0\agent-fastapi
cat pyproject.toml
```

常用依赖：
- `langgraph` >= 0.2 （StateGraph, add_messages）
- `langchain-openai` （ChatOpenAI）
- `langchain-community` （ChatTongyi）
- `pydantic` （结构化输出）
- `psycopg[binary,pool]` （PostgreSQL 连接池）

### 2.3 复用现有代码

在写新代码前，先读取现有代码以识别可复用的部分：

| 现有文件 | 可复用内容 | 目标文件 |
|---------|-----------|---------|
| `state_graph.py` | `map_data` 工具函数 | `agents/map_route_agent.py` |
| `state_graph.py` | ReAct 循环模式（call_llm → call_tool） | 各 Agent 的 llm_node/tool_node |
| `model_prompt.py` | 部分 Prompt 文本 | `prompts/*.txt` |
| `services/chat.py` | 流式输出处理逻辑 | `services/chat.py`（改造） |
| `main.py` | MCP 工具加载逻辑 | `main.py`（改造） |

---

## 步骤 3: 实现

### 3.1 编码标准

1. **类型提示**: 所有函数签名必须有类型提示
2. **Docstring**: Google 风格，中文注释
3. **不硬编码**: API Key 从环境变量读取，配置使用常量
4. **单一职责**: 每个函数/节点做一件事
5. **有意义的名称**: `supervisor_node` 而非 `node1`
6. **错误处理**: LLM 调用和工具执行必须 try/except

### 3.2 Agent 节点实现模式

所有 Agent 遵循统一的 ReAct 模式（参考架构文档 §5）：

```python
# 标准 Agent 三件套模式
async def xxx_llm_node(state: MultiAgentState, tools: list) -> dict:
    """LLM 推理节点 —— 决定是否调用工具"""
    ...

async def xxx_tool_node(state: MultiAgentState, tools: list) -> dict:
    """工具执行节点 —— 并发执行 tool_calls"""
    ...

def xxx_route(state: MultiAgentState) -> str:
    """内部路由 —— 有工具调用走 call_tool，否则走 done"""
    ...
```

### 3.3 Prompt 文件创建

Prompt 独立存储在 `prompts/` 目录，使用 `.txt` 格式：
- 从架构文档 §5 中提取对应的 Prompt 文本
- 使用 `{variable}` 占位符做模板化
- 文件编码 UTF-8

### 3.4 工具注入

使用 `functools.partial` 将工具列表注入节点函数：
```python
from functools import partial
builder.add_node("research_llm", partial(research_llm_node, tools=tool_groups["research"]))
```

---

## 步骤 4: 自我验证

### 4.1 静态检查清单

- [ ] 文件路径与架构文档 §2 目录结构一致？
- [ ] `__init__.py` 文件已创建？
- [ ] 类型提示完整？
- [ ] 工具隔离正确（Agent 只绑定了该组工具）？
- [ ] Prompt 使用占位符而非硬编码？
- [ ] 没有遗留的 `asyncio.Semaphore`？
- [ ] 环境变量通过 `os.getenv()` 读取？

### 4.2 导入验证

对每个新创建的文件，执行导入测试：
```bash
cd D:\mcpdemo\智能旅游助手\更新版本1.0\agent-fastapi
python -c "from <module> import <symbol>"
```

### 4.3 设计原则合规检查

```
────────────────────────────────
已应用的设计原则
────────────────────────────────
[x] 工具隔离: Agent 只持有 xxx 组工具
[x] 结构化路由: 使用 Pydantic SupervisorOutput
[x] 连接池: 无 per-request 连接创建
[x] 错误处理: LLM/工具调用有 try/except
────────────────────────────────
```

---

## 实现参考：各任务速查

### P1-01: 共享状态定义
- 读取 §3，创建 `graph/__init__.py` + `graph/state.py`
- 实现 `Preferences`, `SupervisorResult`, `MultiAgentState`

### P1-02: 工具分组隔离
- 读取 §4，创建 `graph/tool_groups.py`
- 实现 `TOOL_GROUPS` 字典和 `split_tools()` 函数

### P1-03: ResearchAgent
- 读取 §5.4，创建 `agents/__init__.py` + `agents/research_agent.py` + `prompts/research.txt`
- 实现 `research_llm_node`, `research_tool_node`, `research_route`, `research_done_node`
- 关键：工具并发执行用 `asyncio.gather`

### P1-04: PlanWriterAgent
- 读取 §5.7，创建 `agents/plan_writer_agent.py` + `prompts/plan_writer.txt`
- 实现 `plan_writer_llm_node`, `image_tool_node`, `plan_writer_route`, `plan_writer_done_node`

### P1-05: MapRouteAgent
- 读取 §5.8，创建 `agents/map_route_agent.py` + `prompts/map_route.txt`
- **关键**: 从 `state_graph.py` 迁移 `map_data` 工具函数

### P1-06: 图结构组装
- 读取 §6，创建 `graph/builder.py`
- **Phase 1 简化版**: 只串联 Research → PlanWriter → MapRoute，不含 Supervisor/Preference

### P1-07: 服务层适配
- 读取 §7 + §9.3，修改 `services/chat.py`
- 替换 `state_graph()` 为 `build_multi_agent_graph()`

### P1-08: 应用入口改造
- 读取 §9.2，修改 `main.py`
- 全局连接池 + 工具分组存入 `app.state`

### P2-01: SupervisorAgent
- 读取 §5.1，创建 `agents/supervisor.py` + `prompts/supervisor.txt`
- 结构化输出: `SupervisorOutput` Pydantic Model

### P2-02: PreferenceNode + WeatherStrategy
- 读取 §5.2 + §5.3，创建 `agents/preference.py`
- 偏好卡片 JSON + 天气策略计算

### P3-01: TransportAgent
- 读取 §5.5，创建 `agents/transport_agent.py` + `prompts/transport.txt`
- 包含 `transport_check_node` 跳过逻辑

---

## 重要规则

1. **架构文档为准**: 代码必须符合文档中的接口定义和设计
2. **增量实现**: 每次只完成一个任务，不跳跃
3. **保持现有功能**: 修改文件时不破坏现有 API
4. **中文注释**: 代码注释使用中文
5. **不要占位符**: 不使用 `pass` 或 `TODO`，每个函数都有完整实现

---
