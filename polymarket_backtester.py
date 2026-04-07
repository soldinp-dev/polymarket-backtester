import streamlit as st
import requests
import pandas as pd
import time
import json
from datetime import datetime, timezone
from typing import Optional
import random

# ════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Polymarket 5-Min Backtester",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("⚡ Polymarket 5-Min ETH/BTC Backtester")
st.markdown("Simulate your PolyCop bot strategy with real historical data from Polymarket & Binance")

# ════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ════════════════════════════════════════════════════════════════════════════

GAMMA_API   = "https://gamma-api.polymarket.com"
BINANCE_API = "https://api.binance.com/api/v3"

# ════════════════════════════════════════════════════════════════════════════
# DATA FETCHING
# ════════════════════════════════════════════════════════════════════════════

def fetch_polymarket_markets(asset: str, limit: int = 200) -> list:
    """Fetch closed 5-min Up/Down markets from Polymarket."""
    slug_prefix = f"{asset.lower()}-updown-5m"
    markets = []
    offset = 0
    page_size = 100

    st.info(f"🔄 Fetching Polymarket markets for {asset}...")
    
    with st.spinner(f"Searching for {asset} 5-min markets..."):
        while len(markets) < limit:
            try:
                url = (
                    f"{GAMMA_API}/markets"
                    f"?closed=true"
                    f"&limit={min(page_size, limit - len(markets))}"
                    f"&offset={offset}"
                    f"&order=startDate"
                    f"&ascending=false"
                )
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                page = resp.json()
            except Exception as e:
                st.warning(f"⚠️ Polymarket API error: {e}")
                break

            if not page:
                break

            for m in page:
                question = m.get("question", "").lower()
                
                # More flexible filtering: look for asset AND (5-min OR up/down pattern)
                has_asset = asset.lower() in question
                has_timeframe = ("5" in question and "min" in question) or "5m" in question
                has_direction = "up" in question or "down" in question
                
                # Accept if: asset + (timeframe or direction)
                # This is more lenient than before
                if has_asset and (has_timeframe or has_direction):
                    markets.append(m)

            offset += page_size

            if len(page) < page_size:
                break

            time.sleep(0.15)   # polite rate limiting

    # If we still don't have markets, try a direct search
    if len(markets) < limit:
        try:
            st.info(f"📡 Trying alternative API endpoint...")
            url = f"{GAMMA_API}/markets?closed=true&limit={limit}&order=startDate&ascending=false"
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            alt_markets = resp.json() or []
            
            # Filter these more loosely
            for m in alt_markets:
                if len(markets) >= limit:
                    break
                question = m.get("question", "").lower()
                # Just check for asset and any mention of up/down
                if asset.lower() in question and ("up" in question or "down" in question):
                    if m not in markets:  # avoid duplicates
                        markets.append(m)
        except Exception as e:
            st.warning(f"⚠️ Alternative search failed: {e}")

    if len(markets) == 0:
        st.error(f"❌ No markets found. The Polymarket API may be temporarily unavailable. Try again in a moment.")
    else:
        st.success(f"✓ Loaded {len(markets)} markets")

    return markets[:limit]


def fetch_binance_klines(symbol: str, start_ts_ms: int, end_ts_ms: int) -> list:
    """Fetch 1-minute OHLC candles from Binance."""
    try:
        url = (
            f"{BINANCE_API}/klines"
            f"?symbol={symbol}"
            f"&interval=1m"
            f"&startTime={start_ts_ms}"
            f"&endTime={end_ts_ms}"
            f"&limit=10"
        )
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return []


def get_price_at_minute(symbol: str, market_start_ts: int, minute: float) -> Optional[float]:
    """Get the actual asset price at `minute` minutes into the 5-min window."""
    target_ts_ms = int((market_start_ts + minute * 60) * 1000)
    start_ms = int((market_start_ts + (minute - 1) * 60) * 1000)
    end_ms   = int((market_start_ts + (minute + 1) * 60) * 1000)

    candles = fetch_binance_klines(symbol, start_ms, end_ms)
    if not candles:
        return None

    best = min(candles, key=lambda c: abs(c[0] - target_ts_ms))
    return float(best[4])   # close price


