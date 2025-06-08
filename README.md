# Fubon Exit Monitor

A real-time exit monitoring script for Taiwan options using the Fubon SDK and Telegram notifications.  
Designed for traders who need automated stop-loss, take-profit, and trailing-exit logic based on live option prices.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## 📌 Features

- ✅ Connects to Fubon SDK real-time option data  
- ✅ Monitors existing option positions and exits based on defined strategy  
- ✅ Supports fixed stop-loss and dynamic trailing-take-profit  
- ✅ Sends all status and order updates to Telegram  
- ✅ CLI and Telegram command interface (e.g., `/s`, `/c`, `/res`)

---

## 📈 Exit Strategy

- ❌ Stop loss if unrealized P/L ≤ -8 points  
- ✅ Trailing take profit kicks in after +8, +10, +12, +14, +16, +18  
- 📉 After +18 points, if price drops by 3 from high, exit  
- 🕒 Monitors every 3 seconds using WebSocket live data

---

## 🛠️ Installation

You can either clone the repo using Git (if available):

```bash
git clone https://github.com/David-8899/FubonNeo-exit-monitor.git
cd FubonNeo-exit-monitor
```

Or download the project as a `.zip` file directly from the GitHub page.

Then:

1. Copy `.env.example` and rename it to `.env`  
2. Fill in your Fubon credentials and Telegram bot token  
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the script:

```bash
python exit_monitor.py
```

---

## 📦 Fubon SDK Setup

This project requires the **Fubon SDK (`fubon_neo.sdk`)**, which is **not available on PyPI**.

To run this script:

1. You must have an active trading account with Fubon Securities.  
2. Request access to their Python SDK via your broker or Fubon customer support.  
3. After receiving the SDK package (usually a `.zip` or folder), place it in your working environment and ensure it is importable (e.g., placed alongside `exit_monitor.py` or added to `PYTHONPATH`).

> ❗ This repository **does not include or distribute** the SDK itself due to licensing restrictions.

---

## ⚙️ Environment Variables

See `.env.example` for required fields:

```env
ACCOUNT=your_account
PASSWORD=your_password
CERT_PATH=path/to/your_certificate.pfx
CERT_PASSWORD=your_cert_password

TELEGRAM_TOKEN_1=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

---

## 💬 Telegram Commands

| Command       | Description                          |
|---------------|--------------------------------------|
| `/s`          | Show current monitoring status       |
| `/m` or `/r`  | Refresh and list available positions |
| `/c [n] [lots]` | Choose a position to monitor       |
| `/res`        | Restart the script                   |
| `/h`          | Show help message                    |

---

## 📎 Requirements

- Python 3.8+
- `requests`, `python-dotenv`
- Fubon SDK (external, see section above)

---

## ⚠️ Disclaimer

This script is for educational and demonstration purposes only.  
Use at your own risk. It is not a financial advisory tool.  
Ensure correct environment and sandbox testing before applying to real trades.

---

## 📄 License

MIT © 2025 David Lee
