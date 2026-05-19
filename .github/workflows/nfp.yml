"""
CPI 通胀速报自动化推送
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
LAST_NFP_STATUS = os.environ.get("LAST_NFP_STATUS", "暂无数据")

REPO = "Pixel6068/nfp-telegram-bot"
CLAUDE_MODEL = "claude-opus-4-7"      # 最新Opus，按你账户实际可用模型替换
TIMEOUT = 30
MAX_RETRIES = 3

SERIES_HEADLINE = "CUUR0000SA0"        # 总体CPI（NSA）
SERIES_CORE = "CUUR0000SA0L1E"         # 核心CPI（NSA）


# ============ 1. 数据获取 ============
def get_cpi_data() -> dict:
    """从BLS抓取最新CPI数据。"""
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    payload = {
        "seriesid": [SERIES_HEADLINE, SERIES_CORE],
        "startyear": str(datetime.now().year - 1),
        "endyear": str(datetime.now().year),
        "registrationkey": BLS_API_KEY,
    }
    r = requests.post(url, json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()

    if data.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS API 错误: {data.get('message')}")

    result = {}
    for series in data["Results"]["series"]:
        sid = series["seriesID"]
        rows = series.get("data", [])
        if len(rows) < 2:
            raise RuntimeError(f"序列 {sid} 数据不足")

        latest, prev = rows[0], rows[1]
        latest_v, prev_v = float(latest["value"]), float(prev["value"])
        change = round(latest_v - prev_v, 3)
        pct = round(change / prev_v * 100, 2)

        result[sid] = {
            "period": f"{latest['periodName']} {latest['year']}",
            "value": latest["value"],
            "change": change,
            "pct": pct,
        }
    return result


# ============ 2. Claude 解读 ============
def build_cpi_prompt(cpi: dict, core: dict) -> str:
    return f"""你是华尔街对冲基金宏观交易台首席策略师。CPI刚发布，3分钟内给PM和交易台发可交易信号。

【铁律】
- 禁用"可能/或许/建议关注/值得留意"等模糊词，每句必须给方向
- 禁止任何免责声明和风险提示套话
- 每个板块结论必须给ETF代码（XLK/XLF/XLE/XLU/XLRE/XLP/XLY/XLI/XLB/XLV/KRE/IWM/QQQ/TLT/IEF/GLD/UUP/USO 任选）
- 美债、美元、油价等必须给具体目标位（如"10Y破4.5%"）

【触发数据】
总体CPI环比：{cpi['pct']}%（指数{cpi['value']}）
核心CPI环比：{core['pct']}%（指数{core['value']}）
报告期：{cpi['period']}

【交易基准线】
- 总体环比0.2%/核心0.2%是市场中性线
- 0.3%以上=偏热（粘性），0.1%及以下=偏冷（松动）
- 总体>核心：能源/食品扰动主导，可能短期；核心>总体：服务粘性，Fed最忌讳
- 上期非农定性：{LAST_NFP_STATUS}

按以下结构输出，整体不超过450字：

🎯 一句话信号
通胀【粘住/松动/反弹/失控】→ 风险资产【利好/利空/分化】→ 宏观象限【过热/滞胀/软着陆/再加速】

📊 数据定性（2行）
本次环比vs中性线0.2%偏离方向；总体vs核心分歧含义（服务粘性 / 商品松动 / 能源扰动 / 同步）；叠加上期非农，当前处于哪个象限。

🏦 美联储反应函数（2行）
下次FOMC动作：【降25bp/降50bp/按兵/暂停降息周期】（必须明确选一，不许模棱两可）
10Y美债目标位X.XX%（方向+幅度）；DXY 偏强突破X / 偏弱回落X；2s10s 陡峭/平坦化

📈 做多清单（按确定性排序，3个以内，每行≤15字）
1. [ETF代码] — 逻辑
2. [ETF代码] — 逻辑
3. [ETF代码] — 逻辑

