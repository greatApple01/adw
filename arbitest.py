import ccxt
import time
import logging
import telebot
import os
import threading
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# ========== CONFIG ==========
TELEGRAM_TOKEN = os.getenv("8048962279:AAGio1tfg84F15S2DojR_YtYh9bkmTfU1oQ")
CHAT_ID = os.getenv("CHAT_ID", "935195242")

bot = telebot.TeleBot(TELEGRAM_TOKEN, parse_mode="Markdown")

TRADE_AMOUNT_USDT = 10
PROFIT_THRESHOLD = 0.02  # 2% spread
WITHDRAWAL_FEE = 1       # fixed $1 withdrawal cost

logs = []  # memory logs for website
status_info = {"last_checked": None, "last_opportunity": None}

# ========== LOGGING ==========
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

def log(msg):
    logs.append(msg)
    if len(logs) > 100:
        logs.pop(0)
    logging.info(msg)

# ========== EXCHANGES ==========
gate = ccxt.gateio()
mexc = ccxt.mexc()

log("⏳ Loading markets...")
gate.load_markets()
mexc.load_markets()

# ========== PAIRS ==========
pairs_to_check = [
    'SOV/USDT', 'LIKE/USDT', 'GMEE/USDT', 'BCCOIN/USDT', 'PIN/USDT', 'XRP/USDT', 'ADA/USDT', 'SOL/USDT', 'AVAX/USDT', 'DOT/USDT',
    'LINK/USDT', 'UNI/USDT', 'LTC/USDT', 'TRX/USDT', 'XLM/USDT', 'ATOM/USDT', 'ALGO/USDT', 'FIL/USDT', 'XTZ/USDT', 'VET/USDT',
    'ICP/USDT', 'SHIB/USDT', 'DOGE/USDT', 'FLOKI/USDT', 'PEPE/USDT', 'WIF/USDT', 'BONK/USDT', 'ORDI/USDT', 'SUI/USDT', 'APT/USDT',
    'SRI/USDT', 'TIA/USDT', 'PYTH/USDT', 'JTO/USDT', 'ONDO/USDT', 'WLD/USDT', 'STRK/USDT', 'DYM/USDT', 'MANTA/USDT', 'NEAR/USDT',
    'IMX/USDT', 'ARB/USDT', 'OP/USDT', 'CRV/USDT', 'GRT/USDT', 'SNX/USDT', 'REN/USDT', 'FET/USDT', 'INJ/USDT', 'CELO/USDT',
    'RDNT/USDT', 'STORJ/USDT', 'MINA/USDT', 'KAS/USDT', 'LPT/USDT', 'KDA/USDT', 'ANKR/USDT', 'MASK/USDT', 'ENJ/USDT', 'CHZ/USDT',
    'FLOW/USDT', 'NEO/USDT', 'QTUM/USDT', 'IOST/USDT', 'PHA/USDT', 'AR/USDT', 'BLUR/USDT', 'HOOK/USDT', 'GALA/USDT', 'AXS/USDT',
    'MANA/USDT', 'SAND/USDT', 'EGLD/USDT', 'TET/USDT', 'TON/USDT', 'TURBO/USDT', 'EVER/USDT', 'MEME/USDT', 'REKTCOIN/USDT',
    'CTA/USDT', 'BST/USDT', 'SPX/USDT', 'ISLM/USDT', 'IVPAY/USDT', 'LIFE/USDT', 'FURY/USDT', 'VSC/USDT', 'MGT/USDT', 'DCK/USDT',
    'HGPT/USDT', 'PORK/USDT', 'KAR/USDT', 'TRADE/USDT', 'CHO/USDT', 'GMMT/USDT', 'BRN/USDT', 'TSUGT/USDT', 'FRED/USDT',
    'GAMESTOP/USDT', 'PAW/USDT', 'HAT/USDT', 'GFI/USDT', 'SUIP/USDT', 'DKS/USDT', 'BARSIK/USDT', 'GXE/USDT', 'CANTO/USDT',
    'ANDYETH/USDT', 'MONG/USDT', 'ARCA/USDT', 'RBC/USDT', 'USDM/USDT', 'ARRR/USDT', 'SNPT/USDT', 'MEW/USDT', 'EUL/USDT',
    'APE/USDT', 'BRAWL/USDT'
]

# Common pairs only
gate_symbols = set(gate.symbols)
mexc_symbols = set(mexc.symbols)
common_pairs = [p for p in pairs_to_check if p in gate_symbols and p in mexc_symbols]
log(f"✅ Found {len(common_pairs)} tradable pairs in both Gate.io & MEXC")

