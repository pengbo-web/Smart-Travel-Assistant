from fastapi import FastAPI
from core.middleware import gloglobal_middleware, validation_exception_handler
from fastapi.exceptions import RequestValidationError
from database import init_db
from contextlib import asynccontextmanager
import os
from fastapi.staticfiles import StaticFiles

# 引入mcp工具
from state_graph import client, tontyi, map_data

# 用户相关的接口
from controllers.user import router as user_router

# 对话相关的接口
from controllers.chat import router as chat_router

# 获取腾讯云语音识别url接口
from controllers.voice import router as voice_router


# 声明周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时
    init_db()
    # 读取mcp工具
    mcp_tools = await client.get_tools()
    # 加入本地 map_data 工具
    all_tools = mcp_tools + [map_data]
    print("执行工具读取-------", all_tools)
    llm_with_tools = tontyi.bind_tools(all_tools)
    # print('模型读取mcp工具----',llm_with_tools)
    tools_by_name = {tool.name: tool for tool in all_tools}
    print("应用启动时执行")
    # 全局缓存
    app.state.tool_cache = {
        "tools_by_name": tools_by_name,
        "llm_with_tools": llm_with_tools,
        "all_tools": all_tools,
    }
    yield
    print("应用关闭时执行")


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
