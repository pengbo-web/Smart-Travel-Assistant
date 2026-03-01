"""
场景测试脚本 — 用于调试 Multi-Agent 图的端到端行为

功能:
  1. 闲聊测试: 输入一句话，测试 Supervisor 路由到 chat_agent
  2. 旅行规划测试: 输入旅行需求，完整走通 Supervisor → Preference → Research → PlanWriter → MapRoute
  3. 单独 Supervisor 测试: 仅测试意图识别（不走完整图）

用法:
  uv run python debug_scenario.py                           # 交互模式
  uv run python debug_scenario.py --chat "你好，介绍一下自己"  # 快速闲聊测试
  uv run python debug_scenario.py --travel "杭州三日游攻略"    # 完整旅行规划
  uv run python debug_scenario.py --supervisor "成都五日游"    # 仅测试 Supervisor 意图识别
  uv run python debug_scenario.py --travel "杭州三日游" --light # 轻量模式 (MemorySaver, 无需 PostgreSQL)
"""

import asyncio
import json
import os
import platform
import selectors
import sys
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

# Windows 下 psycopg async 需要 SelectorEventLoop
if platform.system() == "Windows":
    _selector = selectors.SelectSelector()
    _loop_factory = lambda: asyncio.SelectorEventLoop(_selector)
else:
    _loop_factory = None  # 使用默认

from dotenv import load_dotenv

load_dotenv()


