"""
PreferenceNode + WeatherStrategyNode

PreferenceNode: 向前端推送偏好选项卡片，使用 LangGraph interrupt 等待用户选择
WeatherStrategyNode: 根据出行日期计算天气查询策略（纯 Python 逻辑，不消耗 LLM token）
"""

import json
from datetime import date, datetime

from langchain_core.messages import AIMessage

from graph.state import MultiAgentState


# ────────────────────────────────────────────────────────
# 偏好卡片配置
# ────────────────────────────────────────────────────────

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


# ────────────────────────────────────────────────────────
# PreferenceNode
# ────────────────────────────────────────────────────────


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
    # ⚠️ 此处图执行会自动中断（interrupt_after=["preference_node"]）
    # 用户提交偏好后，通过 graph.update_state() 写入 preferences
    # preferences_done 设为 true，然后 resume 图继续执行


async def handle_preference_submission(preferences: dict) -> dict:
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

    Returns:
        用于 graph.update_state() 的状态更新 dict
    """
    departure = preferences.get("departure", "").strip()
    has_departure = bool(departure)

    return {
        "preferences": preferences,
        "preferences_done": True,
        "transport_done": not has_departure,  # 无出发地 → transport 直接标记完成
        "transport_result": "",
    }


# ────────────────────────────────────────────────────────
# WeatherStrategyNode
# ────────────────────────────────────────────────────────


async def weather_strategy_node(state: MultiAgentState) -> dict:
    """
    纯 Python 逻辑节点，不消耗 LLM token。
    根据出行日期距今天数决定天气查询策略。

    策略:
        - realtime:   7天内 / 未填日期 → 实时天气预报
        - extended:   7-15天 → 近期趋势
        - historical: 超过15天 → 降级为历史气候参考
    """
    travel_date_str = state.get("preferences", {}).get("travel_date", "")
    today = date.today()

    if not travel_date_str:
        strategy = "realtime"
    else:
        try:
            travel_date = datetime.strptime(travel_date_str, "%Y-%m-%d").date()
            delta_days = (travel_date - today).days

            if delta_days <= 7:
                strategy = "realtime"
            elif delta_days <= 15:
                strategy = "extended"
            else:
                strategy = "historical"
        except ValueError:
            strategy = "realtime"  # 日期格式异常，兜底

    return {"weather_strategy": strategy}
