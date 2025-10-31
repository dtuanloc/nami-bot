# app.py
import os
import time
import hmac
import hashlib
import threading
import requests
from urllib.parse import urlencode
from flask import Flask, request, jsonify, abort

# Config from env (set these in Render dashboard)
NAMI_API_KEY = os.getenv("NAMI_API_KEY", "")
NAMI_API_SECRET = os.getenv("NAMI_API_SECRET", "")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "change_me")
BASE = os.getenv("NAMI_BASE_URL", "https://nami.exchange/api/v4")

# Bot defaults
DEFAULT_SYMBOL = os.getenv("DEFAULT_SYMBOL", "BTC_V1K")   # BTC/V1K per user's choice
app = Flask(__name__)

# Simple auth for HTTP calls from Siri
def verify_token(req):
    auth = req.headers.get("Authorization", "")
    return auth == f"Bearer {WEBHOOK_TOKEN}"

# Helper: create signature per Nami docs
def make_signature(params: dict) -> str:
    # params: dict of query params (without signature)
    # caller must include timestamp in params before calling
    qs = urlencode(params)  # builds "a=1&b=2"
    # HMAC SHA256 hex
    sig = hmac.new(NAMI_API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()
    return sig

# Public market price (no auth)
def get_price(symbol: str):
    # public ticker endpoint (v4 public)
    url = f"{BASE}/public/ticker"
    r = requests.get(url, timeout=8)
    r.raise_for_status()
    data = r.json()
    # Try common shapes: data["BTC_USDT"]["last_price"] or data["BTC_V1K"]...
    key = symbol
    if isinstance(data, dict) and key in data:
        item = data[key]
        # many endpoints use last_price or last or price
        for k in ("last_price", "last", "price"):
            if k in item:
                return float(item[k])
        # fallback: try 'close' or 'lastPrice' else return full object
        return item
    return data

# Auth'd request helper (for spot order & account)
def signed_request(method, path, params=None, json_body=None):
    params = params or {}
    # add timestamp
    params["timestamp"] = int(time.time() * 1000)
    # create signature
    signature = make_signature(params)
    params_with_sig = dict(params)
    params_with_sig["signature"] = signature
    url = f"{BASE}{path}?{urlencode(params_with_sig)}"
    headers = {
        "x-api-key": NAMI_API_KEY,
        "Content-Type": "application/json"
    }
    if method.upper() == "GET":
        r = requests.get(url, headers=headers, timeout=10)
    else:
        # As per docs example, POST endpoint accepts query params for signing; body optional
        r = requests.post(url, json=json_body or {}, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()

# Routes
@app.route("/")
def home():
    return "Nami Bot Online ✅"

@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "ok": True,
        "default_symbol": DEFAULT_SYMBOL,
        "webhook_protected": bool(WEBHOOK_TOKEN)
    })

@app.route("/checkprice", methods=["POST"])
def checkprice():
    if not verify_token(request): abort(401)
    body = request.get_json(silent=True) or {}
    symbol = body.get("symbol", DEFAULT_SYMBOL)
    try:
        price = get_price(symbol)
        return jsonify({"ok": True, "symbol": symbol, "price": price})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/buy", methods=["POST"])
def buy():
    if not verify_token(request): abort(401)
    body = request.get_json(silent=True) or {}
    symbol = body.get("symbol", DEFAULT_SYMBOL)
    side = "BUY"
    otype = body.get("type", "MARKET")  # MARKET or LIMIT
    qty = body.get("quantity")
    price = body.get("price")  # optional for LIMIT
    if not qty:
        return jsonify({"ok": False, "error": "quantity is required"}), 400
    # construct params per Nami docs example for spot order
    params = {
        "symbol": symbol,
        "side": side,
        "type": otype,
        "quantity": str(qty)
    }
    if otype.upper() == "LIMIT":
        if not price:
            return jsonify({"ok": False, "error": "price required for LIMIT"}), 400
        params["price"] = str(price)
    try:
        res = signed_request("POST", "/spot/order", params=params, json_body={})
        return jsonify({"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/sell", methods=["POST"])
def sell():
    if not verify_token(request): abort(401)
    body = request.get_json(silent=True) or {}
    symbol = body.get("symbol", DEFAULT_SYMBOL)
    side = "SELL"
    otype = body.get("type", "MARKET")
    qty = body.get("quantity")
    price = body.get("price")
    if not qty:
        return jsonify({"ok": False, "error": "quantity is required"}), 400
    params = {
        "symbol": symbol,
        "side": side,
        "type": otype,
        "quantity": str(qty)
    }
    if otype.upper() == "LIMIT":
        if not price:
            return jsonify({"ok": False, "error": "price required for LIMIT"}), 400
        params["price"] = str(price)
    try:
        res = signed_request("POST", "/spot/order", params=params, json_body={})
        return jsonify({"ok": True, "result": res})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/trigger", methods=["POST"])
def trigger():
    if not verify_token(request): abort(401)
    # one-off check: call checkprice and return result
    symbol = request.get_json(silent=True) and request.get_json().get("symbol") or DEFAULT_SYMBOL
    try:
        price = get_price(symbol)
        return jsonify({"ok": True, "symbol": symbol, "price": price, "msg": "triggered"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
