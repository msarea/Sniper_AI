# 🎯 Sniper AI: Official Strategy & Operation Manual

## 1. Executive Summary
**Sniper AI Platinum** is a professional-grade algorithmic trading terminal designed for precision and safety. Unlike basic high-frequency scalpers that get eaten by fees, Sniper AI uses a **"Confluence-Based Committee Approach."**

It runs 4 distinct strategy engines simultaneously. A trade is only executed when the majority of these engines agree, and the "Trend Captain" gives the final authorization. This filters out over 80% of market noise, focusing only on high-probability setups.

---

## 2. The "Brain": Core Strategy Engines
The system monitors the market using four distinct logic layers:

### 🛡️ Strategy A: The Trend Captain (Moving Averages)
* **Logic:** Tracks the "Golden Cross" of the 10-period and 50-period Simple Moving Averages (SMA).
* **Role:** Determines the overall market direction.
* **The "Captain's Rule":** This is the primary safety filter. If the Trend Captain detects a Bear Market, **ALL BUY SIGNALS ARE BLOCKED**, regardless of what other indicators say. We never trade against the trend.

### 📉 Strategy B: The Discount Hunter (VWAP Pullback)
* **Logic:** Uses **Volume Weighted Average Price (VWAP)**, an institutional benchmark.
* **Role:** Identifies value. When price is uptrending but dips to touch the VWAP line, the system identifies this as a "discount" entry before the rally continues.

### 💥 Strategy C: The Volatility Sniper (Bollinger Breakout)
* **Logic:** Monitors the expansion of Bollinger Bands.
* **Role:** Identifies explosive moves. When price forcefully breaks above the Upper Bollinger Band with high volume, it signals the start of a momentum breakout.

### 🚀 Strategy D: The Momentum Checker (MACD)
* **Logic:** Measures the convergence and divergence of price momentum.
* **Role:** Confirms strength. It waits for the MACD line to cross *above* the Signal line (Golden Cross) to ensure the move has fuel behind it.

---

## 3. The Decision Engine: "Confluence Voting"
The bot utilizes a strict voting system to ensure quality over quantity.

* **BUY Signal Logic:**
    1.  **Vote Count:** At least **2 out of 4** strategies must signal "BUY" simultaneously.
    2.  **The Captain's Veto:** The Trend Strategy MUST be one of the voters. If the Trend is Neutral or Bearish, the trade is rejected.

* **SELL Signal Logic:**
    * If the net score drops below **-1** (indicators turning bearish), the system exits to protect capital.

---

## 4. "Platinum" Safety Features (The Shield)
Preserving capital is the #1 priority. This version includes institutional-grade protection:

### 1. The 1:2 Golden Ratio
* We mathematically enforce a **Risk/Reward Ratio of 1:2**.
* **Risk:** We risk \$1 to make \$2.
* **Result:** Even with a 40% win rate, the system remains profitable.

### 2. Daily Circuit Breaker 🛡️
* **Logic:** If the account loses **3%** of its value in a single day (adjustable in config), the bot **locks itself**.
* **Purpose:** Prevents a "bad market day" or a flash crash from draining your account. It forces you to live to trade another day.

### 3. Emergency "Kill Switch" 🚨
* **Logic:** A Red Panic Button is located on the dashboard.
* **Action:** Pressing this instantly **SELLS ALL POSITIONS** and cancels all pending orders. Use this during major news events or black swan crashes.

---

## 5. Advanced Controls: Quantity Overrides
By default, the bot calculates position size based on risk (1% of account). However, you can manually force a specific trade size using the **`@`** syntax in the launcher.

### How to use it:
When the launcher asks for targets, you can type:

* `TSLA` -> Bot risks 1% of account (Auto-Calculation).
* `TSLA@2` -> Bot buys exactly **2 shares**.
* `BTC@0.5` -> Bot buys exactly **0.5 coins**.

*Example Command:* `TSLA@5 NVDA BTC@0.1`

---

## 6. Setup & Configuration Guide

To activate automated trading, you must configure the `config.json` file included in your software folder.

### Step 1: Open Configuration
Open the file named `config.json` using any text editor (Notepad, TextEdit).

### Step 2: Enter Your Credentials
Replace the placeholders with your actual keys:
* **alpaca_api_key**: Your public key from Alpaca Markets.
* **alpaca_secret_key**: Your secret key.
* **telegram_token**: The access token for your notification bot.

### Step 3: Activate the System
By default, the software runs in "Safety Mode" (Listen Only). To enable live trading:

1.  Change `"trading_enabled": false` to `"trading_enabled": true`.
2.  Change `"telegram_enabled": false` to `"telegram_enabled": true`.
3.  **Critical for Trial:** Ensure `"broker"` is set to `"paper"`. Do not change this to `"live"` until you have verified performance with fake money.

---

## 7. Legal Disclaimer
*This software is an algorithmic automation tool provided for educational and efficiency purposes. Algorithmic trading involves significant risk of capital loss. Past performance in backtests does not guarantee future live results. The user assumes full responsibility for all trading decisions and financial outcomes.*