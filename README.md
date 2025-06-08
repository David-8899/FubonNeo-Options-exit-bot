# FubonNeo-exit-monitor

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
- ✅ Trailing take profit kicks in after +8, +10, +12... points  
- 📉 After +18 points, if price drops by 3 from high, exit  
- 🕒 Monitors every 3 seconds using WebSocket live data

---

## 🛠️ Installation

1. Clone this repo:
   ```bash
   git clone https://github.com/yourname/fubon-exit-monitor.git
   cd fubon-exit-monitor
