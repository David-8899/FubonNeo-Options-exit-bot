# exit_monitor.py
# Exit Monitor Script (Public Version - Sensitive Info Removed)

from fubon_neo.sdk import FubonSDK, Mode, FutOptOrder
from fubon_neo.constant import TimeInForce, FutOptOrderType, FutOptPriceType, BSAction, FutOptMarketType
from dotenv import load_dotenv
import os, json, time, threading, requests
from datetime import datetime, timezone, timedelta, time as dt_time
import subprocess

# === Load Environment Variables ===
load_dotenv(".env")
ACCOUNT = os.getenv("ACCOUNT")
PASSWORD = os.getenv("PASSWORD")
CERT_PATH = os.getenv("CERT_PATH")
CERT_PASSWORD = os.getenv("CERT_PASSWORD")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN_1")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# === Initialize SDK and Login ===
sdk = FubonSDK(168, 4)
res = sdk.login(ACCOUNT, PASSWORD, CERT_PATH, CERT_PASSWORD)
if not res.is_success:
    print(f"❌ Login failed: {res.message}")
    exit(1)

account = res.data[0]
sdk.init_realtime(Mode.Speed)
futopt = sdk.marketdata.websocket_client.futopt

# === Utility Functions ===
def now_tw():
    return datetime.now(timezone(timedelta(hours=8)))

def is_day_session():
    now = now_tw()
    return dt_time(8, 0) <= now.time() <= dt_time(13, 45)

market_type = FutOptMarketType.Option if is_day_session() else FutOptMarketType.OptionNight

