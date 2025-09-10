ArbiHunt Real - README
======================
Files in this zip:
- arbi_hunt_real.py    (main single-file bot)
- .env.template        (copy to .env and edit with your API keys/settings)
- README.txt           (this file)

Quick start:
1) Install dependencies:
   pip install ccxt

   pip install ccxt python-dotenv
   pip install pyTelegramBotAPI

python arbi_hunt_real.py

2) Copy .env.template -> .env and fill in your API keys and desired settings.
   Important: For live trading, set LIVE_MODE=True and PAPER_MODE=False.
   Start with PAPER_MODE=True while testing.
3) Run:
   

Safety notes:
- This script can place real orders. Only enable LIVE_MODE when you are sure.
- Start with small TRADE_USD_SIZE and PAPER_MODE=True to understand behaviour.
- Exchanges may restrict certain symbols for API trading (whitelist).
- The script does not implement full reconciliation/cancellation logic for partially filled orders.
- Use at your own risk. I am not responsible for financial losses.

python arbi_hunt_real.py


