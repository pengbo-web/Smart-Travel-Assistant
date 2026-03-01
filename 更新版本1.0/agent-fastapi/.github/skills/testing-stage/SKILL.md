---
name: testing-stage
description: 在 implement 阶段完成后验证实现。根据任务性质确定测试类型，运行验证命令并报告结果。dev-workflow 流水线的阶段 4。当用户说"运行测试"、"test"、"验证"时使用。
metadata:
  category: testing
  triggers: "run tests, test, validate, 运行测试, 验证"
allowed-tools: Read Bash(python:*) Bash(pytest:*)
---

# Testing Stage（测试阶段）

你是智能旅游助手的**质量保证工程师**。在实现完成后，通过系统测试验证代码。

> **前置条件**: 此技能在 `implement` 完成后运行。

---

## 测试策略矩阵

| 任务特征 | 测试类型 | 方法 |
|---------|---------|------|
| 纯数据定义 (P1-01) | 导入测试 | `python -c "from graph.state import ..."` |
| 纯函数/工具 (P1-02) | 单元测试 | `pytest tests/unit/test_*.py` |
| Agent 节点 (P1-03~05, P2-01~03, P3-01) | 导入测试 + Mock 单测 | 导入验证 + pytest |
| 图结构组装 (P1-06, P2-04, P3-02) | 集成测试 | 构建图对象验证 |
| 服务/入口 (P1-07, P1-08) | 启动测试 | `uvicorn main:app` 无报错 |
| 端到端 (P1-09, P3-04~05) | 手动 WebSocket 测试 | 发送消息验证完整流程 |
| 前端 (P2-07, P2-08) | 编译测试 | `npm run build` 无报错 |

---

## 步骤 1: 识别测试范围

### 1.1 从任务获取测试方法

读取 `docs/MULTI_AGENT_ARCHITECTURE.md` §10 进度表中该任务的"测试方法"列。

### 1.2 映射测试文件

| 源文件 | 测试文件 |
|-------|---------|
| `graph/state.py` | `tests/unit/test_state.py` |
| `graph/tool_groups.py` | `tests/unit/test_tool_groups.py` |
| `agents/research_agent.py` | `tests/unit/test_research_agent.py` |
| `agents/supervisor.py` | `tests/unit/test_supervisor.py` |
| `agents/preference.py` | `tests/unit/test_preference.py` |
| `graph/builder.py` | `tests/integration/test_graph_builder.py` |

---

## 步骤 2: 执行测试

### 2.1 导入验证（所有任务必做）

```bash
cd D:\mcpdemo\智能旅游助手\更新版本1.0\agent-fastapi
python -c "from <module> import <symbol>; print('✅ 导入成功')"
```

### 2.2 单元测试（如存在）

```bash
pytest tests/unit/test_<module>.py -v
```

### 2.3 启动测试（P1-08, P1-09）

```bash
# 验证应用可以启动（不需要实际连接数据库）
python -c "from main import app; print('✅ app 对象创建成功')"
```

### 2.4 如果测试不存在

对于 Phase 1-3 的 Agent 节点任务，如果测试文件不存在：
1. **创建基础导入测试**（最低要求）
2. 对于 Phase 4（P4-02~04），则创建完整测试

**基础导入测试模板**:
```python
"""
{module_name} 导入与基础验证测试
"""


def test_import():
    """验证模块可以正常导入"""
    from {module_path} import {symbol}
    assert {symbol} is not None


def test_function_signature():
    """验证函数签名正确"""
    import inspect
    from {module_path} import {symbol}
    sig = inspect.signature({symbol})
    assert "state" in sig.parameters
```

---

## 步骤 3: 分析结果

### 3.1 测试通过

```
────────────────────────────────
✅ 测试通过
────────────────────────────────
任务: [P1-03] ResearchAgent 实现
导入验证: ✅ 通过
单元测试: 3/3 通过

准备进入 checkpoint 阶段。
────────────────────────────────
```

### 3.2 测试失败

```
────────────────────────────────
❌ 测试失败
────────────────────────────────
任务: [P1-03] ResearchAgent 实现
失败项:
  1. ImportError: cannot import name 'research_llm_node'
     原因: 函数名拼写错误
     建议: 检查 agents/research_agent.py 中的函数名

返回 implement 阶段修复。
────────────────────────────────
```

---

## 步骤 4: 反馈循环

如果测试失败：
1. 生成修复报告（失败原因 + 建议修复）
2. 返回 implement 阶段修正
3. 修正后重新测试
4. **最多 3 次迭代**，超过则上报用户

---

## 重要规则

1. **导入测试是最低门槛**: 每个新文件至少通过导入测试
2. **不跳过测试**: 即使是"简单"的任务也要验证
3. **测试在项目根目录执行**: `cd D:\mcpdemo\智能旅游助手\更新版本1.0\agent-fastapi`
4. **失败时提供可操作建议**: 不只是报告错误，还要分析原因
5. **Phase 1-3 侧重导入测试**: 完整单测留到 Phase 4

---
