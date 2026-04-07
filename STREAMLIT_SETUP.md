# Polymarket 5-Min Backtester - Streamlit Setup Guide

## Option 1: Deploy to Streamlit Cloud (Easiest for iPhone) ⭐

### Step 1: Create a GitHub account
1. Go to [github.com](https://github.com)
2. Sign up (free)
3. Create a new repository called `polymarket-backtester`

### Step 2: Upload the code
1. In your new repo, click "Add file" → "Upload files"
2. Upload `polymarket_backtester.py`
3. Create a new file called `requirements.txt` with this content:
```
streamlit==1.28.1
requests==2.31.0
pandas==2.1.1
```
4. Commit the files

### Step 3: Deploy to Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with your GitHub account
3. Click "New app"
4. Select your repo, branch, and set the main file path to `polymarket_backtester.py`
5. Click "Deploy"

### Step 4: Access from iPhone
- Streamlit gives you a public URL (like `https://your-username-polymarket.streamlit.app`)
- Open this link in Safari on your iPhone
- Bookmark it for easy access

**That's it!** The app will run on Streamlit's servers, uses real Polymarket & Binance APIs, and is accessible from any device.

---

## Option 2: Run Locally on Mac (Then Access from iPhone)

### Step 1: Install Python
```bash
brew install python3
```

### Step 2: Install Streamlit
```bash
pip install streamlit requests pandas
```

### Step 3: Run the app
```bash
streamlit run polymarket_backtester.py
```

### Step 4: Access from iPhone
1. Find your Mac's IP address:
   - Open Terminal
   - Run: `ifconfig | grep "inet " | grep -v 127.0.0.1`
   - Copy the IP (e.g., `192.168.1.100`)

2. On your iPhone, open Safari and go to:
   ```
   http://YOUR_MAC_IP:8501
   ```

**Note:** Your Mac must stay on and connected to WiFi.

---

## Option 3: Use Replit (Cloud-based, easy)

### Step 1: Go to [replit.com](https://replit.com)

### Step 2: Create new Repl
- Language: Python
- Paste the code

### Step 3: Add requirements
Create a `pyproject.toml` or install packages in the Shell:
```bash
pip install streamlit requests pandas
```

### Step 4: Run
```bash
streamlit run polymarket_backtester.py
```

### Step 5: Access from iPhone
- Replit gives you a public URL
- Open in Safari on iPhone

---

## Features

✅ **Real historical data** - Pulls closed markets from Polymarket API  
✅ **Real price data** - Uses Binance OHLC candles  
✅ **Interactive configuration** - Adjust all parameters via sidebar  
✅ **Live results** - P&L, win rate, drawdown, insights  
✅ **Trade-by-trade log** - See every triggered trade  
✅ **CSV export** - Download results for analysis  
✅ **iPhone compatible** - Works on any browser  

---

## Parameters Explained

- **Asset**: BTC or ETH
- **Direction**: Up, Down, or Both (both = trade whichever direction the price moves)
- **Trigger window**: Minutes into the 5-min market to check entry conditions
- **Contract price range**: Price at which you want to buy the contract ($0.01-$0.99)
- **Price change range**: Min/max price movement you're willing to trade on
- **Trade size**: How much USDC to risk per trade
- **Slippage**: Expected execution cost (%)
- **Bankroll**: Starting capital
- **Market limit**: How many historical markets to test (10-500)

---

## Troubleshooting

**"No markets found"**
- Check internet connection
- Try adjusting market_limit (start with 50)
- API might be rate-limited; wait a minute and try again

**"No Binance data"**
- The market might be too old (Binance has limited historical 1-min data)
- This is normal; the app skips those markets

**App is slow**
- Reduce market_limit to 20-30 for faster testing
- Streamlit Cloud may be slower than local; this is normal

**Can't access from iPhone on home WiFi**
- Make sure iPhone and Mac are on the same WiFi
- Check Mac firewall isn't blocking port 8501
- Try: `System Preferences > Security & Privacy > Firewall`

---

## Recommended Parameters

### Aggressive (more trades, higher risk)
- Contract price: $0.60-$0.90
- Price change: -$999 to -$5 (BTC) or -$999 to -$0.50 (ETH)
- Slippage: 15%

### Conservative (fewer trades, higher win rate)
- Contract price: $0.75-$0.95
- Price change: -$999 to -$20 (BTC) or -$999 to -$3 (ETH)
- Slippage: 5%

### Balanced (default)
- Contract price: $0.70-$0.95
- Price change: -$999 to -$20 (BTC) or -$999 to -$3 (ETH)
- Slippage: 10%

---

**Questions?** Check the insights in the results panel—they'll tell you if your filters are too tight, win rate is weak, or drawdown is high.
