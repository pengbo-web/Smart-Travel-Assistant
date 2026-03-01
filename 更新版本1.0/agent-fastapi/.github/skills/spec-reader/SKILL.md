---
name: spec-reader
description: 读取 Multi-Agent 架构文档并导航到指定章节。所有基于架构文档的操作的基础。当用户说"读取规范"、"查看架构"、"read spec"或在任何依赖架构文档的任务之前使用。
metadata:
  category: documentation
  triggers: "read spec, 读取规范, 查看架构, read architecture"
allowed-tools: Read
---

# Spec Reader（架构文档读取器）

此技能读取主架构文档 `docs/MULTI_AGENT_ARCHITECTURE.md`，并根据当前任务定位到相关章节。

> **这是所有基于架构的操作的前提条件。** 其他技能依赖此技能来获取架构设计详情。

---

## 架构文档位置

```
docs/MULTI_AGENT_ARCHITECTURE.md   ← 唯一架构文档（约 1700+ 行）
```

---

## 章节索引

| 章节 | 行号范围（约） | 内容 | 适用场景 |
|------|---------------|------|---------|
| §1 架构总览 | 1-300 | 现有问题、新架构原则、执行流程、架构图 | 理解全局设计 |
| §2 目录结构 | 300-370 | 目标文件/目录布局 | 创建文件前确认路径 |
| §3 共享状态定义 | 370-470 | `MultiAgentState` TypedDict + 字段流转矩阵 | 实现 `graph/state.py` |
| §4 工具分组隔离 | 470-560 | `TOOL_GROUPS` + `split_tools()` + 隔离效果表 | 实现 `graph/tool_groups.py` |
| §5 各 Agent 详细设计 | 560-1200 | 9 个节点的 Prompt/代码/路由逻辑 | 实现 `agents/*.py` |
| §6 图结构组装 | 1200-1390 | `build_multi_agent_graph()` 完整代码 | 实现 `graph/builder.py` |
| §7 WebSocket 协议 | 1390-1470 | 消息格式 + 流式处理适配 | 修改 `services/chat.py` |
| §8 前端适配 | 1470-1560 | TypeScript 类型 + Store + 组件 | 前端改动 |
| §9 迁移指南 | 1560-1600 | 需修改/删除的文件清单 + 改动要点 | 了解迁移范围 |
| §10 实施路线 | 1600-1680 | **进度跟踪表**（任务 ID + 状态标记） | progress-tracker 解析 |
| §11 场景示例 | 1680-1740 | 3 个典型场景的完整执行流程 | 理解运行时行为 |

---

## 使用方法

### 方法 1：按任务读取（推荐）

根据当前任务 ID 定位需要阅读的章节：

| 任务阶段 | 需要阅读的章节 |
|---------|---------------|
| P1-01 共享状态 | §3 共享状态定义 |
| P1-02 工具分组 | §4 工具分组隔离 |
| P1-03/04/05 Agent 实现 | §5 对应的 Agent 小节 |
| P1-06 图结构组装 | §6 图结构组装 |
| P1-07/08 服务/入口改造 | §7 WebSocket 协议 + §9 迁移指南 |
| P2-* Supervisor + 偏好 | §5.1 + §5.2 + §5.3 |
| P2-07/08 前端改动 | §8 前端适配 |
| P3-* 并发 + Transport | §5.5 + §5.6 + §6 图结构 |
| P4-* 清理 + 测试 | §9 迁移指南 |

### 方法 2：关键词搜索

直接在文档中搜索关键词：
- `SupervisorAgent` → 定位到 §5.1
- `PreferenceNode` → 定位到 §5.2
- `weather_strategy` → 定位到 §5.3
- `split_tools` → 定位到 §4
- `build_multi_agent_graph` → 定位到 §6

---

## 读取规则

1. **按需读取**: 不要一次读完整个文档，根据当前任务只读相关章节
2. **代码优先**: 文档中的代码片段是实现的参考，但不是直接复制粘贴——需要根据实际项目结构调整导入路径
3. **架构文档是唯一真实来源**: 进度跟踪、设计决策、接口定义都以此文档为准
4. **不要编辑架构文档的设计内容**: 只有 progress-tracker 和 checkpoint 技能可以更新 §10 进度表中的状态标记

---

## 现有项目代码参考

在阅读架构文档的同时，以下现有文件提供了重要的实现上下文：

| 现有文件 | 参考价值 |
|---------|---------|
| `state_graph.py` | 现有 Agent 循环逻辑、`map_data` 工具实现 |
| `model_prompt.py` | 现有 Prompt（需拆分到 `prompts/` 目录） |
| `tool.py` | MCP Client 连接配置 |
| `tool_list.py` | 工具名称→中文描述映射 |
| `services/chat.py` | 现有流式输出逻辑 |
| `main.py` | 现有 lifespan 和工具加载 |
| `controllers/chat.py` | 现有 WebSocket 处理 |

---
