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
    prompt = f"""【系统设定】
你是一位华尔街顶级的宏观策略分析师。根据最新美国宏观数据，为高净值客户撰写市场异动速报。语言专业、犀利、客观，直击资金流向本质。

【今日最新数据触发】
数据类型：美国非农就业数据
报告期：{nfp['period']}
实际新增就业：{nfp['change']}千人（就业总人数：{nfp['value']}千人）

【宏观背景记忆】
最近一次CPI通胀数据状态：{LAST_CPI_STATUS}

【客户持仓】
核心重仓：GOOGL, NVDA, TSLA, BN (Brookfield)
高弹性卫星仓位：ALAB, PLTR, HOOD, SMIC, 软银ADR

请严格按以下结构输出（400字以内）：

1️⃣ **宏观定调与美联储路径**
本次数据冷热判断？超预期/不及预期？美联储下次议息大概率动作？十年期美债方向？

2️⃣ **板块资金轮动路线图**
资金最可能涌入的1-2个板块（一句话逻辑）
资金最可能抽离的1-2个板块（一句话逻辑）

3️⃣ **专属持仓影响与操作建议**
针对以上核心仓位和卫星仓位的针对性分析与风险提示"""

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
