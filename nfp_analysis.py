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
        raise RuntimeError("非农数据行数不足")
    latest = nfp_rows[0]
    prev = nfp_rows[1]
    prev2 = nfp_rows[2]   # 用于看上上月修正
    prev3 = nfp_rows[3]   # 用于看上上上月

    nfp_value = float(latest["value"])
    nfp_change = round(nfp_value - float(prev["value"]), 1)        # 本月新增（千人）
    prev_change = round(float(prev["value"]) - float(prev2["value"]), 1)
    prev2_change = round(float(prev2["value"]) - float(prev3["value"]), 1)

    # 失业率
    unemp_rows = raw[SERIES_UNEMP]["data"]
    unemp_latest = float(unemp_rows[0]["value"])
    unemp_prev = float(unemp_rows[1]["value"])
    unemp_change = round(unemp_latest - unemp_prev, 2)

    # 时薪 (Average Hourly Earnings)
    ahe_rows = raw[SERIES_AHE]["data"]
    ahe_latest = float(ahe_rows[0]["value"])
    ahe_prev = float(ahe_rows[1]["value"])
    ahe_mom = round((ahe_latest - ahe_prev) / ahe_prev * 100, 2)
    # 同比时薪
    if len(ahe_rows) >= 13:
        ahe_yoy_base = float(ahe_rows[12]["value"])
        ahe_yoy = round((ahe_latest - ahe_yoy_base) / ahe_yoy_base * 100, 2)
    else:
        ahe_yoy = None

    return {
        "period": f"{latest['periodName']} {latest['year']}",
        "nfp_value": nfp_value,
        "nfp_change": nfp_change,
        "prev_change": prev_change,
        "prev2_change": prev2_change,
        "unemp_rate": unemp_latest,
        "unemp_change": unemp_change,
        "ahe_value": ahe_latest,
        "ahe_mom": ahe_mom,
        "ahe_yoy": ahe_yoy,
    }


# ============ 2. Claude 解读 ============
def build_nfp_prompt(d: dict) -> str:
    ahe_yoy_str = f"{d['ahe_yoy']}%" if d['ahe_yoy'] is not None else "N/A"
    return f"""你是华尔街对冲基金宏观交易台首席策略师。非农刚发布，3分钟内给PM和交易台发可交易信号。

【铁律】
- 禁用"可能/或许/建议关注"等模糊词，每句必须给方向
- 禁止任何免责声明和风险提示套话
- 每个板块结论必须给ETF代码（XLF/KRE/XLI/XLY/XLP/XLU/XLRE/XLE/IWM/QQQ/TLT/IEF/GLD/UUP 任选）
- 美债、美元给具体目标位

【触发数据】
非农新增：{d['nfp_change']}千人
就业总量：{d['nfp_value']}千人
失业率 U-3：{d['unemp_rate']}%（变动 {d['unemp_change']}pp）
时薪环比：{d['ahe_mom']}% / 同比：{ahe_yoy_str}
近3个月新增节奏：本月{d['nfp_change']} → 上月{d['prev_change']} → 上上月{d['prev2_change']}
报告期：{d['period']}

【交易基准线】
- 新增就业：≥25万=过热（鹰派强化）；15-25万=温和（金发姑娘）；5-15万=明显降温（鸽派强化）；<5万或负=衰退预警
- 失业率：>4.3%且仍升 = Sahm Rule警报（衰退信号）
- 时薪环比：>0.4%=工资通胀粘性（Fed最忌讳）；<0.2%=工资压力释放
- 修正方向：近2-3个月连续下修=趋势恶化；连续上修=趋势好于看到的
- 上期CPI定性：{LAST_CPI_STATUS}

按以下结构输出，整体不超过450字：

🎯 一句话信号
就业【过热/温和/降温/坍塌】→ Fed鸽派交易【强化/弱化/反转】→ 风险资产【利好/利空/分化】→ 宏观象限【金发姑娘/再通胀/软着陆/硬着陆】

📊 数据定性（2行）
本次新增vs荣枯线15万的偏离与速率；时薪是否仍粘性；近3月节奏是恶化还是改善；叠加上期CPI，当前是【金发姑娘/再通胀/政策两难/衰退预警】哪个组合。

🏦 美联储反应函数（2行）
下次FOMC动作：【降25bp/降50bp/按兵/暂停降息周期】（必须明确选一）
10Y美债目标位X.XX%（方向+幅度）；DXY 偏强X / 偏弱X；2s10s 陡峭/平坦化

📈 做多清单（按确定性排序，3个以内，每行≤15字）
1. [ETF代码] — 逻辑
2. [ETF代码] — 逻辑
3. [ETF代码] — 逻辑

📉 做空/减持清单（2个以内）
1. [ETF代码] — 逻辑
2. [ETF代码] — 逻辑

⚡ 未来1-2周3条具体动作
格式：[加仓/减仓/对冲/观望] + [资产代码] + [触发价位或时间窗口]
1. …
2. …
3. …

❌ 信号失效线
若 10Y 破X / DXY 破X / SPX 跌破X，立即反向操作。

记住：你是发信号的人，不是写研报的。给方向、给位置、不给废话。"""


def claude_interpret(d: dict) -> str:
    """调用Claude解读，带指数退避重试。"""
    prompt = build_nfp_prompt(d)

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
    """先试Markdown，失败回退纯文本。"""
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
    print(f"非农速报启动 @ {datetime.now().isoformat()}")
    print("=" * 50)

    try:
        print("\n[1/4] 抓取 BLS 数据...")
        d = get_nfp_data()
        print(f"  报告期: {d['period']}")
        print(f"  非农新增 {d['nfp_change']}千 | 失业率 {d['unemp_rate']}% | 时薪环比 {d['ahe_mom']}%")
        print(f"  近3月节奏: {d['nfp_change']} → {d['prev_change']} → {d['prev2_change']}")

        print("\n[2/4] 调用 Claude 解读...")
        analysis = claude_interpret(d)
        print(f"  解读完成 ({len(analysis)} 字)")

        print("\n[3/4] 推送 Telegram...")
        ahe_yoy_str = f"{d['ahe_yoy']}%" if d['ahe_yoy'] is not None else "N/A"
        msg = (
            f"💼 *非农就业速报 ({d['period']})*\n"
            f"新增就业：{d['nfp_change']}千人\n"
            f"失业率：{d['unemp_rate']}%（{'+' if d['unemp_change']>=0 else ''}{d['unemp_change']}pp）\n"
            f"时薪：环比 {d['ahe_mom']}% / 同比 {ahe_yoy_str}\n"
            f"近3月：{d['nfp_change']} → {d['prev_change']} → {d['prev2_change']}\n"
            f"📌 CPI背景：{LAST_CPI_STATUS}\n\n"
            f"{analysis}"
        )
        send_telegram(msg)

        print("\n[4/4] 更新状态变量...")
        nfp_status = (
            f"{d['period']} 非农新增{d['nfp_change']}千，"
            f"失业率{d['unemp_rate']}%，时薪环比{d['ahe_mom']}%"
        )
        update_github_variable("LAST_NFP_STATUS", nfp_status)

        print("\n✅ 全部完成")
        return 0

    except Exception as e:
        print(f"\n❌ 任务失败: {type(e).__name__}: {e}")
        try:
            send_telegram(f"⚠️ 非农速报任务失败\n{type(e).__name__}: {str(e)[:500]}")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
