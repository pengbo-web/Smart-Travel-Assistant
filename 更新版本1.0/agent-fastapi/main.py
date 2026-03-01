from fastapi import FastAPI
from core.middleware import gloglobal_middleware, validation_exception_handler
from fastapi.exceptions import RequestValidationError
from database import init_db
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles

load_dotenv()

# ── Multi-Agent 依赖 ──
from tool import client
from graph.tool_groups import split_tools
from agents.map_route_agent import map_data
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore

DB_URI = str(os.getenv("DB_URI"))

# 用户相关的接口
from controllers.user import router as user_router

# 对话相关的接口
from controllers.chat import router as chat_router

# 获取腾讯云语音识别url接口
from controllers.voice import router as voice_router


# ── 生命周期管理（Multi-Agent 版） ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化数据库
    init_db()

    # 读取 MCP 远程工具 + 本地 map_data 工具
    mcp_tools = await client.get_tools()
    all_tools = mcp_tools + [map_data]
    print(f"[启动] 加载工具 {len(all_tools)} 个:", [t.name for t in all_tools])

    # 工具按职责分组
    tool_groups = split_tools(all_tools)
    print(f"[启动] 工具分组: {list(tool_groups.keys())}")

    # 全局 PostgreSQL 连接池（生命周期与应用一致）
    async with (
        AsyncPostgresStore.from_conn_string(DB_URI) as store,
        AsyncPostgresSaver.from_conn_string(DB_URI) as checkpointer,
    ):
        await store.setup()
        await checkpointer.setup()
        print("[启动] PostgreSQL checkpointer/store 就绪")

        # ★ 统一挂载到 app.state，供 services / controllers 使用
        app.state.graph_deps = {
            "tool_groups": tool_groups,
            "checkpointer": checkpointer,
            "store": store,
        }
        print("[启动] Multi-Agent 应用就绪")
        yield

    print("[关闭] PostgreSQL 连接池已释放")


app = FastAPI(lifespan=lifespan)

# 全局注册异常处理中间件
app.middleware("http")(gloglobal_middleware)
# 注册全局参数校验器
app.add_exception_handler(RequestValidationError, validation_exception_handler)
# 配置静态文件访问
image_folder = os.path.join(os.getcwd(), "image")
os.makedirs(image_folder, exist_ok=True)
app.mount("/image", StaticFiles(directory=image_folder))
# ------------------接口-------------------
"""
include_router
把某个路由模块（Router）注册到主应用（app）中。
相当于告诉 FastAPI：请把这个子路由挂进主路由系统里。
"""
app.include_router(user_router)
app.include_router(chat_router)
app.include_router(voice_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app="main:app",
        host="127.0.0.1",
        port=4000,
        reload=True,
    )
