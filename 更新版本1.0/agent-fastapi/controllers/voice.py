# 腾讯云实时语音识别
import base64
import hashlib
import hmac
import time
from fastapi import APIRouter, Depends
import urllib
import urllib.parse
from core.response import response
from uuid import uuid4
import os
from dotenv import load_dotenv

from jwt_create import get_current_user

router = APIRouter(prefix="/voice", tags=["实时语音识别"])
load_dotenv()
APPID = os.getenv("TENCENT_APPID")
SECRETID = os.getenv("TENCENT_SECRETID")
SECRETKEY = str(os.getenv("TENCENT_SECRETKEY"))

# 腾讯云 ASR 域名常量
HOST = "asr.cloud.tencent.com"


# 生成签名
def generate_signature(params: dict[str, str | int | None]) -> str:
    # 1. 按字典序排序
    sorted_items = sorted(params.items(), key=lambda x: x[0])  # type: ignore

    # 2. 拼接为 key=value&key=value
    query_str = "&".join([f"{k}={v}" for k, v in sorted_items])

    # 3. 拼接签名原文（不含协议部分）
    sign_str = f"{HOST}/asr/v2/{APPID}?{query_str}"

    # 4. HMAC-SHA1 计算签名
    hmacsha1 = hmac.new(
        SECRETKEY.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha1
    ).digest()

    # 5. Base64 encode
    signature = base64.b64encode(hmacsha1).decode("utf-8")

    # 6. URL encode（必须）
    return urllib.parse.quote(signature, safe="")


# 返回腾讯云url
@router.get("/ws-url")
async def get_asr_ws_url(user_id: str = Depends(get_current_user)):
    timestamp = int(time.time())
    expired = timestamp + 60  # URL 60 秒有效
    nonce = int(time.time() * 1000)
    voice_id = str(uuid4())
    # 握手阶段所需参数
    params = {
        "engine_model_type": "16k_zh",
        "voice_id": voice_id,
        "secretid": SECRETID,
        "timestamp": timestamp,
        "expired": expired,
        "nonce": nonce,
        "voice_format": 1,
        "needvad": 1,
    }
    # 生成 signature
    signature = generate_signature(params)
    # 拼接最终 URL
    params["signature"] = signature
    query = "&".join([f"{k}={v}" for k, v in params.items()])

    ws_url = f"wss://{HOST}/asr/v2/{APPID}?{query}"
    return response(ws_url)
