import os
import sys
import argparse
from typing import Optional
from dotenv import load_dotenv

# Import rich elements for enhanced CLI UX
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import print as rprint

# Package imports
from bot.logging_config import setup_logging, logger
from bot.client import BinanceFuturesClient, BinanceAPIError, BinanceNetworkError
from bot.orders import OrderManager
from bot.validators import ValidationError

# Initialize Rich console
console = Console()

def load_credentials() -> tuple[Optional[str], Optional[str]]:
    """Loads API key and secret from environment or .env file."""
    # Find .env in project directory or parent directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(current_dir, ".env"))
    load_dotenv()  # Fallback to current working dir

    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    return api_key, api_secret

def print_banner():
    """Prints a beautiful bot banner."""
    banner = """
  [bold cyan]╦ ╦┌┬┐┌┬┐  ╔╗ ┬┌┐┌┌─┐┌┐┌┌─┐┌─┐  ╔╦╗┬─┐┌─┐┌┬┐┬┌┐┌┌─┐  ╔╗ ┌─┐┌┬┐[/bold cyan]
  [bold cyan]║ ║ ││ │   ╠╩╗││││├─┤││││  ├┤    ║ ├┬┘├─┤ │ ├││││ ┬  ╠╩╗│ │ │ [/bold cyan]
  [bold u]╚═╝─┴┘─┴┘  ╚═╝┴┘└┘┴ ┴┘└┘└─┘└─┘   ╩ ┴└─┴ ┴ ┴ ┴┘└┘└─┘  ╚═╝└─┘ ┴ [/bold u]
                   [dim]Binance Futures USDT-M Testnet CLI Bot[/dim]
    """
    console.print(banner)

def check_credentials_or_exit(api_key: Optional[str], api_secret: Optional[str]):
    """Checks if API credentials exist, otherwise prints a styled error and exits."""
    if not api_key or not api_secret:
        console.print(Panel(
            "[bold red]CRITICAL: API Credentials Missing![/bold red]\n\n"
            "Please set [yellow]BINANCE_API_KEY[/yellow] and [yellow]BINANCE_API_SECRET[/yellow] "
            "in your environment or create a [cyan].env[/cyan] file inside the project directory.\n\n"
            "Refer to the [cyan]README.md[/cyan] or use [cyan].env.template[/cyan] as a guide.",
            title="Authentication Error",
            border_style="red"
        ))
        sys.exit(1)

def display_balance(client: BinanceFuturesClient):
    """Fetches and displays available USDT balances in a styled table."""
    try:
        with console.status("[bold yellow]Fetching balances...", spinner="dots"):
            balances = client.get_account_balances()
        
        table = Table(title="Binance Futures USDT-M Balances", border_style="cyan")
        table.add_column("Asset", style="bold white")
        table.add_column("Wallet Balance", justify="right", style="green")
        table.add_column("Unrealized PNL", justify="right")
        table.add_column("Available Balance", justify="right", style="bold green")
        table.add_column("Margin Balance", justify="right")

        # Focus on USDT and BUSD/other key assets
        for bal in balances:
            asset = bal["asset"]
            wallet_bal = float(bal["walletBalance"])
            unrealized_pnl = float(bal["unrealizedProfit"])
            available = float(bal["availableBalance"])
            margin = float(bal["marginBalance"])

            # Highlight non-zero balances or common base assets
            if wallet_bal > 0 or asset in ["USDT", "BNB"]:
                pnl_color = "red" if unrealized_pnl < 0 else ("green" if unrealized_pnl > 0 else "white")
                pnl_str = f"[{pnl_color}]{unrealized_pnl:+.4f}[/{pnl_color}]"
                table.add_row(
                    asset,
                    f"{wallet_bal:.4f}",
                    pnl_str,
                    f"{available:.4f}",
                    f"{margin:.4f}"
                )
        
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error fetching balances:[/bold red] {e}")