# ========== FILTERS ==========
def filter_arbitrage_opportunity(pair, gate, mexc, trade_amount_usdt=TRADE_AMOUNT_USDT, profit_threshold=PROFIT_THRESHOLD):
    try:
        gate_ticker = gate.fetch_ticker(pair)
        mexc_ticker = mexc.fetch_ticker(pair)
        gate_orderbook = gate.fetch_order_book(pair)
        mexc_orderbook = mexc.fetch_order_book(pair)

        gate_price = gate_ticker['ask']
        mexc_price = mexc_ticker['bid']
        spread = (mexc_price - gate_price) / gate_price

        # --- Spread Filter ---
        gate_spread = gate_ticker['ask'] - gate_ticker['bid']
        if gate_spread / gate_ticker['ask'] > 0.005:
            return None, f"❌ Wide spread on Gate.io {pair}"

        # --- Slippage ---
        top_ask_price = gate_orderbook['asks'][0][0]
        slippage = (top_ask_price - gate_price) / gate_price
        if slippage > 0.005:
            return None, f"❌ Slippage too high {pair}"

        # --- Liquidity ---
        gate_depth_volume = sum([o[1] for o in gate_orderbook['asks'] if o[0] <= gate_price * 1.01])
        liquidity_score = gate_depth_volume * gate_price
        if liquidity_score < trade_amount_usdt:
            return None, f"❌ Low liquidity {pair}"

        target_price = gate_price * 1.02
        liquidity_2pct = sum([o[1] * o[0] for o in gate_orderbook['asks'] if o[0] <= target_price])
        if liquidity_2pct < trade_amount_usdt:
            return None, f"❌ Not enough liquidity 2% {pair}"

        # --- Profit ---
        trading_fee = trade_amount_usdt * 0.001
        coin_amount = trade_amount_usdt / gate_price
        net_profit = (mexc_price - gate_price) * coin_amount - trading_fee - WITHDRAWAL_FEE

        if spread > profit_threshold and net_profit > 0:
            message = (
                f"🚀 Arbitrage Opportunity!\n"
                f"{pair}\n"
                f"Buy Gate: {gate_price:.6f}, Sell MEXC: {mexc_price:.6f}\n"
                f"Spread: {spread:.2%}, Net Profit: ${net_profit:.2f}\n"
                f"Liquidity: ${liquidity_score:.2f}, 2%: ${liquidity_2pct:.2f}"
            )
            status_info["last_opportunity"] = {
                "pair": pair,
                "spread": spread,
                "net_profit": net_profit,
            }
            return message, None
        else:
            return None, f"No arbitrage {pair} spread {spread:.2%} net {net_profit:.2f}"

    except Exception as e:
        return None, f"❌ Error {pair}: {e}"

# ========== SCANNER ==========
def scanner():
    log("🚀 Scanner started...")
    while True:
        for pair in common_pairs:
            message, reason = filter_arbitrage_opportunity(pair, gate, mexc)
            status_info["last_checked"] = pair
            if message:
                try:
                    bot.send_message(CHAT_ID, message)
                    log(message)
                except Exception as e:
                    log(f"Telegram error: {e}")
            else:
                log(reason)
        time.sleep(10)

# ========== FASTAPI ==========
app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    html = f"""
    <html>
    <head>
        <title>Arbitrage Dashboard</title>
        <style>
            body {{ font-family: Arial; background:#f5f5f5; margin:40px; }}
            .card {{ background:white; padding:20px; border-radius:8px; margin-bottom:20px; }}
            h1 {{ color:#333; }}
            pre {{ max-height:400px; overflow:auto; background:#eee; padding:10px; }}
        </style>
    </head>
    <body>
        <h1>🚀 Arbitrage Scanner Dashboard</h1>
        <div class="card">
            <p><b>Pairs:</b> {len(common_pairs)}</p>
            <p><b>Last Checked:</b> {status_info.get("last_checked")}</p>
            <p><b>Last Opportunity:</b> {status_info.get("last_opportunity")}</p>
        </div>
        <div class="card">
            <h3>Logs (last {len(logs)})</h3>
            <pre>{"".join(logs)}</pre>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/status")
def get_status():
    return {
        "pairs": common_pairs,
        "last_checked": status_info.get("last_checked"),
        "last_opportunity": status_info.get("last_opportunity"),
    }

@app.get("/logs")
def get_logs():
    return JSONResponse(content={"logs": logs})

# ========== RUN ==========
if __name__ == "__main__":
    threading.Thread(target=scanner, daemon=True).start()
    threading.Thread(target=bot.polling, kwargs={"none_stop": True}, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8000)
