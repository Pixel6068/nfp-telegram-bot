"""
非农(NFP)速报自动化推送
流程: BLS抓数据 → Claude解读 → Telegram推送 → 更新GitHub状态变量
"""

import os
import sys
import time
import requests
from datetime import datetime

# ============ 配置 ============
BLS_API_KEY = os.environ["BLS_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LAST_CPI_STATUS = os.environ.get("LAST_CPI_STATUS", "暂无数据")

REPO = "Pixel6068/nfp-telegram-bot"
CLAUDE_MODEL = "claude-opus-4-7"      # 最新Opus，按你账户实际可用模型替换
TIMEOUT = 30
MAX_RETRIES = 3

# 非农就业相关序列（SA，BLS默认就季调）
SERIES_NFP = "CES0000000001"           # 非农总就业人数（千人）
SERIES_UNEMP = "LNS14000000"           # 失业率 U-3
SERIES_AHE = "CES0500000003"           # 私营部门时薪（美元）


# ============ 1. 数据获取 ============
def fetch_bls(series_ids: list) -> dict:
    """通用BLS抓取函数。"""
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    payload = {
        "seriesid": series_ids,
        "startyear": str(datetime.now().year - 1),
        "endyear": str(datetime.now().year),
        "registrationkey": BLS_API_KEY,
    }
    r = requests.post(url, json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS API 错误: {data.get('message')}")
    return {s["seriesID"]: s for s in data["Results"]["series"]}


def get_nfp_data() -> dict:
    """抓取非农、失业率、时薪三项核心数据。"""
    raw = fetch_bls([SERIES_NFP, SERIES_UNEMP, SERIES_AHE])

    # 非农就业总量（千人）
    nfp_rows = raw[SERIES_NFP]["data"]
    if len(nfp_rows) < 4:
        raise RuntimeError("非农数据
