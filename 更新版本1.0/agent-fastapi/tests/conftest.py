"""
全局测试配置

- 设置 asyncio 模式
- 提供通用 fixtures
"""

import pytest


@pytest.fixture
def sample_preferences() -> dict:
    """标准偏好数据 fixture"""
    return {
        "travelers": "情侣",
        "pace": "舒适游",
        "style": ["自然风光", "历史文化"],
        "budget": "灵活",
        "departure": "上海",
        "travel_date": "2026-05-01",
    }


@pytest.fixture
def minimal_preferences() -> dict:
    """最小偏好数据 fixture（无出发地、无日期）"""
    return {
        "travelers": "一个人",
        "pace": "特种兵",
        "style": ["城市漫步"],
        "budget": "节俭",
        "departure": "",
        "travel_date": "",
    }
