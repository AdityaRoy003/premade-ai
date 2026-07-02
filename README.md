Binance Futures Testnet Trading Bot
A structured Python 3 application designed to place orders (MARKET, LIMIT, STOP_MARKET) on the Binance Futures USDT-M Testnet with real-time input validations (lot size, tick size, step size, and minimum notional value) and a premium, styled console user interface.

Features
Robust REST Client: Direct connection to the Binance Futures Testnet (https://testnet.binancefuture.com) using Python's requests library.
Clock Drift Synchronization: Automatically calculates latency and synchronizes the client clock with the Binance Futures server time to prevent signature/timestamp rejects.
Strict Parameter Validation: Validates inputs offline against rules from /fapi/v1/exchangeInfo:
Quantizes trading quantities according to the asset's stepSize and limits (minQty/maxQty).
Quantizes prices according to the asset's tickSize and limits (minPrice/maxPrice).
Rejects orders below the asset's MIN_NOTIONAL value.
Wallet Balance Warning: Queries your available USDT balance to notify you if you have insufficient funds (at 1x leverage) before transmitting the order.
Double CLI Interfaces:
Argparse CLI: Direct, one-shot commands for automation or script integration.
Rich Interactive UI: A full console menu featuring colored tables, loaders, and input forms.
Dual Logging: Writes clean user status logs to the console and detailed debug execution trails (including masked signatures and raw API payloads) to trading_bot.log.
Project Structure
trading_bot/
│
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance REST client (auth, requests, sync)
│   ├── orders.py          # Order execution and manager orchestration
│   ├── validators.py      # Real-time exchange parameter input validators
│   └── logging_config.py  # Dual file and console logging configuration
│
├── .env.template          # Sample configuration template
├── cli.py                 # Main CLI and interactive menu entry point
├── README.md              # Documentation and instructions
└── requirements.txt       # Project dependencies
Setup Instructions
1. Prerequisites
Make sure you have Python 3.8 or higher installed. Check your version with:

python --version
2. Generate Binance Futures Testnet Credentials
Register and log in to the Binance Futures Testnet Sandbox.
Locate your Mock Trading API Key and Secret Key on the dashboard.
3. Clone and Navigate to the Repository
Open a terminal and navigate to the directory where the bot files are saved:

cd trading_bot
4. Install Dependencies
Install the required libraries (requests, python-dotenv, and rich):

pip install -r requirements.txt
5. Setup Environment Variables
Copy the template configuration file to a new file named .env:

cp .env.template .env
(On Windows PowerShell, use copy .env.template .env)

Open the .env file and replace the placeholders with your actual API key and secret key:

BINANCE_API_KEY=your_actual_testnet_api_key_here
BINANCE_API_SECRET=your_actual_testnet_api_secret_here
How to Run
The bot supports two modes: Interactive Mode (recommended for visual usage) and Direct CLI Mode (best for automation).

Mode A: Interactive Dashboard (Recommended)
Simply run the script without any arguments. This launches a beautiful console menu:

python cli.py
Interactive Features:

USDT Balances: Displays non-zero assets and available margins in a clean table.
Open Orders: Queries and displays active limit/stop orders.
New Order: Guided prompt that validates your quantity and price dynamically, showing warnings if your parameters violate limits or if your balance is too low.
Cancel Order: Enter an Order ID to cancel it.
Cancel All: Cancel all open orders for a specific symbol instantly.
Clock Sync: Forces a fresh time synchronization with the Binance server.
Mode B: Direct CLI Commands
You can run subcommands directly from your terminal.

1. Check Balances
python cli.py balance
2. Check Open Orders
# View all open orders
python cli.py open-orders

# Filter open orders by symbol
python cli.py open-orders --symbol BTCUSDT
3. Place a MARKET Order
Places a market order immediately. Note: Binance USDT-M testnet symbols have minimum notional limits (usually 50 USDT or equivalent). Adjust quantity accordingly.

# BUY Market Order
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.002

# SELL Market Order
python cli.py place --symbol BTCUSDT --side SELL --type MARKET --quantity 0.002
4. Place a LIMIT Order
Places a limit order (price required).

# BUY Limit Order (places order to buy 0.002 BTC at 55,000 USDT)
python cli.py place --symbol BTCUSDT --side BUY --type LIMIT --quantity 0.002 --price 55000

# SELL Limit Order (places order to sell 0.002 BTC at 100,000 USDT)
python cli.py place --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.002 --price 100000
5. Place a STOP_MARKET Order
Places a trigger stop order (stop-price required).

# STOP SELL Order (protects long position if price drops below 58,000)
python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.002 --stop-price 58000
6. Cancel an Order
Cancels a specific active order using the order ID returned during placement:

python cli.py cancel --symbol BTCUSDT --order-id 12345678
Log Outputs
File Log: Detailed runtime execution details are written to trading_bot.log. It lists client connections, calculated clock drift values, the signed queries, and raw JSON payloads returned from the API.
Credentials Masking: To ensure security, the bot masks your API key and secret key in all outputs and files:
Console: API Key displays as API Key: abc123...89yz
File Log: Raw API secret is never logged, and the API key is masked as abc12...89yz.
Troubleshooting & Assumptions
Min Notional Value: If you get a validation error warning that "order notional value is below the minimum required (50.00 USDT)", it means your quantity * price is too low. In Binance Futures, contracts have a minimum size requirements. Increase the quantity.
Precision Rejections: The bot automatically aligns and truncates decimals based on exchange specs (e.g., BTCUSDT quantity is quantized to 3 decimal places, ETHUSDT to 2). If you input custom decimals (e.g., 0.00257), the bot will safely submit 0.002 rather than erroring out.
System Clock Out of Sync: The client performs synchronization on start. If your system clock is drastically off, the calculated offset will automatically correct timestamps sent to the API.