def parse_market_start_ts(market: dict) -> Optional[int]:
    """Extract Unix timestamp (seconds) from a market dict."""
    for field in ["startDate", "startTime", "created_at", "createdAt"]:
        val = market.get(field)
        if val:
            try:
                if isinstance(val, (int, float)):
                    ts = int(val)
                    return ts // 1000 if ts > 1e12 else ts
                dt = datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                return int(dt.timestamp())
            except Exception:
                continue
    return None


def parse_resolution(market: dict) -> Optional[str]:
    """Determine how the market resolved: 'up' or 'down'."""
    op = market.get("outcomePrices")
    outcomes = market.get("outcomes")
    if op and outcomes:
        try:
            prices   = json.loads(op)   if isinstance(op, str)       else op
            outcomes = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
            for i, p in enumerate(prices):
                if float(p) > 0.95:
                    label = str(outcomes[i]).lower()
                    if "up" in label or label in ("yes",):
                        return "up"
                    if "down" in label or label in ("no",):
                        return "down"
        except Exception:
            pass

    ro = str(market.get("resolvedOutcome", "")).lower()
    if "up" in ro:   return "up"
    if "down" in ro: return "down"

    return None


# ════════════════════════════════════════════════════════════════════════════
# SIMULATION ENGINE
# ════════════════════════════════════════════════════════════════════════════

def simulate_market(
    market: dict,
    asset: str,
    binance_symbol: str,
    direction: str,
    time_min: float,
    time_max: float,
    price_min: float,
    price_max: float,
    change_min: float,
    change_max: float,
    trade_size: float,
    slippage_pct: float,
) -> dict:
    """Simulate one 5-min market."""
    result = {
        "market_id": market.get("id") or market.get("conditionId", "?"),
        "start_date": market.get("startDate", ""),
        "resolution": None,
        "price_open": None,
        "price_trigger": None,
        "price_change": None,
        "contract_price": None,
        "fill_price": None,
        "triggered": False,
        "trade_dir": None,
        "won": None,
        "pnl": 0.0,
        "skip_reason": None,
    }

    # Parse start timestamp
    start_ts = parse_market_start_ts(market)
    if start_ts is None:
        result["skip_reason"] = "no_timestamp"
        return result

    # Get resolution
    resolution = parse_resolution(market)
    if resolution is None:
        result["skip_reason"] = "unresolved"
        return result
    result["resolution"] = resolution

    # Fetch real Binance prices
    open_price = get_price_at_minute(binance_symbol, start_ts, 0)
    trigger_price_asset = get_price_at_minute(binance_symbol, start_ts, (time_min + time_max) / 2)

    if open_price is None or trigger_price_asset is None:
        result["skip_reason"] = "no_binance_data"
        return result

    price_change = trigger_price_asset - open_price
    result["price_open"] = open_price
    result["price_trigger"] = trigger_price_asset
    result["price_change"] = price_change

    # Check price-change trigger
    if not (change_min <= price_change <= change_max):
        result["skip_reason"] = f"price_change out of range"
        return result

    # Model contract price at trigger time
    move_pct = abs(price_change / open_price) * 100
    raw_prob = 0.50 + min(move_pct / 0.35 * 0.45, 0.46)
    move_favours = "up" if price_change > 0 else "down"

    if direction in ("up", "both"):
        contract_price = raw_prob if move_favours == "up" else (1 - raw_prob)
    else:
        contract_price = raw_prob if move_favours == "down" else (1 - raw_prob)

    contract_price = max(0.01, min(0.99, contract_price + random.uniform(-0.03, 0.03)))
    result["contract_price"] = round(contract_price, 4)

    # Check contract price trigger
    if not (price_min <= contract_price <= price_max):
        result["skip_reason"] = "contract_price out of range"
        return result

    # Apply slippage
    fill_price = contract_price * (1 + slippage_pct / 100 * random.uniform(0, 1))
    fill_price = min(fill_price, 0.999)
    result["fill_price"] = round(fill_price, 4)

    if fill_price >= 1.0:
        result["skip_reason"] = "fill_price >= 1.0"
        return result

    # Determine trade direction and outcome
    trade_dir = direction if direction != "both" else ("up" if move_favours == "up" else "down")
    result["trade_dir"] = trade_dir
    result["triggered"] = True

    won = (trade_dir == resolution)
    result["won"] = won

    # Calculate P&L
    shares = trade_size / fill_price
    if won:
        pnl = shares * 1.0 - trade_size
    else:
        pnl = -trade_size

    result["pnl"] = round(pnl, 4)
    return result


