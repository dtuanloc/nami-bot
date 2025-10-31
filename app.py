from flask import Flask, request, jsonify, abort
import time, threading, os

app = Flask(__name__)
RUN_LOOP = {"running": False}
TOKEN = os.getenv("WEBHOOK_TOKEN", "test123")

def check_market():
    # Fake check
    print("🪙 Checking market at", time.strftime("%H:%M:%S"))

def bot_loop():
    while True:
        if RUN_LOOP["running"]:
            check_market()
        time.sleep(5)

threading.Thread(target=bot_loop, daemon=True).start()

def auth(req):
    return req.headers.get("Authorization") == f"Bearer {TOKEN}"

@app.route("/start", methods=["POST"])
def start():
    if not auth(request): abort(401)
    RUN_LOOP["running"] = True
    return jsonify({"running": True})

@app.route("/stop", methods=["POST"])
def stop():
    if not auth(request): abort(401)
    RUN_LOOP["running"] = False
    return jsonify({"running": False})

@app.route("/trigger", methods=["POST"])
def trigger():
    if not auth(request): abort(401)
    check_market()
    return jsonify({"ok": True, "msg": "Triggered!"})

@app.route("/")
def home():
    return "Nami Bot Online 😎"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
