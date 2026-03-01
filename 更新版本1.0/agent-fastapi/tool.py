# 连接第三方mcp工具
from langchain_mcp_adapters.client import MultiServerMCPClient  # type: ignore
import os
from dotenv import load_dotenv

load_dotenv()

# 解决代理拦截 SSE post_writer 连接问题，强制直连阿里云
os.environ.setdefault("NO_PROXY", "dashscope.aliyuncs.com,ai.weiniai.cn")
os.environ.setdefault("no_proxy", "dashscope.aliyuncs.com,ai.weiniai.cn")

API_KEY = os.getenv("API_KEY")
APPCODE = os.getenv("APPCODE")

client = MultiServerMCPClient(
    {
        # 联网搜索
        "WebSearch": {
            "url": "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/sse",
            "headers": {"Authorization": f"Bearer {API_KEY}"},
            "transport": "sse",
        },
        # 高德地图
        "AmapMaps": {
            "url": "https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/sse",
            "headers": {"Authorization": f"Bearer {API_KEY}"},
            "transport": "sse",
        },
        # 12306火车票查询
        "ChinaRailway": {
            "url": "https://dashscope.aliyuncs.com/api/v1/mcps/china-railway/sse",
            "headers": {"Authorization": f"Bearer {API_KEY}"},
            "transport": "sse",
        },

        # 查询天气
        "ZuimeiGetWeather": {
            "url": "https://dashscope.aliyuncs.com/api/v1/mcps/zuimei-getweather/sse",
            "headers": {"Authorization": f"Bearer {API_KEY}"},
            "transport": "sse",
        },

        # "geng-weather": {
        #     "url": "https://ai.weiniai.cn/weather",
        #     "transport": "streamable_http",
        #     "headers": {"Authorization": f"Bearer {APPCODE}"},
        # },
        # 搜索图片
        "geng-search-image": {
            "url": "https://ai.weiniai.cn/search-image",
            "transport": "streamable_http",
            "headers": {"Authorization": f"Bearer {APPCODE}"},
        },
    }
)
