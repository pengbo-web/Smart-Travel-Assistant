# 智能旅游助手 Multi-Agent 架构详细执行文档

> **版本**: 2.0  
> **日期**: 2026-03-01  
> **开发框架**: LangGraph + FastAPI + UniApp  
> **目标**: 将现有单 Agent + 巨型 Prompt 架构重构为 Multi-Agent 协作架构

---

## 目录

1. [架构总览](#1-架构总览)
2. [目录结构](#2-目录结构)
3. [共享状态定义](#3-共享状态定义)
4. [工具分组隔离](#4-工具分组隔离)
5. [各 Agent 详细设计](#5-各-agent-详细设计)
   - 5.1 [SupervisorAgent — 意图路由](#51-supervisoragent--意图路由)
   - 5.2 [PreferenceNode — 偏好收集](#52-preferencenode--偏好收集)
   - 5.3 [WeatherStrategyNode — 天气策略计算](#53-weatherstrategynode--天气策略计算)
   - 5.4 [ResearchAgent — 信息搜集](#54-researchagent--信息搜集)
   - 5.5 [TransportAgent — 交通查询](#55-transportagent--交通查询)
   - 5.6 [MergeNode — 并发合并](#56-mergenode--并发合并)
   - 5.7 [PlanWriterAgent — 攻略写作](#57-planwriteragent--攻略写作)
   - 5.8 [MapRouteAgent — 路线规划](#58-maprouteagent--路线规划)
   - 5.9 [闲聊处理](#59-闲聊处理)
6. [LangGraph 图结构组装](#6-langgraph-图结构组装)
7. [WebSocket 消息协议](#7-websocket-消息协议)
8. [前端适配改动](#8-前端适配改动)
9. [现有代码迁移指南](#9-现有代码迁移指南)
10. [实施路线与分期](#10-实施路线与分期)
11. [场景执行流程示例](#11-场景执行流程示例)

---

## 1. 架构总览

### 1.1 现有架构问题

| 问题 | 表现 |
|---|---|
| 单 Agent 持有全部工具 | `map_data` 在阶段一就可能被调用，靠 Prompt 祈使句约束 |
| 巨型 Prompt | 188行，天气/搜索/攻略/地图/闲聊全在一个 Prompt 里 |
| 串行执行 | `asyncio.Semaphore(1)` 让本可并发的工具强制排队 |
| 无意图分类 | Prompt 内嵌 if/else 逻辑判断是否聊天/旅游 |
| 阶段控制不稳定 | 模型可能跳过阶段或交叉输出 |
| 每次请求新建 DB 连接 | `AsyncPostgresSaver.from_conn_string()` 在每次请求中创建/销毁 |

### 1.2 新架构核心原则

1. **工具隔离**：每个 Agent 只持有职责相关的工具，阶段越界在架构层面不可能发生
2. **结构化路由**：Supervisor 使用 Pydantic 结构化输出分类意图，不依赖 Prompt 文字
3. **真正并发**：ResearchAgent 和 TransportAgent 并发执行，去除 Semaphore
4. **Human-in-the-Loop**：偏好收集通过 LangGraph checkpoint 中断/恢复实现
5. **优雅降级**：天气查询根据日期自动选择实时/历史策略
6. **连接池复用**：PostgreSQL 连接在应用启动时初始化，全局复用

### 1.3 核心执行流程

```
用户消息 → SupervisorAgent(意图分类)
  ├── intent=chat → 直接调用通用LLM流式输出 → END
  └── intent=travel_plan
        → 偏好卡未完成? → 推送 preference_card → 等待用户选择 → 重新进入
        → 偏好卡已完成 → 天气策略计算
            → 并发: ResearchAgent + TransportAgent(可选)
                → MergeNode(等待两路完成)
                    → PlanWriterAgent(攻略+图片)
                        → MapRouteAgent(路线规划)
                            → END
```

### 1.4 完整架构详细图

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                        👤 用户消息（WebSocket 输入）                             ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                                  ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                     ⚡ SupervisorAgent（轻量模型 · 结构化输出）                  ┃
┃                                                                                ┃
┃  模型：qwen-max（快速，只做分类）    工具：无                                    ┃
┃  输出：Pydantic 结构化                                                          ┃
┃    • intent:       travel_plan / chat                                          ┃
┃    • destination:  目的地城市                                                   ┃
┃    • travel_days:  旅行天数（默认 3）                                           ┃
┃    • reason:       分类依据（调试用）                                            ┃
┗━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┛
                │                                            │
        intent = chat                              intent = travel_plan
                │                                            │
                ▼                                            ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━┓              ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  💬 闲聊处理             ┃              ┃  偏好检查：preferences_done?       ┃
┃                          ┃              ┗━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┛
┃  直接调用通用 LLM        ┃                    false │            │ true
┃  qwen3-max 流式输出      ┃                  (首次进入)           │(已有偏好)
┃  无工具绑定              ┃                          │            │
┃  无 SystemPrompt         ┃                          ▼            │
┃  role: assistant 推送     ┃       ┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓   │
┃                          ┃       ┃ 🎯 PreferenceNode         ┃   │
┗━━━━━━━━━┳━━━━━━━━━━━━━━━┛       ┃                            ┃   │
          │                        ┃ 纯数据节点，不调 LLM        ┃   │
          ▼                        ┃ 推送 role:preference_card  ┃   │
   ┏━━━━━━━━━┓                     ┃                            ┃   │
   ┃ ✅ END  ┃                     ┃ 前端渲染偏好选项卡片：      ┃   │
   ┗━━━━━━━━━┛                     ┃  • 出行人：一个人/情侣     ┃   │
                                   ┃          /家庭/朋友        ┃   │
                                   ┃  • 旅行节奏：特种兵        ┃   │
                                   ┃            /舒适游/无偏好  ┃   │
                                   ┃  • 旅行偏好（多选）：自然   ┃   │
                                   ┃    /文化/历史/特色体验     ┃   │
                                   ┃  • 出行预算：节俭/奢侈    ┃   │
                                   ┃  • 出发城市：文本选填      ┃   │
                                   ┃  • 出行日期：日期选择器    ┃   │
                                   ┗━━━━━━━━━━━┳━━━━━━━━━━━━━━━┛   │
                                               │                    │
                                    ┌──────────▼──────────┐         │
                                    │ 🔄 图中断(interrupt) │         │
                                    │  等待用户提交偏好     │         │
                                    │  checkpointer 持久化  │         │
                                    └──────────┬──────────┘         │
                                               │                    │
                                    用户提交偏好(第二轮消息)         │
                                    preferences_done = true         │
                                               │                    │
                                               └──┬─────────────────┘
                                                  │
                                    ┌─────────────▼───────────────────────┐
                                    │  重新进入 SupervisorAgent           │
                                    │  此时 preferences_done = true → 放行│
                                    └─────────────┬───────────────────────┘
                                                  │
                                                  ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                📅 WeatherStrategyNode（Python 纯逻辑，不调 LLM，0 token 消耗）   ┃
┃                                                                                ┃
┃  输入：preferences.travel_date                                                 ┃
┃  计算：出行日期距今天数 delta_days                                               ┃
┃                                                                                ┃
┃  ┌─────────────────┬─────────────────────┬──────────────────────────┐           ┃
┃  │ delta ≤ 7 天    │ 7 < delta ≤ 15 天   │ delta > 15 天            │           ┃
┃  │ 或未填日期      │                      │ 或节假日关键词           │           ┃
┃  │                 │                      │                          │           ┃
┃  │ ▶ realtime      │ ▶ extended           │ ▶ historical             │           ┃
┃  │ 实时天气预报    │ 近期天气趋势         │ 降级：搜索历史气候        │           ┃
┃  └─────────────────┴─────────────────────┴──────────────────────────┘           ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                                  │
                       ┌──────────┴──────────┐
                       │     并发触发 ⚡      │
                       └──┬──────────────┬───┘
                          │              │
          ┌───────────────▼───┐    ┌─────▼─────────────────┐
          │   必须执行         │    │  判断是否需要执行       │
          └─────────┬─────────┘    └──────────┬────────────┘
                    │                          │
                    ▼                          ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  🔍 ResearchAgent（信息搜集）    ┃  ┃  🚆 TransportAgent（交通查询）     ┃
┃                                  ┃  ┃                                    ┃
┃  模型：qwen3-max                 ┃  ┃  触发条件：                        ┃
┃  工具：                          ┃  ┃    preferences.departure 非空      ┃
┃    • query-weather               ┃  ┃                                    ┃
┃    • bailian_web_search          ┃  ┃  ┌──────────────────────────────┐  ┃
┃    • maps_text_search            ┃  ┃  │  departure 为空?              │  ┃
┃                                  ┃  ┃  │                              │  ┃
┃  ┌────────────────────────────┐  ┃  ┃  │  是 → transport_done = true  │  ┃
┃  │ 天气策略分支：              │  ┃  ┃  │       transport_result = ""  │  ┃
┃  │                            │  ┃  ┃  │       直接跳到 MergeNode     │  ┃
┃  │ realtime/extended:         │  ┃  ┃  │                              │  ┃
┃  │   → query-weather(目的地)  │  ┃  ┃  │  否 → 执行 TransportAgent    │  ┃
┃  │   → bailian_web_search     │  ┃  ┃  └──────────────────────────────┘  ┃
┃  │     (景点+美食)            │  ┃  ┃                                    ┃
┃  │   真正并发 asyncio.gather  │  ┃  ┃  模型：qwen3-max                   ┃
┃  │                            │  ┃  ┃  工具：                            ┃
┃  │ historical:                │  ┃  ┃    • get-stations-code-in-city    ┃
┃  │   → bailian_web_search     │  ┃  ┃    • get-tickets                  ┃
┃  │     ("XX月份气候+穿衣")    │  ┃  ┃    • get-interline-tickets        ┃
┃  │   → bailian_web_search     │  ┃  ┃    • get-train-route-stations     ┃
┃  │     (景点+美食)            │  ┃  ┃    • get-current-date             ┃
┃  │   两次搜索并发             │  ┃  ┃    • relative-date                ┃
┃  └────────────────────────────┘  ┃  ┃                                    ┃
┃                                  ┃  ┃  内部循环：                        ┃
┃  内部循环：                      ┃  ┃    transport_llm                   ┃
┃    research_llm                  ┃  ┃      ↕ (有工具调用则循环)          ┃
┃      ↕ (有工具调用则循环)        ┃  ┃    transport_tool                  ┃
┃    research_tool                 ┃  ┃                                    ┃
┃                                  ┃  ┃  产出：                            ┃
┃  产出：                          ┃  ┃    transport_result (车次/票价)     ┃
┃    research_result (天气+景点)   ┃  ┃    transport_done = true           ┃
┃    research_done = true          ┃  ┃                                    ┃
┗━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┛  ┗━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┛
                 │                                      │
                 │      ┌───────────────────────┐       │
                 └─────►│ 🔀 MergeNode          │◄──────┘
                        │                       │
                        │ LangGraph fan-in 机制  │
                        │ 等待两路都到达才放行    │
                        │                       │
                        │ ✓ research_done       │
                        │ ✓ transport_done      │
                        └───────────┬───────────┘
                                    │ 两路都完成
                                    ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                        ✍️ PlanWriterAgent（攻略写作）                            ┃
┃                                                                                ┃
┃  模型：qwen3-max                                                               ┃
┃  工具：geng-search-image（景点图片搜索）                                         ┃
┃                                                                                ┃
┃  输入（从 state 中读取）：                                                       ┃
┃    • research_result  ← ResearchAgent 产出的天气+景点数据                        ┃
┃    • transport_result ← TransportAgent 产出的交通数据（可能为空）                 ┃
┃    • preferences      ← 用户偏好（出行人/节奏/偏好/预算）                        ┃
┃    • weather_strategy ← 天气来源标注类型                                         ┃
┃                                                                                ┃
┃  ┌──────────────────────────────────────────────────────────────┐               ┃
┃  │ 偏好如何影响攻略输出：                                        │               ┃
┃  │                                                              │               ┃
┃  │ 出行人=情侣  → 推荐浪漫景点，增加"双人套餐"推荐               │               ┃
┃  │ 出行人=家庭  → 增加亲子景点，避免极限项目                      │               ┃
┃  │ 节奏=特种兵  → 每天 3-4 景点，紧凑安排                        │               ┃
┃  │ 节奏=舒适游  → 每天 2 景点，增加休闲留白                      │               ┃
┃  │ 偏好=自然    → 优先推荐自然景点                                │               ┃
┃  │ 预算=节俭    → 推荐平价酒店、街边小吃、免费景区                │               ┃
┃  │ 预算=奢侈    → 推荐精品酒店、高端餐厅、特色体验                │               ┃
┃  └──────────────────────────────────────────────────────────────┘               ┃
┃                                                                                ┃
┃  内部循环：                                                                     ┃
┃    plan_writer_llm  ←→  image_tool（search-image，每景点 ≤ 6 张）              ┃
┃                                                                                ┃
┃  产出 plan_content（完整 Markdown 攻略）：                                       ┃
┃    • 🚆 出行交通章节（有 transport_result 才展示）                               ┃
┃    • 📅 每天景点安排（含图片嵌入）                                               ┃
┃    • ☀️ 天气信息（根据 weather_strategy 标注来源类型）                            ┃
┃    • 📌 旅行贴士（根据偏好定制）                                                 ┃
┃                                                                                ┃
┃  ❗ 此 Agent 无法调用 map_data（不在工具列表中）                                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                                  │
                                  ▼
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                      🗺️ MapRouteAgent（路线规划 · 最终阶段）                     ┃
┃                                                                                ┃
┃  模型：qwen3-max                                                               ┃
┃  工具：map_data ★（此 Agent 是全局唯一持有 map_data 的节点）                      ┃
┃                                                                                ┃
┃  输入：state.plan_content（PlanWriterAgent 产出的完整攻略）                       ┃
┃                                                                                ┃
┃  执行逻辑：                                                                     ┃
┃    1. 从攻略中提取每天的景点名称                                                 ┃
┃    2. 查询各景点经纬度                                                           ┃
┃    3. 按天调用 map_data（每天一次）                                               ┃
┃       map_data → 腾讯地图驾车路线 API → 差分解压 polyline 坐标                    ┃
┃    4. 返回 role:tool_result → type:route_polyline → 前端渲染地图                  ┃
┃                                                                                ┃
┃  内部循环：                                                                     ┃
┃    map_route_llm  ←→  map_tool（map_data，按天循环调用）                         ┃
┃                                                                                ┃
┃  调用规则：                                                                     ┃
┃    • 某天只有 1 个景点 → 不调用                                                  ┃
┃    • 某天有 2+ 个景点 → 必须调用                                                 ┃
┃    • 禁止在文本中展示坐标/polyline                                               ┃
┃                                                                                ┃
┃  ❗ 其他 Agent 无法调用 map_data（物理隔离，不在其他工具列表中）                    ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                                  │
                                  ▼
                          ┏━━━━━━━━━━━━━┓
                          ┃   ✅ END    ┃
                          ┗━━━━━━━━━━━━━┛


╔══════════════════════════════════════════════════════════════════════════════════╗
║                      🔧 工具分组隔离（架构级约束）                               ║
╠═══════════════════╦═══════════════════╦═══════════════╦═══════════════════════╣
║  Research 组       ║  Transport 组      ║  Image 组      ║  Map 组              ║
║                   ║                   ║               ║                      ║
║  query-weather    ║  get-tickets      ║  search-image ║  map_data ★          ║
║  bailian_web_     ║  get-stations-    ║               ║                      ║
║    search         ║    code-in-city   ║               ║                      ║
║  maps_text_search ║  get-interline-   ║               ║                      ║
║                   ║    tickets        ║               ║                      ║
║                   ║  get-train-route- ║               ║                      ║
║                   ║    stations       ║               ║                      ║
║                   ║  get-current-date ║               ║                      ║
║                   ║  relative-date    ║               ║                      ║
╠═══════════════════╬═══════════════════╬═══════════════╬═══════════════════════╣
║  ResearchAgent    ║  TransportAgent   ║ PlanWriter    ║  MapRouteAgent       ║
║      专用         ║      专用          ║    Agent 专用 ║      专用             ║
╚═══════════════════╩═══════════════════╩═══════════════╩═══════════════════════╝


╔══════════════════════════════════════════════════════════════════════════════════╗
║                💾 共享状态 MultiAgentState（PostgreSQL 持久化）                   ║
╠══════════════════════════╦═══════════════════════════════════════════════════════╣
║  字段                     ║  说明                                                ║
╠══════════════════════════╬═══════════════════════════════════════════════════════╣
║  messages                ║  完整对话历史（add_messages 自动追加）                 ║
║  supervisor_result       ║  intent / destination / travel_days                  ║
║  preferences             ║  travelers / pace / style / budget / departure /     ║
║                          ║  travel_date / preferences_done                      ║
║  weather_strategy        ║  realtime / extended / historical                    ║
║  research_result         ║  天气 + 景点信息整合文本                               ║
║  research_done           ║  bool，ResearchAgent 完成标记                         ║
║  transport_result        ║  火车信息文本（无出发地时为 ""）                        ║
║  transport_done          ║  bool，TransportAgent 完成标记                        ║
║  plan_content            ║  完整 Markdown 攻略文本                                ║
╚══════════════════════════╩═══════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════════════════════╗
║                      📡 WebSocket 消息协议（前端消费）                            ║
╠═══════════════════════╦══════════════════════════════════════════════════════════╣
║  role                  ║  说明                                                   ║
╠═══════════════════════╬══════════════════════════════════════════════════════════╣
║  preference_card ★新增 ║  偏好选项卡片 → 前端渲染交互式 UI                        ║
║  tool                  ║  工具调用说明 → 展示 loading 步骤动画                    ║
║  tool_result           ║  工具执行结果 → 解析地图数据渲染路线                      ║
║  assistant             ║  LLM 流式输出 → token 级文字追加                         ║
║  end                   ║  回复结束 → code: 200 / 401 / 500                       ║
╚═══════════════════════╩══════════════════════════════════════════════════════════╝
```

---

## 2. 目录结构

```
agent-fastapi/
├── main.py                          # FastAPI 入口（修改 lifespan）
├── database.py                      # 数据库连接（改为连接池）
├── jwt_create.py                    # JWT 鉴权（不变）
├── tool.py                          # MCP Client 连接配置（不变）
├── tool_list.py                     # 工具中文描述映射（不变）
│
├── agents/                          # ★ 新增：各 Agent 实现
│   ├── __init__.py
│   ├── supervisor.py                # SupervisorAgent + 结构化输出
│   ├── preference.py                # PreferenceNode + 天气策略计算
│   ├── research_agent.py            # ResearchAgent（天气+景点搜索）
│   ├── transport_agent.py           # TransportAgent（火车票查询）
│   ├── plan_writer_agent.py         # PlanWriterAgent（攻略写作+图片）
│   ├── map_route_agent.py           # MapRouteAgent（地图路线规划）
│   └── chat_agent.py                # 闲聊处理（通用LLM直出）
│
├── graph/                           # ★ 新增：图结构组装
│   ├── __init__.py
│   ├── state.py                     # MultiAgentState 共享状态定义
│   ├── tool_groups.py               # 工具分组隔离逻辑
│   └── builder.py                   # LangGraph 图结构组装入口
│
├── prompts/                         # ★ 新增：Prompt 从代码分离
│   ├── supervisor.txt
│   ├── research.txt
│   ├── plan_writer.txt
│   ├── map_route.txt
│   └── transport.txt
│
├── controllers/                     # 接口层（小改动）
│   ├── chat.py                      # 修改：调用新的图构建器
│   ├── user.py                      # 不变
│   └── voice.py                     # 不变
│
├── services/                        # 业务逻辑层（重构）
│   └── chat.py                      # 修改：使用新图 + 全局连接池
│
├── models/                          # 数据模型（不变）
│   ├── user.py
│   └── conversations_list.py
│
├── schemas/                         # 请求校验（新增偏好）
│   ├── chat.py                      # 新增 PreferenceValidate
│   └── user.py                      # 不变
│
├── core/                            # 中间件（不变）
│   ├── middleware.py
│   └── response.py
│
├── docs/                            # ★ 新增：文档
│   └── MULTI_AGENT_ARCHITECTURE.md  # 本文档
│
└── state_graph.py                   # ⚠️ 旧文件，迁移完成后删除
```

---

## 3. 共享状态定义

**文件**: `graph/state.py`

```python
from typing_extensions import TypedDict, Annotated
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage
from typing import Literal


class Preferences(TypedDict, total=False):
    """用户旅行偏好，由前端偏好卡收集"""
    travelers: str       # "一个人" | "情侣" | "家庭" | "朋友"
    pace: str            # "特种兵" | "舒适游" | "无偏好"
    style: list[str]     # ["自然风光", "城市漫步", "历史文化", "特色体验"]
    budget: str          # "节俭" | "奢侈" | "灵活"
    departure: str       # 出发城市（选填，空字符串表示未填）
    travel_date: str     # ISO 格式 "2026-05-01"（选填，空字符串表示未填）


class SupervisorResult(TypedDict):
    """SupervisorAgent 的结构化输出"""
    intent: str              # "travel_plan" | "chat"
    destination: str         # 目的地城市
    travel_days: int         # 旅行天数（默认 3）


class MultiAgentState(TypedDict):
    """整个 Multi-Agent 图的共享状态"""

    # ── 对话历史（所有 Agent 共享，自动追加）──
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Supervisor 解析结果 ──
    supervisor_result: SupervisorResult

    # ── 偏好收集 ──
    preferences: Preferences
    preferences_done: bool   # false → 推送偏好卡; true → 进入规划

    # ── 天气策略（Python 纯逻辑计算）──
    weather_strategy: str    # "realtime" | "extended" | "historical"

    # ── ResearchAgent 产出 ──
    research_result: str     # 天气 + 景点信息整合文本
    research_done: bool

    # ── TransportAgent 产出 ──
    transport_result: str    # 火车/高铁信息，无出发地时为 ""
    transport_done: bool

    # ── PlanWriterAgent 产出 ──
    plan_content: str        # 完整 Markdown 攻略文本
```

### 3.1 字段流转矩阵

| 字段 | 写入者 | 读取者 |
|---|---|---|
| `messages` | 所有节点 | 所有节点 |
| `supervisor_result` | SupervisorAgent | PreferenceNode, ResearchAgent, TransportAgent |
| `preferences` | PreferenceNode（从WebSocket消息解析） | ResearchAgent, PlanWriterAgent |
| `preferences_done` | SupervisorAgent（初始化）, PreferenceNode | SupervisorAgent（路由判断） |
| `weather_strategy` | WeatherStrategyNode | ResearchAgent |
| `research_result` | ResearchAgent | PlanWriterAgent |
| `research_done` | ResearchAgent | MergeNode |
| `transport_result` | TransportAgent / SupervisorAgent（无出发地时设""） | PlanWriterAgent |
| `transport_done` | TransportAgent / SupervisorAgent（无出发地时设true） | MergeNode |
| `plan_content` | PlanWriterAgent | MapRouteAgent |

---

## 4. 工具分组隔离

**文件**: `graph/tool_groups.py`

```python
from langchain_core.tools import BaseTool


# 工具分组定义
TOOL_GROUPS = {
    "research": {
        "bailian_web_search",   # 联网搜索景点/美食/攻略
        "query-weather",        # 天气查询（zuimei-getweather MCP）
        "maps_weather",         # 高德天气（备用）
        "maps_text_search",     # 关键词搜索 POI
    },
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
    "image": {
        "search-image",         # geng-search-image MCP 搜索景点图片
    },
    "map": {
        "map_data",             # ★ 本地工具：腾讯地图驾车路线规划
    },
}


def split_tools(all_tools: list[BaseTool]) -> dict[str, list[BaseTool]]:
    """
    将全量工具列表按分组拆分，每个 Agent 只拿到对应的工具子集。

    返回:
        {
            "research": [BaseTool, ...],
            "transport": [BaseTool, ...],
            "image": [BaseTool, ...],
            "map": [BaseTool, ...],
        }
    """
    by_name = {tool.name: tool for tool in all_tools}
    result = {}
    for group_name, tool_names in TOOL_GROUPS.items():
        result[group_name] = [
            by_name[name] for name in tool_names if name in by_name
        ]
    # 打印未分配的工具（调试用）
    assigned = set().union(*TOOL_GROUPS.values())
    unassigned = set(by_name.keys()) - assigned
    if unassigned:
        print(f"[tool_groups] 未分配的工具: {unassigned}")
    return result
```

### 4.1 隔离效果

| Agent | 持有工具 | 物理上不可调用 |
|---|---|---|
| ResearchAgent | query-weather, bailian_web_search, maps_text_search | map_data, get-tickets, search-image |
| TransportAgent | get-tickets, get-stations-code-in-city 等 | map_data, query-weather, search-image |
| PlanWriterAgent | search-image | map_data, query-weather, get-tickets |
| MapRouteAgent | map_data | query-weather, get-tickets, search-image |
| SupervisorAgent | 无工具 | 全部 |

---

## 5. 各 Agent 详细设计

### 5.1 SupervisorAgent — 意图路由

**文件**: `agents/supervisor.py`  
**模型**: `qwen-max`（轻量、快速，只做分类不做生成）  
**工具**: 无  
**职责**: 解析用户意图，提取关键信息，路由到对应分支

#### 5.1.1 结构化输出

```python
from pydantic import BaseModel, Field
from typing import Literal


class SupervisorOutput(BaseModel):
    """Supervisor的结构化输出，使用Pydantic强制约束返回格式"""
    intent: Literal["travel_plan", "chat"] = Field(
        description="意图分类：travel_plan=旅游规划，chat=闲聊/其他"
    )
    destination: str = Field(
        default="",
        description="目的地城市名，如'杭州'、'西安'，非旅游意图时为空"
    )
    travel_days: int = Field(
        default=3,
        description="旅行天数，用户未说明时默认3天"
    )
    reason: str = Field(
        description="分类依据，用于调试和日志"
    )
```

#### 5.1.2 Prompt

**文件**: `prompts/supervisor.txt`

```
你是旅游助手的意图分析模块，只负责分析用户消息的意图并提取关键信息。

分类规则：
1. 如果用户提到"旅行/旅游/规划/攻略/景点/几日游"等旅游相关词汇 → intent="travel_plan"
2. 其他所有情况（闲聊、问好、技术问题等）→ intent="chat"

提取规则（仅 travel_plan 时）：
- destination：从消息中提取目的地城市名
- travel_days：提取旅行天数，未提及则默认 3

请严格按照指定的 JSON Schema 输出，不要输出任何多余文字。
```

#### 5.1.3 节点实现

```python
from langchain_community.chat_models.tongyi import ChatTongyi
from graph.state import MultiAgentState
import os

def create_supervisor_llm():
    """创建 Supervisor 专用的结构化输出 LLM"""
    API_KEY = os.getenv("API_KEY")
    llm = ChatTongyi(model="qwen-max", api_key=API_KEY)
    return llm.with_structured_output(SupervisorOutput)


async def supervisor_node(state: MultiAgentState) -> dict:
    """
    Supervisor 节点：
    1. 分析意图
    2. 初始化偏好状态（如果是首次旅游请求）
    3. 返回路由所需字段
    """
    llm = create_supervisor_llm()

    # 只传入最后一条用户消息（减少 token）
    last_user_msg = state["messages"][-1]
    result: SupervisorOutput = await llm.ainvoke([last_user_msg])

    update = {
        "supervisor_result": {
            "intent": result.intent,
            "destination": result.destination,
            "travel_days": result.travel_days,
        },
    }

    # 旅游意图 + 偏好未完成时，初始化标记
    if result.intent == "travel_plan" and not state.get("preferences_done"):
        update["preferences_done"] = False
        update["transport_done"] = False
        update["research_done"] = False
        update["transport_result"] = ""

    return update


def supervisor_router(state: MultiAgentState) -> str:
    """Supervisor 之后的条件路由"""
    intent = state["supervisor_result"]["intent"]
    if intent == "chat":
        return "chat_agent"
    # travel_plan
    if state.get("preferences_done"):
        return "weather_strategy"
    else:
        return "preference_node"
```

#### 5.1.4 路由表

| 条件 | 下一节点 |
|---|---|
| `intent = "chat"` | `chat_agent` |
| `intent = "travel_plan"` + `preferences_done = false` | `preference_node` |
| `intent = "travel_plan"` + `preferences_done = true` | `weather_strategy` |

---

### 5.2 PreferenceNode — 偏好收集

**文件**: `agents/preference.py`  
**模型**: 无（纯数据节点）  
**工具**: 无  
**职责**: 向前端推送偏好选项卡片，等待用户选择后写入 state

#### 5.2.1 节点实现

```python
from graph.state import MultiAgentState
from langchain_core.messages import AIMessage
import json


# 偏好卡片配置（可抽到配置文件）
PREFERENCE_CARD = {
    "question": "为了提供更个性化的建议，可以给我提供一些你的旅行偏好～",
    "fields": [
        {
            "key": "travelers",
            "label": "🧑‍🤝‍🧑 出行人",
            "options": ["一个人", "情侣", "家庭", "朋友"],
            "multi": False,
        },
        {
            "key": "pace",
            "label": "🏃 旅行节奏",
            "options": ["特种兵", "舒适游", "无偏好"],
            "multi": False,
        },
        {
            "key": "style",
            "label": "🎯 旅行偏好",
            "options": ["自然风光", "城市漫步", "历史文化", "特色体验"],
            "multi": True,  # 多选
        },
        {
            "key": "budget",
            "label": "💰 出行预算",
            "options": ["节俭", "奢侈", "灵活"],
            "multi": False,
        },
        {
            "key": "departure",
            "label": "🚄 出发城市",
            "type": "text",
            "placeholder": "选填，填写后为你查询交通方案",
        },
        {
            "key": "travel_date",
            "label": "📅 出行日期",
            "type": "date",
            "placeholder": "选填，不填默认近期出发",
        },
    ],
}


async def preference_node(state: MultiAgentState) -> dict:
    """
    推送偏好卡片给前端。

    此节点不调用 LLM，返回一条特殊格式的 AIMessage，
    services/chat.py 的流式处理层识别后推送 role:preference_card。

    使用 LangGraph 的 interrupt 机制中断图执行，
    等待用户提交偏好后恢复。
    """
    card_content = json.dumps(PREFERENCE_CARD, ensure_ascii=False)

    return {
        "messages": [
            AIMessage(
                content=card_content,
                additional_kwargs={"type": "preference_card"},
            )
        ],
    }
    # ⚠️ 此处图执行会中断（interrupt）
    # 用户提交偏好后，通过 update_state 写入 preferences
    # preferences_done 设为 true，然后 resume 图继续执行


async def handle_preference_submission(
    preferences: dict,
    state: MultiAgentState,
) -> dict:
    """
    处理用户提交的偏好数据（在 services/chat.py 中调用）。

    Args:
        preferences: 前端提交的偏好数据
            {
                "travelers": "情侣",
                "pace": "舒适游",
                "style": ["自然风光", "城市漫步"],
                "budget": "灵活",
                "departure": "上海",
                "travel_date": "2026-05-01"
            }
    """
    # 处理出发地：根据偏好中的 departure 决定 transport_done
    departure = preferences.get("departure", "").strip()
    has_departure = bool(departure)

    return {
        "preferences": preferences,
        "preferences_done": True,
        "transport_done": not has_departure,  # 无出发地 → transport 直接标记完成
        "transport_result": "",
    }
```

#### 5.2.2 Human-in-the-Loop 实现机制

LangGraph 的 `interrupt` + `resume` 机制是实现偏好收集的关键：

```
第一轮消息 → Supervisor → PreferenceNode
  ↓ preference_node 返回后，图执行中断（interrupt_before/interrupt_after）
  ↓ checkpointer 保存当前 state 到 PostgreSQL
  ↓ WebSocket 推送 preference_card 给前端

（等待）

前端用户选择偏好 → WebSocket 发送第二轮消息
  ↓ 后端调用 graph.update_state(config, preferences_update) 写入偏好
  ↓ 调用 graph.astream(None, config) 恢复图执行（resume）
  ↓ Supervisor 再次进入，此时 preferences_done=true → 放行到 weather_strategy
```

使用 LangGraph 的 `interrupt` API：

```python
# 在图编译时配置中断点
agent_graph = builder.compile(
    checkpointer=checkpointer,
    store=store,
    interrupt_after=["preference_node"],  # preference_node 执行后中断
)
```

---

### 5.3 WeatherStrategyNode — 天气策略计算

**文件**: `agents/preference.py`（与 PreferenceNode 放在同一文件）  
**模型**: 无（Python 纯逻辑）  
**工具**: 无  
**职责**: 根据出行日期计算天气查询策略

#### 5.3.1 节点实现

```python
from datetime import datetime, date


async def weather_strategy_node(state: MultiAgentState) -> dict:
    """
    纯 Python 逻辑节点，不消耗 LLM token。
    根据出行日期距今天数决定天气查询策略。
    """
    travel_date_str = state.get("preferences", {}).get("travel_date", "")
    today = date.today()

    if not travel_date_str:
        # 未填写日期，按近期出发处理
        strategy = "realtime"
    else:
        try:
            travel_date = datetime.strptime(travel_date_str, "%Y-%m-%d").date()
            delta_days = (travel_date - today).days

            if delta_days <= 7:
                strategy = "realtime"    # 7天内，实时天气预报
            elif delta_days <= 15:
                strategy = "extended"    # 7-15天，近期趋势
            else:
                strategy = "historical"  # 超过15天，降级为历史气候
        except ValueError:
            strategy = "realtime"  # 日期格式异常，兜底

    return {"weather_strategy": strategy}
```

#### 5.3.2 策略说明

| 策略 | 触发条件 | ResearchAgent 行为 | 攻略中展示 |
|---|---|---|---|
| `realtime` | 日期在 7 天内 / 未填日期 | 调用 `query-weather` API | ☀️ 实时天气预报 |
| `extended` | 日期在 7-15 天内 | 调用 `query-weather` + 提示参考 | 🌤️ 近期趋势，建议出发前再次确认 |
| `historical` | 日期超过 15 天 | 调用 `bailian_web_search` 搜索历史气候 | 📅 历史气候参考数据 |

---

### 5.4 ResearchAgent — 信息搜集

**文件**: `agents/research_agent.py`  
**模型**: `qwen3-max`  
**工具**: `query-weather`, `bailian_web_search`, `maps_text_search`  
**职责**: 并发搜集目的地天气 + 景点/美食/酒店信息

#### 5.4.1 Prompt

**文件**: `prompts/research.txt`

```
你是旅游信息搜集专员，只负责搜集原始信息，不生成攻略内容。

目的地：{destination}
旅行天数：{travel_days}天
旅行偏好：{style}
天气策略：{weather_strategy}

## 任务

### 天气搜集
- 如果 weather_strategy 为 "realtime" 或 "extended"：
  调用 query-weather 工具查询 {destination} 的天气预报
- 如果 weather_strategy 为 "historical"：
  调用 bailian_web_search 搜索 "{destination} {month}月份气候特点 历史天气 穿衣建议"

### 景点搜集
调用 bailian_web_search 搜索以下信息：
- "{destination} {style} 必去景点推荐"
- 包含景点名称、门票、开放时间等核心信息

## 输出要求
搜集完毕后，将所有工具返回的原始信息整合为结构化文本，格式：

[天气信息]
（工具返回的天气数据）
天气策略类型：{weather_strategy}

[景点与美食信息]
（工具返回的景点数据）

注意：
- 你只负责搜集和整合信息，不要生成攻略
- 不要遗漏工具返回的任何有用数据
- 不要调用 search-image 或 map_data 工具（你没有这些工具）
```

#### 5.4.2 节点实现关键点

```python
async def research_llm_node(state: MultiAgentState, tools: list) -> dict:
    """ResearchAgent 的 LLM 节点"""
    prefs = state.get("preferences", {})
    supervisor = state["supervisor_result"]

    # 注入上下文到 Prompt
    prompt_text = load_prompt("prompts/research.txt").format(
        destination=supervisor["destination"],
        travel_days=supervisor["travel_days"],
        style=", ".join(prefs.get("style", ["综合"])),
        weather_strategy=state["weather_strategy"],
        month=extract_month(prefs.get("travel_date", "")),
    )

    llm_with_tools = ChatOpenAI(
        model="qwen3-max",
        api_key=os.getenv("API_KEY"),
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    ).bind_tools(tools)

    messages = [SystemMessage(content=prompt_text)] + state["messages"][-1:]  # 只传最后一条用户消息
    response = await llm_with_tools.ainvoke(messages)
    return {"messages": [response]}


async def research_tool_node(state: MultiAgentState, tools: list) -> dict:
    """
    ResearchAgent 的工具执行节点。
    ★ 关键改进：去掉 Semaphore，使用 asyncio.gather 真正并发。
    """
    tools_by_name = {t.name: t for t in tools}
    last_message = cast(AIMessage, state["messages"][-1])

    tasks = [
        tools_by_name[tc["name"]].ainvoke(tc["args"])
        for tc in last_message.tool_calls
    ]
    # ★ 真正并发执行！天气和搜索互不依赖
    results = await asyncio.gather(*tasks, return_exceptions=True)

    tool_messages = []
    for tc, result in zip(last_message.tool_calls, results):
        content = f"工具执行失败: {repr(result)}" if isinstance(result, Exception) else str(result)
        tool_messages.append(ToolMessage(content=content, tool_call_id=tc["id"]))
    return {"messages": tool_messages}


def research_route(state: MultiAgentState) -> str:
    """Research 内部路由：有工具调用则执行，否则完成"""
    last = cast(AIMessage, state["messages"][-1])
    if last.tool_calls:
        return "call_tool"
    # 搜集完毕，将最后一条 AI 消息内容存入 research_result
    return "done"


async def research_done_node(state: MultiAgentState) -> dict:
    """搜集完毕，提取结果并标记完成"""
    last_ai = cast(AIMessage, state["messages"][-1])
    return {
        "research_result": last_ai.content,
        "research_done": True,
    }
```

#### 5.4.3 内部循环图

```
research_llm_node → [有工具调用?]
    ├── 是 → research_tool_node → research_llm_node（循环）
    └── 否 → research_done_node → merge_check
```

---

### 5.5 TransportAgent — 交通查询

**文件**: `agents/transport_agent.py`  
**模型**: `qwen3-max`  
**工具**: `get-tickets`, `get-stations-code-in-city`, `get-interline-tickets`, `get-train-route-stations`, `get-current-date`, `relative-date`  
**职责**: 查询出发地到目的地的火车/高铁方案

#### 5.5.1 触发条件

| 条件 | 行为 |
|---|---|
| `preferences.departure` 非空 | 执行 TransportAgent |
| `preferences.departure` 为空 | 跳过，`transport_done=true`, `transport_result=""` |

#### 5.5.2 Prompt

**文件**: `prompts/transport.txt`

```
你是出行交通查询专员，只负责查询出发地到目的地的火车/高铁信息。

出发地：{departure}
目的地：{destination}
出行日期：{travel_date}

## 任务
1. 调用 get-stations-code-in-city 获取出发地和目的地的火车站代码
2. 调用 get-tickets 查询所选日期的可用车次
3. 如果无直达车次，调用 get-interline-tickets 查询中转方案

## 输出格式（纯文本，供攻略写手整合）
[出行交通]
推荐直达车次：
  - G123 {departure}→{destination}，约X小时，二等座约¥XXX
  - G456 {departure}→{destination}，约X小时，二等座约¥XXX

中转方案（如有）：
  - G789 {departure}→中转站 + G012 中转站→{destination}

注意：
- 只输出纯文本格式的交通信息
- 不要生成攻略内容
- 不要调用不属于你的工具
```

#### 5.5.3 节点实现

```python
async def transport_check_node(state: MultiAgentState) -> dict:
    """判断是否需要执行 TransportAgent"""
    departure = state.get("preferences", {}).get("departure", "").strip()
    if not departure:
        return {
            "transport_done": True,
            "transport_result": "",
        }
    return {}  # 继续到 transport_agent


def transport_check_router(state: MultiAgentState) -> str:
    if state.get("transport_done"):
        return "merge_check"
    return "transport_agent"
```

内部循环结构与 ResearchAgent 相同。

---

### 5.6 MergeNode — 并发合并

**文件**: `graph/builder.py`（内联节点）  
**模型**: 无  
**工具**: 无  
**职责**: 等待 ResearchAgent 和 TransportAgent 都完成后才放行

#### 5.6.1 实现

```python
async def merge_node(state: MultiAgentState) -> dict:
    """
    并发汇合点。
    LangGraph 的 fan-in 机制：当所有发往此节点的路径都到达后才执行。
    此节点本身不做任何操作，只是一个同步栅栏。
    """
    return {}


def merge_router(state: MultiAgentState) -> str:
    """确认两路都完成才放行到 PlanWriter"""
    if state.get("research_done") and state.get("transport_done"):
        return "plan_writer"
    # 理论上不会走到这里（LangGraph fan-in 保证）
    return "wait"
```

#### 5.6.2 并发机制说明

LangGraph 中，如果两条边都指向同一个节点，该节点会等待两个上游都完成后才执行：

```python
# ResearchAgent 完成后走到 merge
builder.add_edge("research_done", "merge_node")
# TransportAgent 完成后也走到 merge（或跳过直接标记完成后走到 merge）
builder.add_edge("transport_done_node", "merge_node")
```

这就是 **fan-in** 模式——`merge_node` 天然会等待两路都到达。

---

### 5.7 PlanWriterAgent — 攻略写作

**文件**: `agents/plan_writer_agent.py`  
**模型**: `qwen3-max`  
**工具**: `search-image`（geng-search-image MCP）  
**职责**: 基于搜集数据生成个性化攻略 + 为景点搜索配图

#### 5.7.1 Prompt

**文件**: `prompts/plan_writer.txt`

```
你是专业旅游攻略写手，请基于准备好的全部数据生成定制化攻略。

## 已准备的数据

[景点与天气数据]
{research_result}

[出行交通数据]
{transport_result}

## 用户偏好
- 出行人：{travelers}
- 旅行节奏：{pace}
- 旅行偏好：{style}
- 出行预算：{budget}
- 目的地：{destination}
- 天数：{travel_days}天

## 天气展示规则
- 天气策略为 "realtime"：正常展示预报，标注"☀️ 实时天气预报"
- 天气策略为 "extended"：展示趋势，标注"🌤️ 建议出发前再次确认天气"
- 天气策略为 "historical"：展示气候数据，标注"📅 历史气候参考"

## 攻略格式规范

**🌸{travel_days}天{destination}精华之旅🏔️**
（一句话点题）

### 🚆 出行交通（有 transport_result 才展示此章节）
（整合交通数据）

### 🚆 Day 1：景点A + 景点B
**上午｜景点A**
- 景点介绍（来自搜索数据，不编造）
- 为此景点调用 search-image 搜索图片（≤6张）
- 图片以 Markdown 格式嵌入：![景点名](图片URL)
- 门票/开放时间
- 拍摄建议

**下午｜景点B**
- 同上格式

### 📌 旅行小贴士
- 天气信息（按天气策略规则展示）
- 个性化建议（根据偏好定制）

## 规范
- 每天不超过 3 个景点（"特种兵"节奏可放宽到 4 个）
- "舒适游"节奏每天 2 个景点为宜
- 景点内容必须来自搜索数据
- 不得编造天气数据
- 图片必须通过 search-image 工具获取
- ❗ 此阶段禁止调用 map_data 工具（你没有此工具）
```

#### 5.7.2 偏好如何影响攻略

| 偏好 | 影响 | 具体体现 |
|---|---|---|
| 出行人=情侣 | 景点推荐偏浪漫 | "推荐傍晚来洱海看日落" |
| 出行人=家庭 | 避免极限项目 | 不推荐高难度登山，增加亲子景点 |
| 节奏=特种兵 | 每天 3-4 景点 | 紧凑安排，增加步行导航时间提示 |
| 节奏=舒适游 | 每天 2 景点 | 增加"在xx咖啡厅休息"等留白 |
| 偏好=自然风光 | 景点类型偏自然 | 优先推荐苍山/洱海，弱化人文景点 |
| 预算=节俭 | 推荐平价选项 | 青年旅舍、街边小吃、免费景区 |
| 预算=奢侈 | 推荐高端选项 | 精品酒店、私人导游、特色餐厅 |

#### 5.7.3 内部循环图

```
plan_writer_llm → [有工具调用(search-image)?]
    ├── 是 → image_tool_node → plan_writer_llm（循环搜索更多图片）
    └── 否 → plan_writer_done → map_route_agent
```

---

### 5.8 MapRouteAgent — 路线规划

**文件**: `agents/map_route_agent.py`  
**模型**: `qwen3-max`  
**工具**: `map_data` ★（此 Agent 是唯一持有 `map_data` 的节点）  
**职责**: 从攻略中提取景点经纬度，按天调用腾讯地图生成路线

#### 5.8.1 Prompt

**文件**: `prompts/map_route.txt`

```
你是地图路线规划专员，负责根据旅游攻略生成每天的地图路线。

已生成的旅游攻略内容：
{plan_content}

## 任务
1. 从攻略中提取每天涉及的景点名称
2. 查询各景点的经纬度（如果攻略中没有经纬度信息，使用常识估算或跳过）
3. 每天调用一次 map_data 工具，传入：
   - from_location: 起点经纬度 "lat,lng"
   - to_location: 终点经纬度 "lat,lng"
   - waypoints: 途经点经纬度（多个用分号拼接）
   - day: "第一天" / "第二天" / ...
   - markers: 景点标记列表

## 调用规则
- 某天只有 1 个景点时不调用 map_data
- 某天有 2+ 个景点时必须调用
- 每天调用一次，不合并
- 多天需要多次调用

## 禁止
- 不在文本中展示 points、polyline、坐标
- 不输出工具返回的 JSON
- 不解释路线数据
- 完成所有天的路线调用后，直接结束，不输出额外文字
```

#### 5.8.2 内部循环图

```
map_route_llm → [有工具调用(map_data)?]
    ├── 是 → map_tool_node → map_route_llm（继续下一天）
    └── 否 → END
```

#### 5.8.3 map_data 工具（保持不变）

沿用现有的 `map_data` 本地工具实现，不做修改。工具从 `state_graph.py` 提取到独立文件：

```python
# agents/map_route_agent.py 中包含 map_data 工具定义
# 保持与现有实现完全一致的功能：
# - 调用腾讯地图驾车路线 API
# - 差分解压 polyline 坐标
# - 返回 {"points": [...], "type": "route_polyline", "day": "...", "marker": [...]}
```

---

### 5.9 闲聊处理

**文件**: `agents/chat_agent.py`  
**模型**: `qwen3-max`（通用能力，无 SystemPrompt）  
**工具**: 无  
**职责**: 作为通用 LLM，流式回复非旅游类问题

#### 5.9.1 实现

```python
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
```

chat_agent 执行后直接到 `END`，最简路径。

---

## 6. LangGraph 图结构组装

**文件**: `graph/builder.py`

```python
from langgraph.graph import StateGraph, START, END
from graph.state import MultiAgentState
from functools import partial


def build_multi_agent_graph(checkpointer, store, tool_groups):
    """
    构建 Multi-Agent 协作图。

    Args:
        checkpointer: AsyncPostgresSaver 实例（全局连接池）
        store: AsyncPostgresStore 实例（全局连接池）
        tool_groups: split_tools() 返回的工具分组 dict
    """
    builder = StateGraph(MultiAgentState)

    # ════════════════════════════════════════
    # 节点注册
    # ════════════════════════════════════════

    # 主干节点
    builder.add_node("supervisor",          supervisor_node)
    builder.add_node("chat_agent",          chat_agent_node)
    builder.add_node("preference_node",     preference_node)
    builder.add_node("weather_strategy",    weather_strategy_node)

    # TravelPipeline - Research 分支
    builder.add_node("research_llm",        partial(research_llm_node,   tools=tool_groups["research"]))
    builder.add_node("research_tool",       partial(research_tool_node,  tools=tool_groups["research"]))
    builder.add_node("research_done",       research_done_node)

    # TravelPipeline - Transport 分支
    builder.add_node("transport_check",     transport_check_node)
    builder.add_node("transport_llm",       partial(transport_llm_node,  tools=tool_groups["transport"]))
    builder.add_node("transport_tool",      partial(transport_tool_node, tools=tool_groups["transport"]))
    builder.add_node("transport_done",      transport_done_node)

    # TravelPipeline - 合并 + 写作 + 地图
    builder.add_node("merge_node",          merge_node)
    builder.add_node("plan_writer_llm",     partial(plan_writer_llm_node, tools=tool_groups["image"]))
    builder.add_node("image_tool",          partial(image_tool_node,      tools=tool_groups["image"]))
    builder.add_node("plan_writer_done",    plan_writer_done_node)
    builder.add_node("map_route_llm",       partial(map_route_llm_node,   tools=tool_groups["map"]))
    builder.add_node("map_tool",            partial(map_tool_node,         tools=tool_groups["map"]))

    # ════════════════════════════════════════
    # 边（连接）定义
    # ════════════════════════════════════════

    # ── 入口 ──
    builder.add_edge(START, "supervisor")

    # ── Supervisor 三路分发 ──
    builder.add_conditional_edges("supervisor", supervisor_router, {
        "chat_agent":       "chat_agent",
        "preference_node":  "preference_node",
        "weather_strategy": "weather_strategy",
    })

    # ── 闲聊 → 结束 ──
    builder.add_edge("chat_agent", END)

    # ── 偏好卡（中断点，等待用户选择后恢复）──
    # preference_node 执行后图中断，等待 resume
    # resume 后重新从 supervisor 开始，此时 preferences_done=true

    # ── 天气策略 → 并发分叉 ──
    builder.add_edge("weather_strategy", "research_llm")       # 分叉路径1
    builder.add_edge("weather_strategy", "transport_check")    # 分叉路径2

    # ── Research 内部循环 ──
    builder.add_conditional_edges("research_llm", research_route, {
        "call_tool":  "research_tool",
        "done":       "research_done",
    })
    builder.add_edge("research_tool", "research_llm")
    builder.add_edge("research_done", "merge_node")

    # ── Transport 判断 + 内部循环 ──
    builder.add_conditional_edges("transport_check", transport_check_router, {
        "transport_agent":  "transport_llm",
        "merge_check":      "merge_node",     # 无出发地，直接到合并
    })
    builder.add_conditional_edges("transport_llm", transport_route, {
        "call_tool":  "transport_tool",
        "done":       "transport_done",
    })
    builder.add_edge("transport_tool", "transport_llm")
    builder.add_edge("transport_done", "merge_node")

    # ── 合并 → 攻略写作 ──
    builder.add_edge("merge_node", "plan_writer_llm")

    # ── PlanWriter 内部循环 ──
    builder.add_conditional_edges("plan_writer_llm", plan_writer_route, {
        "call_tool":  "image_tool",
        "done":       "plan_writer_done",
    })
    builder.add_edge("image_tool", "plan_writer_llm")
    builder.add_edge("plan_writer_done", "map_route_llm")

    # ── MapRoute 内部循环 ──
    builder.add_conditional_edges("map_route_llm", map_route_logic, {
        "call_tool":  "map_tool",
        "done":       END,
    })
    builder.add_edge("map_tool", "map_route_llm")

    # ════════════════════════════════════════
    # 编译
    # ════════════════════════════════════════
    return builder.compile(
        checkpointer=checkpointer,
        store=store,
        interrupt_after=["preference_node"],  # 偏好卡后中断
    )
```

---

## 7. WebSocket 消息协议

### 7.1 服务端 → 前端（推送）

| role | 触发时机 | content 格式 | 前端处理 |
|---|---|---|---|
| `preference_card` | **新增** PreferenceNode 推送 | JSON：`{question, fields}` | 渲染偏好选项 UI |
| `tool` | Agent 发起工具调用 | string：工具描述 | 展示步骤动画 |
| `tool_result` | 工具返回结果 | `{toolName: result}` | 地图数据解析渲染 |
| `assistant` | LLM 流式输出 | string：token片段 | 追加显示文字 |
| `end` | 回复结束 | `{code: 200/401/500}` | 解除输入禁用 |

### 7.2 前端 → 服务端（发送）

**普通消息**（不变）：
```json
{
  "sessionId": "uuid-xxx",
  "content": "帮我规划杭州3日游"
}
```

**偏好提交**（新增，第二轮消息）：
```json
{
  "sessionId": "uuid-xxx",
  "content": "",
  "type": "preference_submit",
  "preferences": {
    "travelers": "情侣",
    "pace": "舒适游",
    "style": ["自然风光", "城市漫步"],
    "budget": "灵活",
    "departure": "上海",
    "travel_date": "2026-05-01"
  }
}
```

### 7.3 services/chat.py 流式处理适配

```python
# 需要新增 preference_card 消息类型的识别逻辑
async for item, metadata in graph.astream(messages, stream_mode="messages", config=config):
    if isinstance(item, AIMessageChunk):
        # 判断是否是偏好卡
        if item.additional_kwargs.get("type") == "preference_card":
            yield {"role": "preference_card", "content": json.loads(item.content)}
        elif item.tool_calls:
            for call in item.tool_calls:
                desc = TOOL_LIST.get(call["name"], "未知工具")
                if desc != "未知工具":
                    yield {"role": "tool", "content": desc}
        elif item.content:
            yield {"role": "assistant", "content": item.content}
    elif isinstance(item, ToolMessage):
        yield {"role": "tool_result", "content": {item.name: item.content}}
```

---

## 8. 前端适配改动

### 8.1 TypeScript 类型新增

```typescript
// types/index.d.ts 新增

// 偏好选项字段定义
export type PreferenceField = {
  key: string;
  label: string;
  options?: string[];
  multi?: boolean;      // 是否多选
  type?: "text" | "date";  // 文本输入或日期选择
  placeholder?: string;
};

// 偏好卡片数据
export type PreferenceCardType = {
  question: string;
  fields: PreferenceField[];
};

// 用户选择的偏好
export type UserPreferences = {
  travelers: string;
  pace: string;
  style: string[];
  budget: string;
  departure: string;
  travel_date: string;
};

// AiMessageType 新增 preference_card 角色
export type AiMessageType = {
  role: "user" | "tool" | "tool_result" | "assistant" | "end" | "preference_card";
  content: string | PreferenceCardType;
  code?: number;
};

// MessageListType 新增偏好卡片字段
export type MessageListType = {
  role: "user" | "tool" | "tool_result" | "assistant" | "end" | "preference_card";
  content: string;
  preferenceCard?: PreferenceCardType;  // 偏好卡片数据
  // ... 其他现有字段不变
};
```

### 8.2 Pinia Store 改动

```typescript
// store/index.ts 新增处理逻辑

// 在 socketTask.onMessage 中新增：
if (modelObj.role === "preference_card") {
  aiMessageObj.preferenceCard = modelObj.content as PreferenceCardType;
  aiMessageObj.loadingCircle = false;
  aiMessageObj.toolThink = false;
  // 不设置 disabledStatus = false，
  // 因为用户还需要提交偏好后才能继续
}
```

### 8.3 新增 PreferenceCard.vue 组件

在 `pages/chat/component/` 下新增 `PreferenceCard.vue`，渲染偏好选项卡片（参考截图中的 UI 样式）。用户点击选项后，通过 WebSocket 发送 `preference_submit` 消息。

---

## 9. 现有代码迁移指南

### 9.1 需要修改的文件

| 文件 | 改动级别 | 说明 |
|---|---|---|
| `main.py` | 中等 | lifespan 中初始化全局连接池，注册工具分组 |
| `services/chat.py` | 较大 | 替换 `state_graph()` 为 `build_multi_agent_graph()`，新增偏好消息处理 |
| `controllers/chat.py` | 小 | WebSocket 处理增加 `type: preference_submit` 分支 |
| `model_prompt.py` | 删除 | Prompt 迁移到 `prompts/` 目录 |
| `state_graph.py` | 删除 | 拆分到 `agents/` 和 `graph/` |

### 9.2 main.py 改动要点

```python
# 旧代码
from state_graph import client, tontyi, map_data

# 新代码
from tool import client
from graph.tool_groups import split_tools
from graph.builder import build_multi_agent_graph

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    # 读取 MCP 工具
    mcp_tools = await client.get_tools()
    all_tools = mcp_tools + [map_data]   # map_data 从 agents/map_route_agent.py 导入
    # ★ 工具分组
    tool_groups = split_tools(all_tools)
    # ★ 全局 PostgreSQL 连接池
    async with AsyncPostgresStore.from_conn_string(DB_URI) as store:
        async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
            await store.setup()
            await checkpointer.setup()
            app.state.graph_deps = {
                "tool_groups": tool_groups,
                "checkpointer": checkpointer,
                "store": store,
            }
            yield
```

### 9.3 services/chat.py 改动要点

```python
# 旧代码：每次请求新建连接
async with AsyncPostgresStore.from_conn_string(DB_URI) as store:
    async with AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer:
        ...

# 新代码：使用全局连接池
def get_graph_deps(websocket: WebSocket):
    return websocket.app.state.graph_deps

async def main_model(thread_id, user_id, content, session, graph_deps):
    graph = build_multi_agent_graph(
        checkpointer=graph_deps["checkpointer"],
        store=graph_deps["store"],
        tool_groups=graph_deps["tool_groups"],
    )
    config = {"configurable": {"thread_id": thread_id}}
    messages = {"messages": [{"role": "user", "content": content}]}
    async for item, metadata in graph.astream(messages, stream_mode="messages", config=config):
        # ... 流式处理（同第7节）
```

### 9.4 可复用的代码

| 现有代码 | 处理方式 |
|---|---|
| `map_data` 工具函数 | 原样迁移到 `agents/map_route_agent.py` |
| `TOOL_LIST` 字典 | 保留原文件 `tool_list.py` |
| `tool.py` MCP 配置 | 不变 |
| `database.py` | 不变（SQLModel 部分），连接池在 main.py lifespan 中 |
| `jwt_create.py` | 不变 |
| `core/` 中间件 | 不变 |
| `models/` 数据模型 | 不变 |

---

## 10. 实施路线与分期

> **进度标记规范**：`[ ]` = 未开始, `[~]` = 进行中, `[x]` = 已完成

### Phase 1：最小可行版本（2-3 天）

**目标**: 拆分三阶段为三个独立 Agent，验证基本流程跑通

| 任务 ID | 任务名称 | 状态 | 修改的文件 | 测试方法 |
|---------|---------|------|-----------|---------|
| P1-01 | 共享状态定义 | [x] | `graph/__init__.py`, `graph/state.py` | `python -c "from graph.state import MultiAgentState"` |
| P1-02 | 工具分组隔离 | [x] | `graph/tool_groups.py` | `python -c "from graph.tool_groups import split_tools"` |
| P1-03 | ResearchAgent 实现 | [x] | `agents/__init__.py`, `agents/research_agent.py`, `prompts/research.txt` | `python -c "from agents.research_agent import research_llm_node"` |
| P1-04 | PlanWriterAgent 实现 | [x] | `agents/plan_writer_agent.py`, `prompts/plan_writer.txt` | `python -c "from agents.plan_writer_agent import plan_writer_llm_node"` |
| P1-05 | MapRouteAgent 实现 | [x] | `agents/map_route_agent.py`, `prompts/map_route.txt` | `python -c "from agents.map_route_agent import map_route_llm_node"` |
| P1-06 | 图结构组装（基础版） | [ ] | `graph/builder.py` | `python -c "from graph.builder import build_multi_agent_graph"` |
| P1-07 | 服务层适配 | [ ] | `services/chat.py` | 手动 WebSocket 测试 |
| P1-08 | 应用入口改造 | [ ] | `main.py` | `uvicorn main:app` 启动无报错 |
| P1-09 | Phase 1 集成验证 | [ ] | 无 | 发送旅游规划请求，三个 Agent 串行执行 |

**依赖关系**: P1-01 → P1-02 → P1-03/P1-04/P1-05（并行）→ P1-06 → P1-07 → P1-08 → P1-09

### Phase 2：Supervisor + 偏好卡（2-3 天）

**目标**: 加入意图分类和偏好收集

| 任务 ID | 任务名称 | 状态 | 修改的文件 | 测试方法 |
|---------|---------|------|-----------|---------|
| P2-01 | SupervisorAgent 实现 | [ ] | `agents/supervisor.py`, `prompts/supervisor.txt` | `python -c "from agents.supervisor import supervisor_node"` |
| P2-02 | PreferenceNode + WeatherStrategy | [ ] | `agents/preference.py` | `python -c "from agents.preference import preference_node"` |
| P2-03 | ChatAgent 实现 | [ ] | `agents/chat_agent.py` | `python -c "from agents.chat_agent import chat_agent_node"` |
| P2-04 | 图结构升级（Supervisor 路由） | [ ] | `graph/builder.py` | 手动测试意图分流 |
| P2-05 | WebSocket 偏好消息处理 | [ ] | `controllers/chat.py`, `services/chat.py` | 手动 WebSocket 测试 preference_submit |
| P2-06 | 偏好验证 Schema | [ ] | `schemas/chat.py` | `python -c "from schemas.chat import PreferenceSubmit"` |
| P2-07 | 前端 PreferenceCard 组件 | [ ] | `pages/chat/component/PreferenceCard.vue` | 前端渲染偏好卡测试 |
| P2-08 | 前端 Store 适配 | [ ] | `store/index.ts` | 接收 preference_card 消息类型 |

**依赖关系**: P2-01 → P2-02/P2-03（并行）→ P2-04 → P2-05/P2-06 → P2-07/P2-08

### Phase 3：并发 + TransportAgent（1-2 天）

**目标**: 加入交通查询和并发执行

| 任务 ID | 任务名称 | 状态 | 修改的文件 | 测试方法 |
|---------|---------|------|-----------|---------|
| P3-01 | TransportAgent 实现 | [ ] | `agents/transport_agent.py`, `prompts/transport.txt` | `python -c "from agents.transport_agent import transport_llm_node"` |
| P3-02 | 并发分叉 + MergeNode | [ ] | `graph/builder.py` | 手动测试并发执行 |
| P3-03 | 去除 Semaphore 串行瓶颈 | [ ] | `graph/builder.py` | 对比并发/串行耗时 |
| P3-04 | 含出发地场景测试 | [ ] | 无 | 发送含出发城市的请求 |
| P3-05 | 无出发地场景测试 | [ ] | 无 | 发送不含出发城市的请求 |

**依赖关系**: P3-01 → P3-02 → P3-03 → P3-04/P3-05

### Phase 4：清理 + 测试（1 天）

**目标**: 清理旧代码，补充测试

| 任务 ID | 任务名称 | 状态 | 修改的文件 | 测试方法 |
|---------|---------|------|-----------|---------|
| P4-01 | 删除旧文件 | [ ] | 删除 `state_graph.py`, `model_prompt.py` | 全量导入无报错 |
| P4-02 | 单元测试补充 | [ ] | `tests/` | `pytest tests/unit/ -v` |
| P4-03 | 集成测试 | [ ] | `tests/` | `pytest tests/integration/ -v` |
| P4-04 | 端到端测试 | [ ] | `tests/` | `pytest tests/e2e/ -v` |

**依赖关系**: P4-01 → P4-02 → P4-03 → P4-04

---

## 11. 场景执行流程示例

### 场景 A：日常闲聊

```
用户: "你好，今天天气怎么样？"
  → Supervisor: intent=chat, reason="寒暄问好"
    → chat_agent: 直接调用 qwen3-max 流式回复
      → 推送 role:assistant "你好！我是你的旅游助手…"
        → 推送 role:end code=200
```

**经过节点**: `supervisor` → `chat_agent` → END  
**LLM 调用**: 2次（Supervisor 1 + ChatAgent 1）  
**工具调用**: 0次

---

### 场景 B：旅游规划（无出发地、近期出发）

```
用户: "帮我规划杭州3日游"
  → Supervisor: intent=travel_plan, destination=杭州, travel_days=3
    → preferences_done=false → PreferenceNode
      → 推送 role:preference_card（偏好卡片）
      → 图中断，等待用户

用户提交偏好: {travelers:"一个人", pace:"特种兵", style:["自然风光","城市漫步"], budget:"节俭", departure:"", travel_date:""}
  → 写入 state, preferences_done=true, transport_done=true（无出发地）
  → 图恢复 → Supervisor（再次进入）
    → preferences_done=true → weather_strategy
      → strategy=realtime（无日期=近期）
        → 并发启动:
          ├── ResearchAgent
          │   → query-weather("杭州")        推送 role:tool "查询天气"
          │   → bailian_web_search("杭州…")   推送 role:tool "搜索景点数据"
          │   → research_done
          └── TransportAgent: 跳过（已标记完成）
        → merge_node（Research完成即放行）
          → PlanWriterAgent
            → search-image("西湖")           推送 role:tool "搜索图片"
            → search-image("灵隐寺")         推送 role:tool "搜索图片"
            → ... 流式输出攻略                推送 role:assistant "🌸3天杭州…"
            → plan_writer_done
              → MapRouteAgent
                → map_data(第一天路线)        推送 role:tool_result {route_polyline}
                → map_data(第二天路线)        推送 role:tool_result {route_polyline}
                → map_data(第三天路线)        推送 role:tool_result {route_polyline}
                  → END                      推送 role:end code=200
```

**经过节点**: supervisor → preference_node → (中断) → supervisor → weather_strategy → research_llm → research_tool → research_done → merge_node → plan_writer_llm → image_tool → plan_writer_done → map_route_llm → map_tool → END  
**LLM 调用**: 约 6-8 次  
**工具调用**: 约 8-12 次

---

### 场景 C：含出发地 + 远期日期

```
用户: "帮我规划五一去西安旅游"
  → Supervisor: intent=travel_plan, destination=西安, travel_days=3
    → PreferenceNode → 偏好卡

用户提交: {departure:"上海", travel_date:"2026-05-01", ...}
  → weather_strategy: delta=61天 > 15天 → strategy=historical
    → 并发启动:
      ├── ResearchAgent
      │   → bailian_web_search("西安五月气候特点 历史天气")  ← 天气降级为搜索
      │   → bailian_web_search("西安景点美食攻略")
      │   → research_done
      └── TransportAgent
          → get-stations-code-in-city("上海")
          → get-stations-code-in-city("西安")
          → get-tickets(上海→西安, 2026-05-01)
          → transport_done
    → merge_node（等待两路都完成）
      → PlanWriterAgent
        → 攻略包含「出行交通」章节 + 天气标注"📅 历史气候参考"
        → plan_writer_done
          → MapRouteAgent → END
```

**经过节点**: 同场景B + transport_check → transport_llm → transport_tool → transport_done  
**LLM 调用**: 约 8-10 次  
**工具调用**: 约 12-16 次  
**性能提升**: Research 和 Transport 并发执行，总耗时 = max(两者) 而非 sum(两者)
