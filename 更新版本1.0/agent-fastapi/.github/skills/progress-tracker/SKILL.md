---
name: progress-tracker
description: 从架构文档的进度表中识别下一个开发任务，并验证声明的进度是否与实际代码库状态匹配。dev-workflow 流水线的阶段 2。当用户说"检查进度"、"status"、"下一个任务"、"what's next"时使用。
metadata:
  category: progress-tracking
  triggers: "status, what's next, 检查进度, 下一个任务, 定位任务"
allowed-tools: Read Bash(python:*)
---

# Progress Tracker（进度跟踪器）

从 `docs/MULTI_AGENT_ARCHITECTURE.md` §10 进度表中识别**下一个开发任务**，并**验证**声明的进度与实际代码是否匹配。

> **单一职责**: 定位 → 验证 → 确认

---

## 工作流程

```
步骤 1: 读取进度表  →  步骤 2: 验证产物  →  步骤 3: 识别任务  →  步骤 4: 用户确认
                           │
                           ▼
                      不匹配? → 上报 → 修正
```

---

## 步骤 1: 读取进度表

### 1.1 解析进度表

读取 `docs/MULTI_AGENT_ARCHITECTURE.md` 中 §10 实施路线与分期章节。

**进度标记识别规则**:

| 标记 | 含义 | 状态 |
|------|------|------|
| `[ ]` | 未开始 | `NOT_STARTED` |
| `[~]` | 进行中 | `IN_PROGRESS` |
| `[x]` | 已完成 | `COMPLETED` |

### 1.2 构建任务列表

按 Phase 分组输出：
```
Phase 1: 最小可行版本
  [x] P1-01: 共享状态定义
  [x] P1-02: 工具分组隔离
  [~] P1-03: ResearchAgent 实现  ← CURRENT
  [ ] P1-04: PlanWriterAgent 实现
  ...

Phase 2: Supervisor + 偏好卡
  [ ] P2-01: SupervisorAgent 实现
  ...
```

---

## 步骤 2: 验证产物

对每个标记为 `COMPLETED` 的任务，检查预期文件是否存在且可导入：

### 验证产物映射

| 任务 ID | 预期产物 | 验证命令 |
|---------|---------|---------|
| P1-01 | `graph/state.py` | `python -c "from graph.state import MultiAgentState"` |
| P1-02 | `graph/tool_groups.py` | `python -c "from graph.tool_groups import split_tools"` |
| P1-03 | `agents/research_agent.py` | `python -c "from agents.research_agent import research_llm_node"` |
| P1-04 | `agents/plan_writer_agent.py` | `python -c "from agents.plan_writer_agent import plan_writer_llm_node"` |
| P1-05 | `agents/map_route_agent.py` | `python -c "from agents.map_route_agent import map_route_llm_node"` |
| P1-06 | `graph/builder.py` | `python -c "from graph.builder import build_multi_agent_graph"` |
| P1-07 | `services/chat.py` | 检查是否包含 `build_multi_agent_graph` 调用 |
| P1-08 | `main.py` | 检查是否包含 `split_tools` 和全局连接池 |
| P2-01 | `agents/supervisor.py` | `python -c "from agents.supervisor import supervisor_node"` |
| P2-02 | `agents/preference.py` | `python -c "from agents.preference import preference_node"` |
| P2-03 | `agents/chat_agent.py` | `python -c "from agents.chat_agent import chat_agent_node"` |
| P3-01 | `agents/transport_agent.py` | `python -c "from agents.transport_agent import transport_llm_node"` |

**验证命令执行**（在项目根目录下）:
```bash
cd D:\mcpdemo\智能旅游助手\更新版本1.0\agent-fastapi
python -c "<验证命令>"
```

### 不匹配处理

如果检测到不匹配（声明完成但文件不存在/导入失败），上报：

```
────────────────────────────────
⚠️ 检测到进度不一致
────────────────────────────────
任务 P1-03 标记为 [x] 已完成
实际状态: agents/research_agent.py 不存在

选项:
1. 修正进度标记 → 将 [x] 改回 [ ]
2. 确认完成 → 代码在其他位置
3. 从实际状态继续
────────────────────────────────
```

---

## 步骤 3: 识别下一个任务

**优先级逻辑**:
1. 如果任何任务是 `IN_PROGRESS` → 那是当前任务
2. 否则，按依赖顺序找第一个 `NOT_STARTED` → 那是下一个任务
3. 如果当前 Phase 全部完成 → 进入下一个 Phase 的第一个任务
4. 如果全部完成 → 报告 "所有任务完成"

**依赖检查**: 开始任务前，确认该任务的前置依赖（见架构文档 §10 依赖关系）已满足。

### 输出格式

```
────────────────────────────────
✅ 识别到当前任务
────────────────────────────────
Phase:    1 - 最小可行版本
Task ID:  P1-03
名称:     ResearchAgent 实现
状态:     NOT_STARTED

架构文档参考:
  进度表: §10 Phase 1
  详细设计: §5.4 ResearchAgent（docs/MULTI_AGENT_ARCHITECTURE.md）

需创建文件:
  - agents/research_agent.py
  - prompts/research.txt

依赖项:
  ✅ P1-01: 共享状态定义
  ✅ P1-02: 工具分组隔离

验证: 依赖已满足 ✓
────────────────────────────────
```

---

## 步骤 4: 用户确认

```
────────────────────────────────
确认任务
────────────────────────────────
准备处理: [P1-03] ResearchAgent 实现

选项:
  确认 - 继续此任务
  指定其他 - 选择不同任务
  取消 - 停止

你的选择:
────────────────────────────────
```

---

## 输出约定

返回给 dev-workflow 的数据：

| 字段 | 示例值 |
|------|-------|
| Task ID | `P1-03` |
| 任务名称 | `ResearchAgent 实现` |
| Phase | `1 - 最小可行版本` |
| 架构文档章节 | `§5.4 ResearchAgent` |
| 需创建的文件 | `agents/research_agent.py`, `prompts/research.txt` |
| 依赖已满足 | Yes / No |

---

## 重要规则

1. **始终验证**: 不假设进度表是准确的，检查实际文件
2. **需要用户确认**: 不自动进入实现
3. **单任务聚焦**: 一次识别一个任务
4. **依赖意识**: 前置任务未完成时发出警告
5. **非破坏性**: 此技能只读取和报告，不修改代码

---
