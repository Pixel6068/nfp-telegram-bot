import requests, os
from datetime import datetime

BLS_API_KEY = os.environ["BLS_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
LAST_CPI_STATUS = os.environ.get("LAST_CPI_STATUS", "暂无数据")
REPO = "Pixel6068/nfp-telegram-bot"

def get_nfp_data():
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    payload = {
        "seriesid": ["CES0000000001"],
        "startyear": str(datetime.now().year - 1),
        "endyear": str(datetime.now().year),
        "registrationkey": BLS_API_KEY
    }
    r = requests.post(url, json=payload)
    series = r.json()["Results"]["series"][0]["data"]
    latest = series[0]
    prev = series[1]
    change = round(float(latest["value"]) - float(prev["value"]), 1)
    return {
        "period": latest["periodName"] + " " + latest["year"],
        "value": latest["value"],
        "change": change
    }

def update_github_variable(name, value):
    url = f"https://api.github.com/repos/{REPO}/actions/variables/{name}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
    r = requests.patch(url, headers=headers, json={"name": name, "value": value})
    print(f"更新变量 {name}：", r.status_code)

def claude_interpret(nfp):
prompt = f"""你是华尔街对冲基金宏观交易台首席策略师。非农刚发布，3分钟内给PM和交易台发可交易信号。

【铁律】
- 禁用"可能/或许/建议关注"等模糊词，每句必须给方向
- 禁止任何免责声明和风险提示套话
- 每个板块结论必须给ETF代码（XLF/KRE/XLI/XLY/XLP/XLU/XLRE/XLE/IWM/QQQ/TLT/IEF/GLD/UUP 任选）
- 美债、美元给具体目标位

【触发数据】
非农新增：{nfp['change']}千人
就业总量：{nfp['value']}千人
报告期：{nfp['period']}

【交易基准线】
- 15万是劳动力市场荣枯线
- ≥25万=过热（Fed鹰派强化）；15-25万=温和扩张（金发姑娘）
- 5-15万=明显降温（Fed鸽派强化）；<5万或负值=衰退预警（避险模式）
- 上期CPI定性：{LAST_CPI_STATUS}

按以下结构输出，整体不超过450字：

🎯 一句话信号
就业【过热/温和/降温/坍塌】→ Fed鸽派交易【强化/弱化/反转】→ 风险资产【利好/利空/分化】→ 宏观象限【金发姑娘/再通胀/软着陆/硬着陆】

📊 数据定性（2行）
本次新增vs荣枯线15万的偏离与速率；叠加上期CPI，当前是【金发姑娘/再通胀/政策两难/衰退预警】哪个组合。

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
    nfp = get_nfp_data()
    print("非农数据：", nfp)
    analysis = claude_interpret(nfp)
    msg = (
        f"🧑‍💼 *非农就业速报 ({nfp['period']})*\n"
        f"新增就业：+{nfp['change']}千人 | 总人数：{nfp['value']}千人\n"
        f"📌 CPI背景：{LAST_CPI_STATUS}\n\n"
        f"{analysis}"
    )
    send_telegram(msg)
    nfp_status = f"{nfp['period']} 非农新增{nfp['change']}千人"
    update_github_variable("LAST_NFP_STATUS", nfp_status)
    print("推送完成，状态已更新")
