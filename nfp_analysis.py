import requests, os
from datetime import datetime

BLS_API_KEY = os.environ["BLS_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

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

def gemini_interpret(data):
    prompt = f"""
    美国非农就业数据刚刚公布：
    - 报告期：{data['period']}
    - 非农就业人数：{data['value']} 千人
    - 环比变化：{data['change']} 千人
    
    请用中文从以下角度简洁解读（300字内）：
    1. 数据强弱判断（与市场预期对比）
    2. 对美联储货币政策的影响
    3. 对美股、美元指数的短期影响方向
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown"
    })

if __name__ == "__main__":
    data = get_nfp_data()
    analysis = gemini_interpret(data)
    msg = f"📊 *美国非农就业数据解读*\n\n{analysis}"
    send_telegram(msg)
    print("推送成功")
