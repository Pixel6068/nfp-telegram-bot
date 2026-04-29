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
    prompt = f"""你是一位对冲基金的宏观交易员，不写报告，只给交易台发信号。语言精炼，直接给结论，禁止废话和套话。

【本次触发数据】
非农新增就业：{nfp['change']}千人（就业总量：{nfp['value']}千人）
报告期：{nfp['period']}

【背景记忆】
上期CPI状态：{LAST_CPI_STATUS}

请按以下格式输出，每项不超过2行：

📍 数据定性
冷/热/符合预期？与上期CPI叠加后，宏观环境是"滞胀/过热/软着陆/衰退"哪个象限？

🏦 美联储信号
下次议息最大概率动作（降/加/按兵）？10年美债方向？

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
