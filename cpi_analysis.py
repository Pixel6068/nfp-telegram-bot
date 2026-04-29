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
    prompt = f"""你是一位对冲基金的宏观交易员，不写报告，只给交易台发信号。语言精炼，直接给结论，禁止废话和套话。

【本次触发数据】
总体CPI环比：{cpi['pct']}%（指数：{cpi['value']}）
核心CPI环比：{core['pct']}%（指数：{core['value']}）
报告期：{cpi['period']}

【背景记忆】
上期非农状态：{LAST_NFP_STATUS}

请按以下格式输出，每项不超过2行：

📍 数据定性
总体vs核心的分歧说明什么（供给冲击还是需求驱动）？叠加非农背景，当前处于哪个宏观象限？

🏦 美联储信号
下次议息最大概率动作？10年美债方向？

🔄 板块轮动（只写最确定的）
买入方向：[板块名] — 1句逻辑
卖出方向：[板块名] — 1句逻辑

⚡ 本周必要动作
3条以内，具体到"加/减/观望+资产类别"，不提个股"""

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