def display_open_orders(client: BinanceFuturesClient, symbol: Optional[str] = None):
    """Fetches and displays open orders in a styled table."""
    try:
        with console.status("[bold yellow]Fetching open orders...", spinner="dots"):
            orders = client.get_open_orders(symbol)

        if not orders:
            console.print("[yellow]No open orders found.[/yellow]")
            return

        table = Table(title=f"Open Orders {f'({symbol.upper()})' if symbol else ''}", border_style="cyan")
        table.add_column("OrderId", style="dim")
        table.add_column("Symbol", style="bold white")
        table.add_column("Side", style="bold")
        table.add_column("Type")
        table.add_column("Price", justify="right")
        table.add_column("Stop Price", justify="right")
        table.add_column("Orig Qty", justify="right")
        table.add_column("Executed Qty", justify="right")

        for o in orders:
            side = o["side"]
            side_color = "green" if side == "BUY" else "red"
            side_str = f"[{side_color}]{side}[/{side_color}]"
            
            price = float(o.get("price", 0.0))
            stop_price = float(o.get("stopPrice", 0.0))
            orig_qty = float(o.get("origQty", 0.0))
            exec_qty = float(o.get("executedQty", 0.0))

            table.add_row(
                str(o["orderId"]),
                o["symbol"],
                side_str,
                o["type"],
                f"{price:.4f}" if price > 0 else "-",
                f"{stop_price:.4f}" if stop_price > 0 else "-",
                f"{orig_qty:.4f}",
                f"{exec_qty:.4f}"
            )
        
        console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error fetching open orders:[/bold red] {e}")

def handle_cli_order(args, client: BinanceFuturesClient):
    """Executes order placement command from argparse arguments."""
    check_credentials_or_exit(client.api_key, client.api_secret)
    manager = OrderManager(client)

    # Print summary of request
    console.print(Panel(
        f"[bold white]Symbol:[/bold white] {args.symbol.upper()}\n"
        f"[bold white]Side:[/bold white] {args.side.upper()}\n"
        f"[bold white]Type:[/bold white] {args.type.upper()}\n"
        f"[bold white]Quantity:[/bold white] {args.quantity}\n"
        f"[bold white]Price:[/bold white] {args.price if args.price is not None else 'N/A'}\n"
        f"[bold white]Stop Price:[/bold white] {args.stop_price if args.stop_price is not None else 'N/A'}",
        title="Order Request Summary",
        border_style="blue"
    ))

    try:
        with console.status("[bold yellow]Submitting order...", spinner="dots") as status:
            response = manager.execute_order(
                symbol=args.symbol,
                side=args.side,
                order_type=args.type,
                quantity=args.quantity,
                price=args.price,
                stop_price=args.stop_price
            )
        
        # Display response details
        avg_price = response.get("avgPrice")
        if not avg_price and "price" in response:
            avg_price = response.get("price")
            
        console.print(Panel(
            f"[bold green]✓ Order Placed Successfully![/bold green]\n\n"
            f"[bold white]Order ID:[/bold white] {response.get('orderId')}\n"
            f"[bold white]Status:[/bold white] {response.get('status')}\n"
            f"[bold white]Client Order ID:[/bold white] {response.get('clientOrderId')}\n"
            f"[bold white]Executed Quantity:[/bold white] {response.get('executedQty')}\n"
            f"[bold white]Average Executed Price:[/bold white] {avg_price} USDT\n"
            f"[bold white]Time in Force:[/bold white] {response.get('timeInForce')}",
            title="Binance Response Details",
            border_style="green"
        ))
    except (ValidationError, BinanceAPIError, BinanceNetworkError) as e:
        console.print(Panel(
            f"[bold red]✗ Order Placement Failed![/bold red]\n\n"
            f"[yellow]Reason:[/yellow] {e}",
            title="Error",
            border_style="red"
        ))
        sys.exit(1)

