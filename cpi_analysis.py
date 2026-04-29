import requests, os
from datetime import datetime

BLS_API_KEY = os.environ["BLS_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LAST_NFP_STATUS = os.environ.get("LAST_NFP_STATUS", "暂无数据")
REPO = "Pixel6068/nfp-telegram-bot"

def get_cpi_data():
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    payload = {
        "seriesid": ["CUUR0000SA0", "CUUR0000SA0L1E"],
        "startyear": str(datetime.now().year - 1),
        "endyear": str(datetime.now().year),
        "registrationkey": BLS_API_KEY
    }
    r = requests.post(url, json=payload)
    result = {}
    for series in r.json()["Results"]["series"]:
        sid = series["seriesID"]
        latest = series["data"][0]
        prev = series["data"][1]
        change = round(float(latest["value"]) - float(prev["value"]), 3)
        pct = round(change / float(prev["value"]) * 100, 2)
        result[sid] = {
            "period": latest["periodName"] + " " + latest["year"],
            "value": latest["value"],
            "change": change,
            "pct": pct
        }
    return result

def update_github_variable(name, value):
    url = f"https://api.github.com/repos/{REPO}/actions/variables/{name}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    r = requests.patch(url, headers=headers, json={"name": name, "value": value})
    print(f"更新变量 {name}：", r.status_code)

def claude_interpret(data):
    cpi = data["CUUR0000SA0"]
    core = data["CUUR0000SA0L1E"]
prompt = f"""你是华尔街对冲基金宏观交易台首席策略师。CPI刚发布，3分钟内给PM和交易台发可交易信号。

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

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json={
        "model": "claude-opus-4-5",
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}]
    })
    result = r.json()
    if "content" not in result:
        raise Exception(f"Claude API 错误: {result}")
    return result["content"][0]["text"]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    })
    print("Telegram 返回：", r.json())

if __name__ == "__main__":
    print("开始运行...")
    data = get_cpi_data()
    cpi = data["CUUR0000SA0"]
    core = data["CUUR0000SA0L1E"]
    analysis = claude_interpret(data)
    msg = (
        f"🌡️ *CPI通胀速报 ({cpi['period']})*\n"
        f"总体CPI：{cpi['value']}（环比 {cpi['pct']}%）\n"
        f"核心CPI：{core['value']}（环比 {core['pct']}%）\n"
        f"📌 非农背景：{LAST_NFP_STATUS}\n\n"
        f"{analysis}"
    )
    send_telegram(msg)
    cpi_status = f"{cpi['period']} 总体CPI环比{cpi['pct']}%，核心CPI环比{core['pct']}%"
    update_github_variable("LAST_CPI_STATUS", cpi_status)
    print("推送完成，状态已更新")