# ════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ════════════════════════════════════════════════════════════════════════════

# Sidebar for inputs
with st.sidebar:
    st.header("⚙️ Configuration")
    
    st.subheader("Asset & Direction")
    asset = st.selectbox("Asset", ["BTC", "ETH"])
    direction = st.selectbox("Direction", ["up", "down", "both"])
    
    st.subheader("Timing")
    time_min = st.slider("Trigger window start (min)", 0.0, 4.9, 4.0, 0.1)
    time_max = st.slider("Trigger window end (min)", 0.1, 5.0, 5.0, 0.1)
    
    st.subheader("Contract Price")
    price_min = st.slider("Min contract price", 0.01, 0.99, 0.70, 0.01)
    price_max = st.slider("Max contract price", 0.01, 0.99, 0.95, 0.01)
    
    st.subheader("Asset Price Change (USD)")
    change_min = st.number_input("Min price change", value=-999.0, step=0.1)
    change_max = st.number_input("Max price change", value=-20.0 if asset == "BTC" else -3.0, step=0.1)
    
    st.subheader("Trade Parameters")
    trade_size = st.number_input("Trade size (USDC)", value=5.0, min_value=0.01, step=0.1)
    slippage = st.number_input("Slippage (%)", value=10.0, min_value=0.0, step=1.0)
    bankroll = st.number_input("Starting bankroll (USDC)", value=100.0, min_value=1.0, step=1.0)
    market_limit = st.slider("Number of markets to test", 10, 500, 50, 10)
    
    run_backtest = st.button("🚀 Run Backtest", use_container_width=True)