def run_interactive_mode(client: BinanceFuturesClient):
    """Runs a styled interactive CLI interface."""
    manager = OrderManager(client)
    print_banner()

    # Check connection
    console.print("[dim]Connecting to Binance Futures Testnet...[/dim]")
    if client.ping():
        console.print("[green]✓ Connected to Binance Futures Testnet server.[/green]")
    else:
        console.print("[bold red]✗ Connection failed. Please check your internet connection and Testnet status.[/bold red]")
        if not Confirm.ask("Do you want to continue anyway?"):
            sys.exit(1)

    while True:
        try:
            console.print("\n[bold cyan]Interactive Menu:[/bold cyan]")
            console.print("  [1] View USDT Balances")
            console.print("  [2] View Open Orders")
            console.print("  [3] Place New Order (MARKET/LIMIT/STOP_MARKET)")
            console.print("  [4] Cancel Open Order")
            console.print("  [5] Cancel All Open Orders for a Symbol")
            console.print("  [6] Sync Server Time")
            console.print("  [7] Exit")
            
            choice = Prompt.ask("\nChoose an option", choices=["1", "2", "3", "4", "5", "6", "7"], default="1")
            
            if choice == "1":
                check_credentials_or_exit(client.api_key, client.api_secret)
                display_balance(client)
                
            elif choice == "2":
                check_credentials_or_exit(client.api_key, client.api_secret)
                symbol_filter = Prompt.ask("Filter by symbol (e.g. BTCUSDT, or leave empty for all)", default="")
                display_open_orders(client, symbol_filter if symbol_filter else None)
                
            elif choice == "3":
                check_credentials_or_exit(client.api_key, client.api_secret)
                symbol = Prompt.ask("Enter Symbol (e.g. BTCUSDT)", default="BTCUSDT").upper()
                side = Prompt.ask("Select Side", choices=["BUY", "SELL"], default="BUY")
                order_type = Prompt.ask("Select Order Type", choices=["MARKET", "LIMIT", "STOP_MARKET"], default="MARKET")
                
                # Check validators to format output correctly and warn if necessary
                try:
                    quantity_str = Prompt.ask("Enter Quantity")
                    quantity = float(quantity_str)
                except ValueError:
                    console.print("[bold red]Invalid number format for quantity.[/bold red]")
                    continue

                price = None
                if order_type == "LIMIT":
                    try:
                        price_str = Prompt.ask("Enter Limit Price (USDT)")
                        price = float(price_str)
                    except ValueError:
                        console.print("[bold red]Invalid number format for price.[/bold red]")
                        continue

                stop_price = None
                if order_type == "STOP_MARKET":
                    try:
                        stop_str = Prompt.ask("Enter Stop Price (USDT)")
                        stop_price = float(stop_str)
                    except ValueError:
                        console.print("[bold red]Invalid number format for stop price.[/bold red]")
                        continue

                # Review Order summary
                console.print(Panel(
                    f"[bold white]Symbol:[/bold white] {symbol}\n"
                    f"[bold white]Side:[/bold white] {side}\n"
                    f"[bold white]Type:[/bold white] {order_type}\n"
                    f"[bold white]Quantity:[/bold white] {quantity}\n"
                    f"[bold white]Price:[/bold white] {price if price is not None else 'N/A'}\n"
                    f"[bold white]Stop Price:[/bold white] {stop_price if stop_price is not None else 'N/A'}",
                    title="Order Placement Summary",
                    border_style="yellow"
                ))

                if not Confirm.ask("Do you want to submit this order?"):
                    console.print("[yellow]Order aborted by user.[/yellow]")
                    continue

                try:
                    with console.status("[bold yellow]Placing order...", spinner="dots"):
                        response = manager.execute_order(
                            symbol=symbol,
                            side=side,
                            order_type=order_type,
                            quantity=quantity,
                            price=price,
                            stop_price=stop_price
                        )
                    
                    avg_price = response.get("avgPrice")
                    if not avg_price and "price" in response:
                        avg_price = response.get("price")

                    console.print(Panel(
                        f"[bold green]✓ Order Placed Successfully![/bold green]\n\n"
                        f"[bold white]Order ID:[/bold white] {response.get('orderId')}\n"
                        f"[bold white]Status:[/bold white] {response.get('status')}\n"
                        f"[bold white]Executed Quantity:[/bold white] {response.get('executedQty')}\n"
                        f"[bold white]Average Price:[/bold white] {avg_price} USDT",
                        title="Success",
                        border_style="green"
                    ))
                except (ValidationError, BinanceAPIError, BinanceNetworkError) as e:
                    console.print(Panel(
                        f"[bold red]✗ Order Placement Failed![/bold red]\n\n"
                        f"[yellow]Reason:[/yellow] {e}",
                        title="Error",
                        border_style="red"
                    ))
                    
            elif choice == "4":
                check_credentials_or_exit(client.api_key, client.api_secret)
                symbol = Prompt.ask("Enter Symbol (e.g. BTCUSDT)", default="BTCUSDT").upper()
                order_id_str = Prompt.ask("Enter Order ID to cancel")
                try:
                    order_id = int(order_id_str)
                    with console.status(f"[bold yellow]Canceling order {order_id}...", spinner="dots"):
                        res = client.cancel_order(symbol, order_id)
                    console.print(f"[bold green]✓ Order {order_id} cancelled. Status: {res.get('status')}[/bold green]")
                except ValueError:
                    console.print("[bold red]Order ID must be a valid integer.[/bold red]")
                except Exception as e:
                    console.print(f"[bold red]Failed to cancel order:[/bold red] {e}")
                    
            elif choice == "5":
                check_credentials_or_exit(client.api_key, client.api_secret)
                symbol = Prompt.ask("Enter Symbol (e.g. BTCUSDT)", default="BTCUSDT").upper()
                if Confirm.ask(f"Are you sure you want to cancel ALL open orders for {symbol}?"):
                    try:
                        with console.status(f"[bold yellow]Canceling all open orders for {symbol}...", spinner="dots"):
                            client.cancel_all_open_orders(symbol)
                        console.print(f"[bold green]✓ All open orders for {symbol} cancelled successfully.[/bold green]")
                    except Exception as e:
                        console.print(f"[bold red]Failed to cancel all open orders:[/bold red] {e}")

            elif choice == "6":
                client.sync_time()
                console.print(f"[green]✓ Time synchronized with server. Offset: {client.time_offset_ms} ms[/green]")

            elif choice == "7":
                console.print("[bold cyan]Goodbye![/bold cyan]")
                break

        except KeyboardInterrupt:
            console.print("\n[yellow]Menu interrupted. Returning to menu...[/yellow]")
        except Exception as e:
            console.print(f"[bold red]An unexpected error occurred:[/bold red] {e}")
            logger.exception("Unexpected error in CLI loop")