# ── 颜色工具 ──
class C:
    """终端颜色"""
    HEADER  = "\033[95m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RESET   = "\033[0m"


def log(tag: str, msg: str, color: str = C.RESET):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{C.DIM}{ts}{C.RESET} {color}{C.BOLD}[{tag}]{C.RESET} {msg}")


def separator(title: str = ""):
    print(f"\n{C.CYAN}{'═' * 60}")
    if title:
        print(f"  {title}")
        print(f"{'═' * 60}{C.RESET}\n")
    else:
        print(f"{C.RESET}")


# ────────────────────────────────────────────────────────
# MCP 工具加载（带重试）
# ────────────────────────────────────────────────────────

async def load_tools_with_retry(max_retries: int = 3, delay: float = 2.0):
    """加载 MCP 工具，自动重试以应对远程服务不稳定"""
    from tool import client
    from agents.map_route_agent import map_data

    for attempt in range(1, max_retries + 1):
        try:
            mcp_tools = await client.get_tools()
            all_tools = mcp_tools + [map_data]
            log("INIT", f"工具加载成功 ({len(all_tools)} 个)", C.GREEN)
            return all_tools
        except Exception as e:
            log("WARN", f"工具加载失败 (第 {attempt}/{max_retries} 次): {type(e).__name__}: {e}", C.RED)
            if attempt < max_retries:
                log("WARN", f"等待 {delay}s 后重试...", C.YELLOW)
                await asyncio.sleep(delay)
                delay *= 1.5  # 指数退避
            else:
                raise RuntimeError(
                    f"MCP 工具加载失败 ({max_retries} 次重试均失败)。\n"
                    "可能原因: 远程 MCP 服务不可用 (如 zuimei-getweather 404)。\n"
                    "建议: 1) 稍后重试  2) 使用 --supervisor 模式（不需要 MCP 工具）"
                ) from e


# ────────────────────────────────────────────────────────
# Checkpointer 上下文管理器（支持 PostgreSQL / MemorySaver）
# ────────────────────────────────────────────────────────

@asynccontextmanager
async def create_checkpointer(light_mode: bool = False):
    """
    创建 checkpointer + store。

    Args:
        light_mode: True → 使用内存 (MemorySaver)，无需 PostgreSQL
                    False → 使用 AsyncPostgresSaver (生产一致)
    """
    if light_mode:
        from langgraph.checkpoint.memory import MemorySaver
        from langgraph.store.memory import InMemoryStore

        log("INIT", "轻量模式: 使用 MemorySaver (内存)", C.YELLOW)
        yield MemorySaver(), InMemoryStore()
    else:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from langgraph.store.postgres.aio import AsyncPostgresStore

        DB_URI = str(os.getenv("DB_URI"))
        async with (
            AsyncPostgresStore.from_conn_string(DB_URI) as store,
            AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer,
        ):
            await store.setup()
            await checkpointer.setup()
            log("INIT", "PostgreSQL checkpointer/store 就绪", C.GREEN)
            yield checkpointer, store


# ────────────────────────────────────────────────────────
# 测试 1: 仅 Supervisor 意图识别
# ────────────────────────────────────────────────────────

async def test_supervisor_only(query: str):
    """仅测试 Supervisor 模型的意图识别能力，不启动完整图"""
    separator("Supervisor 意图识别测试")
    log("INPUT", f'"{query}"', C.BLUE)

    from langchain_openai import ChatOpenAI
    from agents.supervisor import SupervisorOutput, SUPERVISOR_PROMPT

    llm = ChatOpenAI(
        model="qwen3-max",
        api_key=os.getenv("API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    ).with_structured_output(SupervisorOutput)

    messages = [
        {"role": "system", "content": SUPERVISOR_PROMPT},
        {"role": "user", "content": query},
    ]

    t0 = time.time()
    try:
        result: SupervisorOutput = await llm.ainvoke(messages)
        elapsed = time.time() - t0
        log("RESULT", f"耗时 {elapsed:.2f}s", C.GREEN)
        log("INTENT", f"{result.intent}", C.GREEN)
        log("DEST", f"{result.destination}", C.GREEN)
        log("DAYS", f"{result.travel_days}", C.GREEN)
        return result
    except Exception:
        traceback.print_exc()
        log("ERROR", "Supervisor 调用失败", C.RED)
        return None


# ────────────────────────────────────────────────────────
# 流式事件打印器
# ────────────────────────────────────────────────────────

def create_stream_printer():
    """创建流式事件打印器，返回 (print_event, get_stats, get_text_buffer) 三元组"""
    from langchain_core.messages import AIMessageChunk, ToolMessage
    from tool_list import TOOL_LIST

    node_events = {}
    text_buffer = []

    def print_event(item, metadata, collect_text: bool = False):
        node = metadata.get("langgraph_node", "unknown")
        node_events[node] = node_events.get(node, 0) + 1

        if isinstance(item, AIMessageChunk):
            # 偏好卡片
            if item.additional_kwargs.get("type") == "preference_card":
                try:
                    card = json.loads(item.content)
                    fields = [f["key"] for f in card.get("fields", [])]
                except (json.JSONDecodeError, TypeError):
                    fields = "parse_error"
                log(node, f"📋 偏好卡片 fields={fields}", C.HEADER)

            # 工具调用
            elif item.tool_calls:
                for call in item.tool_calls:
                    desc = TOOL_LIST.get(call["name"], call["name"])
                    args_preview = str(call.get("args", {}))[:100]
                    log(node, f"🔧 调用工具: {call['name']} ({desc})", C.YELLOW)
                    log(node, f"   参数: {args_preview}", C.DIM)

            # 文本内容
            elif item.content:
                if collect_text and node in ("plan_writer_llm", "map_route_llm"):
                    text_buffer.append(item.content)
                    count = node_events[node]
                    if count <= 3:
                        log(node, f"💬 {item.content[:100]}", C.GREEN)
                    elif count % 50 == 0:
                        log(node, f"💬 ...({count} chunks)...", C.DIM)
                else:
                    text = item.content[:120] + ("..." if len(item.content) > 120 else "")
                    log(node, f"💬 {text}", C.GREEN)

        elif isinstance(item, ToolMessage):
            result_preview = str(item.content)[:150]
            log(node, f"📦 工具结果 [{item.name}]: {result_preview}", C.CYAN)

    return print_event, lambda: dict(node_events), lambda: text_buffer


# ────────────────────────────────────────────────────────
# 测试 2: 完整图流式执行
# ────────────────────────────────────────────────────────

async def test_full_graph(query: str, mode: str = "travel", light: bool = False):
    """
    完整运行 Multi-Agent 图，打印每一步的详细信息。

    Args:
        query: 用户输入
        mode: "chat" — 仅跑到聊天结束
              "travel" — 跑完旅行规划全流程（遇到偏好中断后自动填充偏好继续）
        light: True 使用 MemorySaver (无需 PostgreSQL)
    """
    separator(f"完整图测试 (mode={mode}, {'轻量' if light else 'PostgreSQL'})")
    log("INPUT", f'"{query}"', C.BLUE)

    from graph.tool_groups import split_tools
    from graph.builder import build_multi_agent_graph
    from agents.preference import handle_preference_submission

    # ── 加载工具（带重试）──
    log("INIT", "加载 MCP 工具...", C.YELLOW)
    all_tools = await load_tools_with_retry()
    tool_groups = split_tools(all_tools)
    log("INIT", f"工具分组: {list(tool_groups.keys())}", C.GREEN)

    thread_id = f"debug-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    async with create_checkpointer(light_mode=light) as (checkpointer, store):
        log("INIT", f"thread_id={thread_id}", C.GREEN)

        graph = build_multi_agent_graph(
            checkpointer=checkpointer,
            store=store,
            tool_groups=tool_groups,
        )

        # ══════ 第 1 轮: 用户输入 ══════
        separator("第 1 轮: 用户消息")
        input_data = {"messages": [{"role": "user", "content": query}]}
        t0 = time.time()
        print_event, get_stats, _ = create_stream_printer()

        try:
            async for item, metadata in graph.astream(
                input_data, stream_mode="messages", config=config
            ):
                print_event(item, metadata)
        except Exception:
            traceback.print_exc()
            log("ERROR", "图执行出错", C.RED)

        elapsed = time.time() - t0
        log("STATS", f"第 1 轮耗时 {elapsed:.1f}s | 节点事件: {get_stats()}", C.BLUE)

        # ── 检查是否在 preference_node 中断 ──
        state = await graph.aget_state(config)
        next_nodes = state.next if state else ()

        if "supervisor" in next_nodes and mode == "travel":
            # ══════ 第 2 轮: 自动提交偏好 ══════
            separator("第 2 轮: 自动提交偏好 (模拟用户选择)")

            mock_preferences = {
                "travelers": "情侣",
                "pace": "舒适游",
                "style": ["自然风光", "城市漫步"],
                "budget": "灵活",
                "departure": "上海",
                "travel_date": "",  # 留空 = 近期出发
            }
            log("PREF", f"模拟偏好: {json.dumps(mock_preferences, ensure_ascii=False)}", C.HEADER)

            state_update = await handle_preference_submission(mock_preferences)
            log("PREF", f"状态更新: {state_update}", C.HEADER)

            await graph.aupdate_state(config, state_update)
            log("PREF", "已 update_state，开始 resume...", C.YELLOW)

            t1 = time.time()
            print_event_r2, get_stats_r2, get_text_buffer = create_stream_printer()

            try:
                async for item, metadata in graph.astream(
                    None, stream_mode="messages", config=config
                ):
                    print_event_r2(item, metadata, collect_text=True)
            except Exception:
                traceback.print_exc()
                log("ERROR", "第 2 轮执行出错", C.RED)

            elapsed2 = time.time() - t1
            log("STATS", f"第 2 轮耗时 {elapsed2:.1f}s | 节点事件: {get_stats_r2()}", C.BLUE)

            # ── 打印最终攻略摘要 ──
            buf = get_text_buffer()
            if buf:
                full_text = "".join(buf)
                separator("攻略输出摘要")
                if len(full_text) > 800:
                    print(full_text[:500])
                    print(f"\n{C.DIM}... 省略中间 {len(full_text) - 700} 字 ...{C.RESET}\n")
                    print(full_text[-200:])
                else:
                    print(full_text)
                log("LENGTH", f"攻略总长度: {len(full_text)} 字", C.BLUE)

        elif next_nodes:
            log("STATE", f"图在 next={next_nodes} 处中断 (mode={mode}，不自动继续)", C.YELLOW)
        else:
            log("STATE", "图已执行完毕", C.GREEN)

        # ══════ 最终状态快照 ══════
        separator("最终状态快照")
        final_state = await graph.aget_state(config)
        if final_state and final_state.values:
            sv = final_state.values
            for k in ["supervisor_result", "preferences_done", "weather_strategy",
                       "research_done", "transport_done"]:
                if k in sv:
                    log("STATE", f"{k} = {sv[k]}", C.CYAN)

            msgs = sv.get("messages", [])
            log("STATE", f"messages 总数: {len(msgs)}", C.CYAN)
            for m in msgs[-3:]:
                role = type(m).__name__
                content_preview = str(m.content)[:80] if m.content else "(empty)"
                log("MSG", f"{role}: {content_preview}", C.DIM)

    log("DONE", "测试完成 ✓", C.GREEN)


# ────────────────────────────────────────────────────────
# 交互式菜单
# ────────────────────────────────────────────────────────

async def interactive_menu(light: bool = False):
    """交互式选择测试场景"""
    separator("Multi-Agent 场景调试工具")
    mode_label = "轻量模式 (MemorySaver)" if light else "完整模式 (PostgreSQL)"
    print(f"  {C.DIM}模式: {mode_label}{C.RESET}\n")
    print(f"""  {C.BOLD}可用测试场景:{C.RESET}

  {C.GREEN}1{C.RESET} — Supervisor 意图识别 (速度最快，不需要 MCP/DB)
  {C.GREEN}2{C.RESET} — 闲聊测试 (完整图 → Supervisor → chat_agent → END)
  {C.GREEN}3{C.RESET} — 旅行规划测试 (完整图 + 自动偏好提交，5~8 分钟)
  {C.GREEN}4{C.RESET} — 自定义输入
  {C.GREEN}q{C.RESET} — 退出
""")

    PRESETS = {
        "1": ("supervisor", "杭州三日游攻略"),
        "2": ("chat", "你好，你是谁？"),
        "3": ("travel", "帮我规划一个杭州三日游攻略"),
    }

    while True:
        choice = input(f"{C.BOLD}选择场景 [1/2/3/4/q]: {C.RESET}").strip()

        if choice == "q":
            break

        if choice in ("1", "2", "3"):
            mode, default_query = PRESETS[choice]
            custom = input(f"  输入测试问题 (回车使用默认: {default_query}): ").strip()
            query = custom or default_query
        elif choice == "4":
            query = input("  输入测试问题: ").strip()
            if not query:
                continue
            mode_choice = input("  模式 [s=supervisor / c=chat / t=travel] (默认 t): ").strip()
            mode = {"s": "supervisor", "c": "chat"}.get(mode_choice, "travel")
        else:
            print("  无效选择，请重试")
            continue

        try:
            if mode == "supervisor":
                await test_supervisor_only(query)
            else:
                await test_full_graph(query, mode=mode, light=light)
        except Exception:
            traceback.print_exc()
            log("FATAL", "测试异常终止", C.RED)

        print()  # 空行分隔


# ────────────────────────────────────────────────────────
# CLI 入口
# ────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Multi-Agent 场景调试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  uv run python debug_scenario.py --supervisor "杭州三日游"
  uv run python debug_scenario.py --chat "你好"
  uv run python debug_scenario.py --travel "杭州三日游" --light
  uv run python debug_scenario.py                  # 交互模式
  uv run python debug_scenario.py --light           # 交互模式 (轻量)""",
    )
    parser.add_argument("--supervisor", type=str, help="仅测试 Supervisor 意图识别")
    parser.add_argument("--chat", type=str, help="闲聊测试 (完整图)")
    parser.add_argument("--travel", type=str, help="旅行规划完整测试")
    parser.add_argument("--light", action="store_true",
                        help="轻量模式: 使用 MemorySaver 替代 PostgreSQL (无需数据库)")
    args = parser.parse_args()

    if args.supervisor:
        asyncio.run(test_supervisor_only(args.supervisor))
    elif args.chat:
        asyncio.run(test_full_graph(args.chat, mode="chat", light=args.light),
                    loop_factory=_loop_factory)
    elif args.travel:
        asyncio.run(test_full_graph(args.travel, mode="travel", light=args.light),
                    loop_factory=_loop_factory)
    else:
        asyncio.run(interactive_menu(light=args.light), loop_factory=_loop_factory)


if __name__ == "__main__":
    main()