# Main content area
if run_backtest:
    st.subheader("📊 Backtest Results")
    
    # Fetch markets
    markets = fetch_polymarket_markets(asset, market_limit)
    
    if not markets:
        st.error(f"❌ No markets found for {asset}. Check your internet connection.")
    else:
        st.success(f"✓ Loaded {len(markets)} markets")
        
        symbol_map = {"ETH": "ETHUSDT", "BTC": "BTCUSDT"}
        binance_symbol = symbol_map[asset]
        
        # Run simulation
        st.info(f"🔄 Running backtest on {len(markets)} markets...")
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        for i, market in enumerate(markets):
            result = simulate_market(
                market=market,
                asset=asset,
                binance_symbol=binance_symbol,
                direction=direction,
                time_min=time_min,
                time_max=time_max,
                price_min=price_min,
                price_max=price_max,
                change_min=change_min,
                change_max=change_max,
                trade_size=trade_size,
                slippage_pct=slippage,
            )
            results.append(result)
            
            progress = (i + 1) / len(markets)
            progress_bar.progress(progress)
            status_text.text(f"Processing {i + 1}/{len(markets)} markets...")
            
            time.sleep(0.02)  # Small delay to avoid rate limits
        
        progress_bar.empty()
        status_text.empty()
        
        # Calculate metrics
        triggered = [r for r in results if r["triggered"]]
        skipped = [r for r in results if not r["triggered"]]
        wins = [r for r in triggered if r["won"]]
        losses = [r for r in triggered if not r["won"]]
        
        total_pnl = sum(r["pnl"] for r in triggered)
        final_bank = bankroll + total_pnl
        roi_pct = (total_pnl / bankroll) * 100
        win_rate = len(wins) / len(triggered) * 100 if triggered else 0
        trigger_rate = len(triggered) / len(results) * 100 if results else 0
        
        # Max drawdown
        current_bank = bankroll
        peak = bankroll
        max_dd = 0.0
        for r in triggered:
            current_bank += r["pnl"]
            if current_bank > peak:
                peak = current_bank
            dd = (peak - current_bank) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        # Display metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total P&L", f"${total_pnl:.2f}", 
                     delta=f"{roi_pct:+.1f}%",
                     delta_color="normal" if total_pnl >= 0 else "inverse")
        
        with col2:
            st.metric("Win Rate", f"{win_rate:.1f}%", 
                     f"{len(wins)} wins, {len(losses)} losses")
        
        with col3:
            st.metric("Trades Triggered", f"{len(triggered)}", 
                     f"{trigger_rate:.1f}% of markets")
        
        col4, col5, col6 = st.columns(3)
        
        with col4:
            st.metric("Final Bankroll", f"${final_bank:.2f}")
        
        with col5:
            st.metric("Max Drawdown", f"{max_dd*100:.1f}%")
        
        with col6:
            st.metric("Avg Fill Price", f"${(sum(r['fill_price'] for r in triggered) / len(triggered) if triggered else 0):.4f}")
        
        # Trades table
        if triggered:
            st.subheader("📈 Triggered Trades")
            
            trades_df = pd.DataFrame([{
                "Market ID": r["market_id"][:12],
                "Date": r["start_date"][:10],
                "Resolution": r["resolution"].upper(),
                "Direction": r["trade_dir"].upper(),
                "Price Change": f"${r['price_change']:.2f}",
                "Fill Price": f"${r['fill_price']:.4f}",
                "Result": "✓ WIN" if r["won"] else "✗ LOSS",
                "P&L": f"${r['pnl']:+.2f}"
            } for r in triggered[:50]])
            
            st.dataframe(trades_df, use_container_width=True, hide_index=True)
            
            if len(triggered) > 50:
                st.caption(f"Showing first 50 of {len(triggered)} trades")
        
        # Skip reasons
        if skipped:
            st.subheader("⏭️ Skipped Markets")
            
            reasons = {}
            for r in skipped:
                key = r.get("skip_reason", "unknown")
                if key and "price_change" in key:
                    key = "price_change out of range"
                elif key and "contract_price" in key:
                    key = "contract_price out of range"
                reasons[key] = reasons.get(key, 0) + 1
            
            reasons_df = pd.DataFrame([
                {"Reason": reason, "Count": count}
                for reason, count in sorted(reasons.items(), key=lambda x: -x[1])
            ])
            
            st.dataframe(reasons_df, use_container_width=True, hide_index=True)
        
        # Insights
        st.subheader("💡 Insights")
        
        insights = []
        
        if len(triggered) == 0:
            insights.append("⚠️ **Zero trades triggered.** Try widening your price or change ranges.")
        elif win_rate > 65:
            insights.append(f"✅ **Strong win rate ({win_rate:.0f}%).** Your criteria are filtering well.")
        elif win_rate < 45:
            insights.append(f"⚠️ **Win rate below 50% ({win_rate:.0f}%).** Consider tighter entry filters.")
        
        if trigger_rate < 5:
            insights.append(f"⚠️ **Very low trigger rate ({trigger_rate:.1f}%).** Your filters may be too strict.")
        
        if max_dd > 0.3:
            insights.append(f"⚠️ **High max drawdown ({max_dd*100:.0f}%).** Consider smaller trade size.")
        
        if insights:
            for insight in insights:
                st.info(insight)
        else:
            st.success("✓ No major warnings. Parameters look reasonable.")
        
        # Export CSV
        st.subheader("📥 Export")
        
        if triggered:
            csv = "market_id,start_date,resolution,trade_dir,price_open,price_trigger,price_change,contract_price,fill_price,won,pnl\n"
            for r in triggered:
                csv += f"{r['market_id']},{r['start_date']},{r['resolution']},{r['trade_dir']},{r['price_open']:.2f},{r['price_trigger']:.2f},{r['price_change']:.2f},{r['contract_price']:.4f},{r['fill_price']:.4f},{str(r['won']).lower()},{r['pnl']:.4f}\n"
            
            st.download_button(
                label="📥 Download Trades as CSV",
                data=csv,
                file_name=f"backtest_{asset.lower()}_{direction}_{int(time.time())}.csv",
                mime="text/csv"
            )
        else:
            st.info("No triggered trades to export.")