def main():
    """Main program entry point."""
    # Setup default logging configuration
    setup_logging()

    # Load keys
    api_key, api_secret = load_credentials()
    
    parser = argparse.ArgumentParser(
        description="Binance Futures USDT-M Testnet Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start interactive menu mode
  python cli.py
  
  # Check available balance
  python cli.py balance

  # Place a MARKET BUY order
  python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.002

  # Place a LIMIT SELL order
  python cli.py place --symbol ETHUSDT --side SELL --type LIMIT --quantity 0.05 --price 4000
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")
    
    # Parser for interactive
    subparsers.add_parser("interactive", help="Start the interactive menu (default)")
    
    # Parser for balance
    subparsers.add_parser("balance", help="Display USDT asset balance")
    
    # Parser for open-orders
    open_parser = subparsers.add_parser("open-orders", help="Display all active open orders")
    open_parser.add_argument("--symbol", type=str, help="Filter open orders by symbol (e.g. BTCUSDT)")
    
    # Parser for cancel
    cancel_parser = subparsers.add_parser("cancel", help="Cancel an active open order")
    cancel_parser.add_argument("--symbol", type=str, required=True, help="Symbol of the order (e.g. BTCUSDT)")
    cancel_parser.add_argument("--order-id", type=int, required=True, help="ID of the order to cancel")

    # Parser for placing order
    place_parser = subparsers.add_parser("place", help="Submit a new order")
    place_parser.add_argument("--symbol", type=str, required=True, help="Symbol to trade (e.g. BTCUSDT)")
    place_parser.add_argument("--side", type=str, required=True, choices=["BUY", "SELL"], help="Order side (BUY or SELL)")
    place_parser.add_argument("--type", type=str, required=True, choices=["MARKET", "LIMIT", "STOP_MARKET"], help="Order type")
    place_parser.add_argument("--quantity", type=float, required=True, help="Order quantity")
    place_parser.add_argument("--price", type=float, help="Limit price (Required for LIMIT order)")
    place_parser.add_argument("--stop-price", type=float, help="Trigger price (Required for STOP_MARKET order)")

    args = parser.parse_args()

    # Initialize client
    client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret)

    # Dispatch command
    try:
        if args.command is None or args.command == "interactive":
            run_interactive_mode(client)
        elif args.command == "balance":
            check_credentials_or_exit(api_key, api_secret)
            display_balance(client)
        elif args.command == "open-orders":
            check_credentials_or_exit(api_key, api_secret)
            display_open_orders(client, args.symbol)
        elif args.command == "cancel":
            check_credentials_or_exit(api_key, api_secret)
            with console.status(f"[bold yellow]Canceling order {args.order_id} for {args.symbol}...", spinner="dots"):
                res = client.cancel_order(args.symbol.upper(), args.order_id)
            console.print(f"[bold green]✓ Order {args.order_id} cancelled. Status: {res.get('status')}[/bold green]")
        elif args.command == "place":
            handle_cli_order(args, client)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation aborted by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]Command failed with error:[/bold red] {e}")
        logger.exception("Exception occurred in command dispatcher")
        sys.exit(1)

if __name__ == "__main__":
    main()