def tele(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
        requests.post(url, json=payload, timeout=5)
        print(f"[Telegram] {msg}")
    except Exception as e:
        print(f"[Telegram Error] {e}")

# === Global Variables ===
symbol = entry_price = lots = None
latest_price = stop_price = highest_price = None
is_pending = is_exit_done = False
triggered_stop = triggered_trail = False
moved_8 = moved_10 = moved_12 = moved_14 = moved_16 = moved_18 = False
latest_order_no = None
notify_timestamps = {}
lock = threading.Lock()
subscribed = False

# === Notify with Rate Limiting ===
def notify_limited(msg: str, sec: int = 60, mode="b", key=None):
    now = datetime.now()
    actual_key = key or msg
    last_time = notify_timestamps.get(actual_key)
    if not last_time or (now - last_time).total_seconds() >= sec:
        if mode in ("b", "t"):
            tele(msg)
        if mode in ("b", "p"):
            print(msg)
        notify_timestamps[actual_key] = now

# === Generate Option Symbol (e.g., TX410000A5) ===
def get_option_symbol(strike_price, call_put, expiry_date, symbol_prefix):
    month_map = {
        "Call": ['A','B','C','D','E','F','G','H','I','J','K','L'],
        "Put":  ['M','N','O','P','Q','R','S','T','U','V','W','X']
    }
    call_put_str = str(call_put).split('.')[-1]  # 'Call' or 'Put'
    year_code = expiry_date[3]                   # '202505' -> '5'
    month_num = int(expiry_date[4:6])            # '202505' -> 5
    month_letter = month_map[call_put_str][month_num - 1]
    return f"{symbol_prefix}{int(strike_price)}{month_letter}{year_code}"

# === Query and List Open Positions ===
def find_recent_entries(account):
    try:
        resp = sdk.futopt_accounting.query_single_position(account)
        if not resp.is_success or not resp.data:
            tele("⚠️ No open positions found.")
            return []

        entries = []
        for pos in resp.data:
            try:
                order_no = pos.order_no or ""
                order_prefix = order_no.split("-")[0] if "-" in order_no else order_no
                symbol = get_option_symbol(
                    strike_price=pos.strike_price,
                    call_put=pos.call_put,
                    expiry_date=pos.expiry_date,
                    symbol_prefix=pos.symbol
                )
                entries.append({
                    "symbol": symbol,
                    "price": float(pos.price),
                    "lots": int(pos.tradable_lot),
                    "call_put": pos.call_put,
                    "order_no": order_prefix,
                    "strike": pos.strike_price,
                    "expiry": pos.expiry_date
                })
            except Exception as e:
                print(f"⚠️ Error parsing position: {e}")
                continue

        return sorted(entries, key=lambda e: e['order_no'], reverse=True)

    except Exception as e:
        tele(f"❗ Error querying positions: {e}")
        return []

# === Show Available Positions in Telegram ===
def resume_monitor():
    positions = find_recent_entries(account)
    if not positions:
        tele("📭 No available positions to monitor.")
        return
    msg = "📋 Available Positions:\n"
    for idx, p in enumerate(positions, 1):
        msg += f"{idx}. Order: {p['order_no']} ➜ Symbol: {p['symbol']} ➜ Price: {p['price']} ➜ Lots: {p['lots']} ➜ {p['call_put']}\n"
    tele(msg)

# === Place Exit Order (RangeMarket IOC) ===
def place_exit_order(is_buy, is_entry):
    global latest_order_no
    if symbol is None or lots is None:
        tele("❌ Order failed: symbol or lots not set")
        return None
    order = FutOptOrder(
        buy_sell=BSAction.Buy if is_buy else BSAction.Sell,
        symbol=symbol,
        lot=lots,
        price=None,
        market_type=market_type,
        price_type=FutOptPriceType.RangeMarket,
        time_in_force=TimeInForce.IOC,
        order_type=FutOptOrderType.New if is_entry else FutOptOrderType.Close,
        user_def="py_exit"
    )
    resp = sdk.futopt.place_order(account, order)
    if resp.is_success:
        latest_order_no = resp.data.order_no
        tele(f"✅ Order placed: {latest_order_no}")
    else:
        tele(f"❌ Order failed: {resp.message}")
    return resp

# === Exit Check with Trailing Logic ===
def check_exit():
    global is_pending, is_exit_done, latest_price, stop_price
    global highest_price, triggered_trail, triggered_stop
    global moved_8, moved_10, moved_12, moved_14, moved_16, moved_18
    try:
        with lock:
            if is_pending or is_exit_done or symbol is None or entry_price is None or lots is None or latest_price is None:
                return

            price = latest_price
            profit = price - entry_price

        if profit <= -8 and not triggered_stop:
            tele(f"📉 Stop loss triggered (-8): {latest_price}")
            is_pending = True
            triggered_stop = True
            place_exit_order(False, False)
            return

        if profit >= 8 and not moved_8:
            stop_price = entry_price + 6
            moved_8 = True
            tele(f"📌 Trail set (+8): {stop_price}")
        if profit >= 10 and not moved_10:
            stop_price = entry_price + 8
            moved_10 = True
            tele(f"📌 Trail raised (+10): {stop_price}")
        if profit >= 12 and not moved_12:
            stop_price = entry_price + 10
            moved_12 = True
            tele(f"📌 Trail raised (+12): {stop_price}")
        if profit >= 14 and not moved_14:
            stop_price = entry_price + 12
            moved_14 = True
            tele(f"📌 Trail raised (+14): {stop_price}")
        if profit >= 16 and not moved_16:
            stop_price = entry_price + 14
            moved_16 = True
            tele(f"📌 Trail raised (+16): {stop_price}")
        if profit >= 18 and not moved_18:
            stop_price = entry_price + 16
            moved_18 = True
            highest_price = latest_price
            tele(f"🚀 Trail maxed (+18): {stop_price}, enabling high tracking")

        if moved_18 and latest_price > highest_price:
            highest_price = latest_price
            tele(f"📈 New high: {highest_price}")

        if moved_18 and latest_price <= highest_price - 3 and not triggered_trail:
            tele(f"📉 Exit by pullback from high: High={highest_price}, Now={latest_price}")
            is_pending = True
            triggered_trail = True
            place_exit_order(False, False)
            return

        if stop_price and latest_price <= stop_price:
            tele(f"📉 Exit: price dropped below trail {stop_price}, Now={latest_price}")
            is_pending = True
            place_exit_order(False, False)
            return

    except Exception as e:
        tele(f"❗ check_exit error: {e}")
        
# === Order Filled Callback ===
def on_filled(code, content):
    global is_exit_done
    if getattr(content, "order_no", None) != latest_order_no:
        print(f"🛑 Ignored unrelated order: {getattr(content, 'order_no', 'N/A')}")
        return
    if content.order_type == "Close":
        tele(f"📤 Exit Filled ➜ Price: {content.filled_avg_price}, Lots: {content.filled_lot}")
        is_exit_done = True
        resume_monitor()

# === WebSocket Tick Handler ===
def handle_message(msg):
    global subscribed, latest_price
    try:
        obj = json.loads(msg)
        if obj.get("event") == "authenticated" and not subscribed and symbol:
            futopt.subscribe({"channel": "trades", "symbol": symbol})
            futopt.subscribe({"channel": "trades", "symbol": symbol, "afterHours": True})
            subscribed = True
            tele(f"✅ Subscribed to {symbol}")
        elif obj.get("event") == "data" and obj.get("channel") == "trades":
            trades = obj["data"].get("trades", [])
            if trades:
                with lock:
                    latest_price = trades[0]["price"]
                    notify_limited(f"📈 Latest Price: {latest_price}", sec=60, mode="t", key="price")
    except Exception as e:
        tele(f"❗ handle_message error: {e}")

# === Telegram Command Loop ===
def parse_command(cmd):
    global symbol, entry_price, lots, is_exit_done, is_pending, stop_price, highest_price
    global moved_8, moved_10, moved_12, moved_14, moved_16, moved_18
    global triggered_trail, triggered_stop, subscribed

    try:
        if cmd == "/s":
            if not symbol:
                tele("❓ No position selected. Use /c [number] [lots]")
            else:
                tele(f"📊 Status\nSymbol: {symbol}\nEntry: {entry_price}\nLatest: {latest_price}\nPending: {'Yes' if is_pending else 'No'}")

        elif cmd == "/r" or cmd == "/m":
            resume_monitor()

        elif cmd.startswith("/c"):
            parts = cmd.split()
            if len(parts) < 2:
                tele("Usage: /c [number] [lots (optional)]")
                return
            idx = int(parts[1]) - 1
            positions = find_recent_entries(account)
            if idx < 0 or idx >= len(positions):
                tele("❗ Invalid selection index")
                return

            selected = positions[idx]
            symbol = selected["symbol"]
            entry_price = float(selected["price"])
            lots = int(parts[2]) if len(parts) >= 3 else int(selected["lots"])

            is_exit_done = is_pending = False
            stop_price = highest_price = None
            moved_8 = moved_10 = moved_12 = moved_14 = moved_16 = moved_18 = False
            triggered_trail = triggered_stop = False
            subscribed = False

            futopt.subscribe({"channel": "trades", "symbol": symbol})
            futopt.subscribe({"channel": "trades", "symbol": symbol, "afterHours": True})

            tele(f"✅ Monitoring Position: {symbol}, Entry: {entry_price}, Lots: {lots}")

        elif cmd == "/res":
            tele("♻️ Restarting exit monitor...")
            subprocess.Popen(["python", __file__])
            os._exit(0)

        elif cmd == "/h":
            tele("Commands:\n/s - Status\n/r - Refresh positions\n/m - Show positions\n/c [n] [lots] - Choose position\n/res - Restart script")

        else:
            tele("❓ Unknown command. Try /h")

    except Exception as e:
        tele(f"❗ parse_command error: {e}")

# === Poll Telegram Commands ===
def telegram_loop():
    offset = None
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            if offset:
                url += f"?offset={offset}"
            res = requests.get(url, timeout=10).json()

            if offset is None and res.get("result"):
                offset = res["result"][-1]["update_id"] + 1
                continue

            for result in res.get("result", []):
                offset = result["update_id"] + 1
                msg = result.get("message", {}).get("text", "")
                if msg:
                    parse_command(msg.strip())
        except Exception as e:
            tele(f"❗ Telegram loop error: {e}")
        time.sleep(2)

# === WebSocket Reconnect Logic ===
def handle_disconnect(code, message):
    tele(f"⚠️ Disconnected: {code}, {message}")
    safe_reconnect()

def handle_error(error, tb_info=None):
    tele(f"❗ WebSocket Error: {error}")
    if tb_info:
        print(tb_info)

def safe_reconnect():
    global subscribed
    try:
        futopt.disconnect()
    except: pass
    time.sleep(2)
    try:
        futopt.connect()
        subscribed = False
        tele("✅ Reconnected successfully")
    except Exception as e:
        tele(f"❌ Reconnect failed: {e}")

# === Start Monitoring ===
def exit_loop():
    while not is_pending and not is_exit_done:
        check_exit()
        time.sleep(3)

futopt.on("disconnect", handle_disconnect)
futopt.on("error", handle_error)
futopt.on("message", handle_message)
sdk.set_on_futopt_filled(on_filled)

futopt.connect()
threading.Thread(target=exit_loop, daemon=True).start()
threading.Thread(target=telegram_loop, daemon=True).start()
resume_monitor()
print("▶ Exit monitor started.")
while True:
    time.sleep(1)
