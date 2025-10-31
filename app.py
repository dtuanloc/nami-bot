# app.py
import os
import time
import hmac
import hashlib
import requests
import threading
from flask import Flask, request, jsonify, abort

app = Flask(__name__)

API_KEY = os.getenv("NAMI_API_KEY")
API_SECRET = os.getenv("NAMI_API_SECRET")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "change_me_secret")
BASE_URL = "https://nami.exchange/api/v4"
SYMBOL = "BTC_USDT"  # Cặp coin muốn trade
BUY_PRICE = 30000.0
SELL_PRICE = 32000.0
QTY = 0.001

RUN_LOOP = {"running": False}
LOCK = threading.Lock()


def nami_sign(timestamp: str, method: str, path: str, body: str) -> str:
    message = f"{timestamp}{method}{path}{body}"
    return hmac.new(API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()


def nami_headers(method, path, body=""):
    timestamp = str(int(time.time() * 1000))
    signature = nami_sign(timestamp, method, path, body)
    return {
        "X-API-KEY": API_KEY,
        "X-API-SIGN": signature,
        "X-API-TIMESTAMP": timestamp,
        "Content-Type": "application/json"
    }


def get_price(symbol):
    url = f"{BASE_URL}/market/ticker?symbol={symbol}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return float(r.json()["data"]["lastPrice"])


def place_order(side, symbol, qty):
    path = "/order"
    url = BASE_URL + path
    body_dict = {
        "symbol": symbol,
        "side": side,
        "type": "MARKET",
        "quantity": str(qty)
    }
    import json
    body_json = json.dumps(body_dict)
    headers = nami_headers("POST", path, body_json)
    r = requests.post(url, data=body_json, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()


def bot_loop():
    print("🚀 Bot started")
    while True:
        with LOCK:
            running = RUN_LOOP["running"]
        if running:
            try:
                price = get_price(SYMBOL)
                print(time.strftime("%H:%M:%S"), SYMBOL, price)
                if price <= BUY_PRICE:
                    print("🟢 Mua vào")
                    res = place_order("BUY", SYMBOL, QTY)
                    print(res)
                elif price >= SELL_PRICE:
                    print("🔴 Bán ra")
                    res = place_order("SELL", SYMBOL, QTY)
                    print(res)
            except Exception as e:
                print("Error:", e)
        time.sleep(10)


threading.Thread(target=bot_loop, daemon=True).start()


def auth(req):
    return req.headers.get("Authorization") == f"Bearer {WEBHOOK_TOKEN}"


@app.route("/trigger", methods=["POST"])
def trigger():
    if not auth(request):
        abort(401)
    price = get_price(SYMBOL)
    return jsonify({"ok": True, "price": price})


@app.route("/start", methods=["POST"])
def start():
    if not auth(request):
        abort(401)
    with LOCK:
        RUN_LOOP["running"] = True
    return jsonify({"ok": True, "running": True})


@app.route("/stop", methods=["POST"])
def stop():
    if not auth(request):
        abort(401)
    with LOCK:
        RUN_LOOP["running"] = False
    return jsonify({"ok": True, "running": False})


@app.route("/status", methods=["GET"])
def status():
    return jsonify({"running": RUN_LOOP["running"]})


@app.route("/")
def home():
    return "✅ Nami Bot is online!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
