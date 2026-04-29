import requests, os
from datetime import datetime

BLS_API_KEY = os.environ["BLS_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

def get_cpi_data():
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    payload = {
        "seriesid": [
            "CUUR0000SA0",    # CPI 总体
            "CUUR0000SA0L1E", # 核心CPI（剔除食品和能源）
        ],
        "startyear": str(datetime.now().year - 1),
        "endyear": str(datetime.now().year),
        "registrationkey": BLS_API_KEY
    }
    r = requests.post(url, json=payload)
    print("BLS 返回状态：", r.json()["status"])

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

def claude_interpret(data):
    cpi = data["CUUR0000SA0"]
    core = data["CUUR0000SA0L1E"]

    prompt = f"""以下是美国最新CPI通胀数据：

【CPI 总体指数】
- 报告期：{cpi['period']}
- 指数值：{cpi['value']}
- 环比变化：{cpi['change']}（{cpi['pct']}%）

【核心CPI（剔除食品和能源）】
- 报告期：{core['period']}
- 指数值：{core['value']}
- 环比变化：{core['change']}（{core['pct']}%）

请用中文综合分析（400字以内），重点回答：
1. 通胀是升温还是降温，趋势如何
2. 核心CPI与总体CPI的差异说明什么
3. 美联储对此的可能反应（降息/加息/维持）
4. 对持有美股投资者的实际影响和操作建议"""

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    payload = {
        "model": "claude-opus-4-5",
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}]
    }
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
    result = r.json()
    print("Claude 返回：", result)
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
    print("CPI数据获取完成：", data)
    analysis = claude_interpret(data)
    print("Claude 解读完成")

    cpi = data["CUUR0000SA0"]
    core = data["CUUR0000SA0L1E"]
    msg = (
        f"🌡️ *美国CPI通胀数据解读*\n\n"
        f"📊 *总体CPI ({cpi['period']})*：{cpi['value']}，环比 {cpi['pct']}%\n"
        f"🔵 *核心CPI ({core['period']})*：{core['value']}，环比 {core['pct']}%\n\n"
        f"{analysis}"
    )
    send_telegram(msg)
    print("推送成功")