📉 做空/减持清单（2个以内）
1. [ETF代码] — 逻辑
2. [ETF代码] — 逻辑

⚡ 今夜到下次NFP的3条动作
格式：[加仓/减仓/对冲/观望] + [资产代码] + [触发价位或时间窗口]
1. …
2. …
3. …

❌ 信号失效线
若 SPX 跌破X / 10Y 破X / VIX 升破X，立即反向操作。

记住：你是发信号的人，不是写研报的。给方向、给位置、不给废话。"""


def claude_interpret(data: dict) -> str:
    """调用Claude解读，带指数退避重试。"""
    cpi = data[SERIES_HEADLINE]
    core = data[SERIES_CORE]
    prompt = build_cpi_prompt(cpi, core)

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
    }

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body,
                timeout=TIMEOUT * 2,
            )
            r.raise_for_status()
            result = r.json()
            if result.get("content"):
                return result["content"][0]["text"]
            raise RuntimeError(f"响应异常: {result}")
        except Exception as e:
            last_err = e
            print(f"Claude API 第{attempt}次失败: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)

    raise RuntimeError(f"Claude API 重试{MAX_RETRIES}次仍失败: {last_err}")


# ============ 3. Telegram 推送 ============
def send_telegram(text: str) -> None:
    """先试Markdown，失败回退纯文本（避免特殊字符卡住推送）。"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=TIMEOUT)
    if r.ok:
        print("Telegram 推送成功 (Markdown)")
        return

    print(f"Markdown 失败: {r.text} → 回退纯文本")
    payload.pop("parse_mode")
    r = requests.post(url, json=payload, timeout=TIMEOUT)
    if r.ok:
        print("Telegram 推送成功 (纯文本)")
        return

    raise RuntimeError(f"Telegram 推送失败: {r.text}")


# ============ 4. GitHub 状态变量 ============
def update_github_variable(name: str, value: str) -> None:
    url = f"https://api.github.com/repos/{REPO}/actions/variables/{name}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    r = requests.patch(url, headers=headers, json={"name": name, "value": value}, timeout=TIMEOUT)
    print(f"更新变量 {name}: HTTP {r.status_code}")
    if not r.ok:
        print(f"  响应: {r.text}")


# ============ 主流程 ============
def main() -> int:
    print("=" * 50)
    print(f"CPI 速报启动 @ {datetime.now().isoformat()}")
    print("=" * 50)

    try:
        print("\n[1/4] 抓取 BLS 数据...")
        data = get_cpi_data()
        cpi, core = data[SERIES_HEADLINE], data[SERIES_CORE]
        print(f"  报告期: {cpi['period']}")
        print(f"  总体CPI环比 {cpi['pct']}% | 核心CPI环比 {core['pct']}%")

        print("\n[2/4] 调用 Claude 解读...")
        analysis = claude_interpret(data)
        print(f"  解读完成 ({len(analysis)} 字)")

        print("\n[3/4] 推送 Telegram...")
        msg = (
            f"🌡️ *CPI通胀速报 ({cpi['period']})*\n"
            f"总体CPI：{cpi['value']}（环比 {cpi['pct']}%）\n"
            f"核心CPI：{core['value']}（环比 {core['pct']}%）\n"
            f"📌 非农背景：{LAST_NFP_STATUS}\n\n"
            f"{analysis}"
        )
        send_telegram(msg)

        print("\n[4/4] 更新状态变量...")
        cpi_status = f"{cpi['period']} 总体CPI环比{cpi['pct']}%，核心CPI环比{core['pct']}%"
        update_github_variable("LAST_CPI_STATUS", cpi_status)

        print("\n✅ 全部完成")
        return 0

    except Exception as e:
        print(f"\n❌ 任务失败: {type(e).__name__}: {e}")
        # 失败也推一条告警，避免静默
        try:
            send_telegram(f"⚠️ CPI速报任务失败\n{type(e).__name__}: {str(e)[:500]}")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
