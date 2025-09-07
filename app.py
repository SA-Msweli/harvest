#!/usr/bin/env python3
"""
Comprehensive Stellar Smart Harvest Bot
Advanced DeFi automation with multiple strategies and risk management
"""

import json
import time
import logging
import requests
import os
import sys
import sqlite3
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from stellar_sdk import Server, Keypair, TransactionBuilder, Network, Asset
from stellar_sdk.exceptions import NotFoundError, BadResponseError
from apscheduler.schedulers.background import BackgroundScheduler
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from apscheduler.triggers.cron import CronTrigger

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
CONFIG_FILE = "config.json"
LOG_FILE = "harvest_bot.log"
KEY_FILE = "secret.key"
DB_FILE = "harvest_bot.db"

# Global variables
bot_status = "stopped"
logs = []
scheduler = BackgroundScheduler()
current_prices = {}
portfolio_value = 0
last_harvest_time = None
config_complete = False
strategies = {}
performance_metrics = {}

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("StellarHarvestBot")

# Database setup
def init_db():
    """Initialize the database for storing transactions and performance data"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Create tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_hash TEXT UNIQUE,
            asset TEXT,
            action TEXT,
            amount REAL,
            price REAL,
            timestamp DATETIME,
            status TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME,
            portfolio_value REAL,
            daily_yield REAL,
            total_yield REAL
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset TEXT,
            price REAL,
            timestamp DATETIME
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

class PriceOracle:
    """Unified price oracle with multiple data sources"""
    
    def __init__(self, network):
        self.network = network
        self.horizon_server = Server(horizon_url="https://horizon-testnet.stellar.org" if network == Network.TESTNET_NETWORK_PASSPHRASE else "https://horizon.stellar.org")
        self.sources = [
            self.get_price_from_horizon,
            self.get_price_from_stellarx,
            self.get_price_from_lumenswap
        ]
        
    def get_price(self, base_asset, quote_asset="USD"):
        """Get price from multiple sources with fallback"""
        for source in self.sources:
            try:
                price = source(base_asset, quote_asset)
                if price and price > 0:
                    # Store price in history
                    self.store_price_history(base_asset, price)
                    return price
            except Exception as e:
                logger.warning(f"Price source failed: {e}")
                continue
                
        logger.warning("All price sources failed, using default price")
        return 1.0  # Safe default

    def get_price_from_horizon(self, base_asset, quote_asset):
        """Get price from Horizon using orderbook data"""
        try:
            if base_asset == "XLM":
                base_asset_obj = Asset.native()
            else:
                # For other assets, we need to know the issuer
                if ":" in base_asset:
                    asset_code, asset_issuer = base_asset.split(":")
                    base_asset_obj = Asset(asset_code, asset_issuer)
                else:
                    # Default to KALE if no issuer specified
                    base_asset_obj = Asset(base_asset, "CA3D5KRYM6CB7OWQ6TWYRR3Z4T7GNZLKERYNZGGA5SOAOPIFY6YQGAXE")
            
            if quote_asset == "XLM":
                quote_asset_obj = Asset.native()
            else:
                # For USD, we'll use a stablecoin
                quote_asset_obj = Asset("USDC", "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN")
            
            orderbook = self.horizon_server.orderbook(base_asset_obj, quote_asset_obj).call()
            if orderbook['bids']:
                return float(orderbook['bids'][0]['price'])
                
        except Exception as e:
            logger.error(f"Error getting price from Horizon: {e}")
        return None

    def get_price_from_stellarx(self, base_asset, quote_asset):
        """Get price from StellarX API"""
        try:
            # This is a placeholder - StellarX might have a different API
            # In a real implementation, you would use their actual API
            url = f"https://api.stellarx.com/price/{base_asset}/{quote_asset}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return float(data.get('price', 0))
        except:
            pass
        return None

    def get_price_from_lumenswap(self, base_asset, quote_asset):
        """Get price from Lumenswap API"""
        try:
            # This is a placeholder - Lumenswap might have a different API
            url = f"https://api.lumenswap.com/price/{base_asset}/{quote_asset}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return float(data.get('price', 0))
        except:
            pass
        return None

    def store_price_history(self, asset, price):
        """Store price in history database"""
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO price_history (asset, price, timestamp) VALUES (?, ?, ?)",
                     (asset, price, datetime.now()))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error storing price history: {e}")

    def get_price_history(self, asset, hours=24):
        """Get price history for an asset"""
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            since = datetime.now() - timedelta(hours=hours)
            c.execute("SELECT price, timestamp FROM price_history WHERE asset = ? AND timestamp > ? ORDER BY timestamp",
                     (asset, since))
            data = c.fetchall()
            conn.close()
            return data
        except Exception as e:
            logger.error(f"Error getting price history: {e}")
            return []

class StrategyEngine:
    """Strategy engine for implementing different trading strategies"""
    
    def __init__(self, config):
        self.config = config
        self.strategies = {
            "simple_threshold": self.simple_threshold_strategy,
            "moving_average": self.moving_average_strategy,
            "rsi": self.rsi_strategy,
            "volatility": self.volatility_strategy
        }
    
    def evaluate(self, asset_config, price_data):
        """Evaluate which strategy to use and return trade signal"""
        strategy_name = asset_config.get('strategy', 'simple_threshold')
        strategy_func = self.strategies.get(strategy_name, self.simple_threshold_strategy)
        
        return strategy_func(asset_config, price_data)
    
    def simple_threshold_strategy(self, asset_config, price_data):
        """Simple threshold-based strategy"""
        current_price = price_data[-1][0] if price_data else 0
        threshold = asset_config.get('threshold_price', 1.0)
        
        if current_price >= threshold:
            return "BUY"
        return "HOLD"
    
    def moving_average_strategy(self, asset_config, price_data):
        """Moving average crossover strategy"""
        if len(price_data) < 20:  # Need enough data
            return "HOLD"
            
        prices = [p[0] for p in price_data]
        short_ma = sum(prices[-10:]) / 10  # 10-period MA
        long_ma = sum(prices[-20:]) / 20   # 20-period MA
        
        if short_ma > long_ma:
            return "BUY"
        return "HOLD"
    
    def rsi_strategy(self, asset_config, price_data):
        """RSI-based strategy"""
        if len(price_data) < 15:  # Need enough data
            return "HOLD"
            
        prices = [p[0] for p in price_data]
        
        # Calculate RSI
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(losses[-14:]) / 14
        
        if avg_loss == 0:
            rsi = 100
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
        
        # RSI strategy logic
        if rsi < 30:  # Oversold
            return "BUY"
        elif rsi > 70:  # Overbought
            return "SELL"
        return "HOLD"
    
    def volatility_strategy(self, asset_config, price_data):
        """Volatility-based strategy"""
        if len(price_data) < 10:  # Need enough data
            return "HOLD"
            
        prices = [p[0] for p in price_data]
        returns = []
        
        for i in range(1, len(prices)):
            returns.append((prices[i] - prices[i-1]) / prices[i-1])
        
        volatility = np.std(returns) * np.sqrt(365)  # Annualized volatility
        
        if volatility < asset_config.get('max_volatility', 0.5):  # 50% max volatility
            return "BUY"
        return "HOLD"

class PortfolioManager:
    """Portfolio management system"""
    
    def __init__(self, server, keypair):
        self.server = server
        self.keypair = keypair
        self.portfolio = {}
    
    def update_portfolio(self):
        """Update portfolio balances"""
        try:
            account = self.server.accounts().account_id(self.keypair.public_key).call()
            balances = account['balances']
            
            for balance in balances:
                if balance['asset_type'] == 'native':
                    self.portfolio['XLM'] = {
                        'balance': float(balance['balance']),
                        'value': float(balance['balance'])  # Will be updated with price
                    }
                else:
                    asset_code = balance['asset_code']
                    self.portfolio[asset_code] = {
                        'balance': float(balance['balance']),
                        'value': float(balance['balance'])  # Will be updated with price
                    }
                    
            return True
        except Exception as e:
            logger.error(f"Error updating portfolio: {e}")
            return False
    
    def calculate_portfolio_value(self, price_oracle):
        """Calculate total portfolio value"""
        total_value = 0
        
        for asset, data in self.portfolio.items():
            if asset == 'XLM':
                price = price_oracle.get_price('XLM', 'USD')
            else:
                price = price_oracle.get_price(asset, 'USD')
                
            if price:
                asset_value = data['balance'] * price
                self.portfolio[asset]['value'] = asset_value
                self.portfolio[asset]['price'] = price
                total_value += asset_value
        
        return total_value
    
    def get_performance_metrics(self):
        """Calculate performance metrics"""
        # This would typically compare current value to historical values
        # For simplicity, we'll return some basic metrics
        return {
            'total_value': sum(asset['value'] for asset in self.portfolio.values()),
            'asset_allocation': {asset: data['value'] for asset, data in self.portfolio.items()}
        }

class NotificationManager:
    """Notification system for alerts and updates"""
    
    def __init__(self, config):
        self.config = config
        self.notification_methods = []
        
        # Setup notification methods based on config
        if config.get('email_notifications', False):
            self.notification_methods.append(self.send_email)
        
        if config.get('telegram_notifications', False):
            self.notification_methods.append(self.send_telegram_message)
    
    def notify(self, message, level="INFO"):
        """Send notification through all configured methods"""
        for method in self.notification_methods:
            try:
                method(message, level)
            except Exception as e:
                logger.error(f"Notification method failed: {e}")
    
    def send_email(self, message, level):
        """Send email notification"""
        # Implementation would use SMTP or a service like SendGrid
        logger.info(f"Email notification ({level}): {message}")
    
    def send_telegram_message(self, message, level):
        """Send Telegram notification"""
        # Implementation would use the Telegram Bot API
        logger.info(f"Telegram notification ({level}): {message}")

class StellarHarvestBot:
    def __init__(self):
        # Initialize strategies
        self.strategies = {'KALE': 'simple_threshold'}
        self.config = self.load_config()
        self.setup_strategies()
        self.notification_manager = NotificationManager(self.config)

        self.keypair = self.load_keypair()
        self.server = Server(horizon_url=self.config['horizon_url'])
        self.network = Network.TESTNET_NETWORK_PASSPHRASE if self.config['network'] == 'testnet' else Network.PUBLIC_NETWORK_PASSPHRASE
        self.price_oracle = PriceOracle(self.network)
        self.portfolio_manager = PortfolioManager(self.server, self.keypair)
        self.strategy_engine = StrategyEngine(self.config)
        
        
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            if not os.path.exists(CONFIG_FILE) or os.path.getsize(CONFIG_FILE) == 0:
                return self.create_default_config()
                
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                
            # Set defaults for new config options
            defaults = {
                "slippage_tolerance": 0.01,
                "max_retries": 3,
                "health_check_interval": 300,
                "email_notifications": False,
                "telegram_notifications": False,
                "max_volatility": 0.5,
                "assets": [
                    {
                        "name": "KALE",
                        "contract_id": "CA3D5KRYM6CB7OWQ6TWYRR3Z4T7GNZLKERYNZGGA5SOAOPIFY6YQGAXE",
                        "threshold_price": 1.05,
                        "strategy": "simple_threshold",
                        "allocation": 0.5  # 50% of portfolio
                    }
                ]
            }
            
            for key, value in defaults.items():
                if key not in config:
                    config[key] = value
                    
            return config
        except json.JSONDecodeError:
            logger.error("Config file contains invalid JSON, creating default config")
            return self.create_default_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self.create_default_config()

    def create_default_config(self):
        """Create default configuration file"""
        default_config = {
            "network": "testnet",
            "horizon_url": "https://horizon-testnet.stellar.org",
            "asset_pair": "KALE/USD",
            "threshold_price": 1.05,
            "kale_contract_id": "CA3D5KRYM6CB7OWQ6TWYRR3Z4T7GNZLKERYNZGGA5SOAOPIFY6YQGAXE",
            "reflector_asset": "KALE",
            "reflector_quote_asset": "USD",
            "schedule_interval": 30,
            "min_balance": 2.0,
            "slippage_tolerance": 0.01,
            "max_retries": 3,
            "health_check_interval": 300,
            "email_notifications": False,
            "telegram_notifications": False,
            "max_volatility": 0.5,
            "assets": [
                {
                    "name": "KALE",
                    "contract_id": "CA3D5KRYM6CB7OWQ6TWYRR3Z4T7GNZLKERYNZGGA5SOAOPIFY6YQGAXE",
                    "threshold_price": 1.05,
                    "strategy": "simple_threshold",
                    "allocation": 0.5
                }
            ]
        }
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        
        return default_config

    def save_config(self, new_config):
        """Save configuration to JSON file"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(new_config, f, indent=4)
        self.config = new_config

    def encrypt_key(self, private_key):
        """Encrypt private key for secure storage"""
        if not os.path.exists(KEY_FILE):
            key = Fernet.generate_key()
            with open(KEY_FILE, 'wb') as f:
                f.write(key)
        else:
            with open(KEY_FILE, 'rb') as f:
                key = f.read()
                
        try:
            fernet = Fernet(key)
        except ValueError:
            key = Fernet.generate_key()
            with open(KEY_FILE, 'wb') as f:
                f.write(key)
            fernet = Fernet(key)
        
        return fernet.encrypt(private_key.encode()).decode()

    def decrypt_key(self, encrypted_key):
        """Decrypt private key"""
        if not os.path.exists(KEY_FILE):
            raise Exception("No encryption key found")
            
        with open(KEY_FILE, 'rb') as f:
            key = f.read()
        
        try:
            fernet = Fernet(key)
        except ValueError:
            raise Exception("Invalid encryption key found")
        
        return fernet.decrypt(encrypted_key.encode()).decode()

    def load_keypair(self):
        """Load or create Stellar keypair"""
        if 'encrypted_private_key' in self.config and self.config['encrypted_private_key']:
            try:
                private_key = self.decrypt_key(self.config['encrypted_private_key'])
                return Keypair.from_secret(private_key)
            except Exception as e:
                logger.error(f"Failed to decrypt private key: {e}")
                return None
        else:
            keypair = Keypair.random()
            encrypted_key = self.encrypt_key(keypair.secret)
            self.config['encrypted_private_key'] = encrypted_key
            self.save_config(self.config)
            
            if self.config['network'] == 'testnet':
                self.fund_account(keypair)
                
            return keypair

    def fund_account(self, keypair):
        """Fund account using Friendbot on Testnet"""
        try:
            response = requests.get(f"https://friendbot.stellar.org?addr={keypair.public_key}")
            if response.status_code == 200:
                logger.info(f"Account {keypair.public_key} funded successfully")
                self.notification_manager.notify(f"Account {keypair.public_key} funded successfully")
            else:
                logger.error(f"Failed to fund account: {response.text}")
        except Exception as e:
            logger.error(f"Error funding account: {e}")

    def get_account_balance(self):
        """Get current account balance"""
        try:
            account = self.server.accounts().account_id(self.keypair.public_key).call()
            balances = account['balances']
            for balance in balances:
                if balance['asset_type'] == 'native':
                    return float(balance['balance'])
            return 0
        except NotFoundError:
            logger.error("Account not found on the network")
            return 0
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return 0

    def setup_strategies(self):
        """Setup trading strategies based on config"""
        for asset in self.config.get('assets', []):
            strategy_name = asset.get('strategy', 'simple_threshold')
            self.strategies[asset['name']] = strategy_name
            logger.info(f"Setup {strategy_name} strategy for {asset['name']}")

    def invoke_harvest_contract(self, asset_config):
        """Invoke the harvest function on the KALE contract"""
        try:
            account = self.server.load_account(self.keypair.public_key)
            
            transaction = (
                TransactionBuilder(
                    source_account=account,
                    network_passphrase=self.network,
                    base_fee=100
                )
                .append_invoke_contract_function_op(
                    contract_id=asset_config['contract_id'],
                    function_name="harvest",
                    parameters=[],
                    source=self.keypair.public_key
                )
                .set_timeout(30)
                .build()
            )
            
            transaction.sign(self.keypair)
            response = self.server.submit_transaction(transaction)
            
            logger.info(f"Harvest transaction successful: {response['hash']}")
            
            # Store transaction in database
            self.store_transaction(
                response['hash'],
                asset_config['name'],
                "HARVEST",
                0,  # Amount not available from harvest
                self.price_oracle.get_price(asset_config['name'], 'USD'),
                "SUCCESS"
            )
            
            self.notification_manager.notify(f"Harvest executed for {asset_config['name']}. TX: {response['hash']}")
            
            return True, response['hash']
        except Exception as e:
            logger.error(f"Error invoking harvest contract: {e}")
            
            # Store failed transaction
            self.store_transaction(
                "FAILED",
                asset_config['name'],
                "HARVEST",
                0,
                self.price_oracle.get_price(asset_config['name'], 'USD'),
                "FAILED"
            )
            
            self.notification_manager.notify(f"Harvest failed for {asset_config['name']}: {str(e)}", "ERROR")
            
            return False, str(e)

    def store_transaction(self, tx_hash, asset, action, amount, price, status):
        """Store transaction in database"""
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO transactions (tx_hash, asset, action, amount, price, timestamp, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (tx_hash, asset, action, amount, price, datetime.now(), status))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error storing transaction: {e}")

    def check_and_harvest(self):
        """Check price and execute harvest if conditions are met"""
        global current_prices, last_harvest_time, portfolio_value
        
        try:
            # Update portfolio
            self.portfolio_manager.update_portfolio()
            portfolio_value = self.portfolio_manager.calculate_portfolio_value(self.price_oracle)
            
            # Store performance metrics
            self.store_performance_metrics(portfolio_value)
            
            # Check if we have sufficient balance
            balance = self.get_account_balance()
            if balance < self.config['min_balance']:
                logger.warning(f"Insufficient balance: {balance} XLM. Minimum required: {self.config['min_balance']} XLM")
                self.notification_manager.notify(f"Insufficient balance: {balance} XLM", "WARNING")
                return
            
            # Check each asset for harvest opportunities
            for asset_config in self.config.get('assets', []):
                asset_name = asset_config['name']
                
                # Get current price
                current_price = self.price_oracle.get_price(asset_name, 'USD')
                current_prices[asset_name] = current_price
                
                # Get price history for strategy evaluation
                price_history = self.price_oracle.get_price_history(asset_name, hours=24)
                
                # Evaluate strategy
                signal = self.strategy_engine.evaluate(asset_config, price_history)
                
                logger.info(f"Asset: {asset_name}, Price: {current_price}, Signal: {signal}")
                
                # Execute based on signal
                if signal == "BUY":
                    logger.info(f"Buy signal for {asset_name}, executing harvest...")
                    
                    for attempt in range(self.config['max_retries']):
                        success, result = self.invoke_harvest_contract(asset_config)
                        if success:
                            last_harvest_time = time.time()
                            logger.info(f"Harvest executed successfully. TX Hash: {result}")
                            break
                        else:
                            logger.error(f"Attempt {attempt + 1} failed: {result}")
                            if attempt < self.config['max_retries'] - 1:
                                time.sleep(2)
                    else:
                        logger.error("All harvest attempts failed")
                else:
                    logger.info(f"No action signal for {asset_name}")
                    
        except Exception as e:
            logger.error(f"Error in check_and_harvest: {e}")
            self.notification_manager.notify(f"Error in check_and_harvest: {str(e)}", "ERROR")

    def store_performance_metrics(self, portfolio_value):
        """Store performance metrics in database"""
        try:
            # Calculate daily yield (simplified)
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            
            # Get yesterday's value
            yesterday = datetime.now() - timedelta(days=1)
            c.execute("SELECT portfolio_value FROM performance WHERE timestamp > ? ORDER BY timestamp DESC LIMIT 1", 
                     (yesterday,))
            result = c.fetchone()
            
            daily_yield = 0
            if result:
                yesterday_value = result[0]
                daily_yield = ((portfolio_value - yesterday_value) / yesterday_value) * 100 if yesterday_value > 0 else 0
            
            # Store current performance
            c.execute("INSERT INTO performance (timestamp, portfolio_value, daily_yield, total_yield) VALUES (?, ?, ?, ?)",
                     (datetime.now(), portfolio_value, daily_yield, daily_yield))  # Simplified total yield
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error storing performance metrics: {e}")

    def is_config_complete(self):
        """Check if configuration is complete"""
        required_fields = ['kale_contract_id', 'encrypted_private_key']
        for field in required_fields:
            if not self.config.get(field):
                return False
        return True

    def get_transaction_history(self, limit=10):
        """Get recent transactions for the account"""
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT * FROM transactions ORDER BY timestamp DESC LIMIT ?", (limit,))
            transactions = c.fetchall()
            conn.close()
            return transactions
        except Exception as e:
            logger.error(f"Error getting transaction history: {e}")
            return []

    def get_performance_history(self, days=7):
        """Get performance history"""
        try:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            since = datetime.now() - timedelta(days=days)
            c.execute("SELECT timestamp, portfolio_value, daily_yield FROM performance WHERE timestamp > ? ORDER BY timestamp", 
                     (since,))
            performance = c.fetchall()
            conn.close()
            return performance
        except Exception as e:
            logger.error(f"Error getting performance history: {e}")
            return []

    def backtest_strategy(self, asset_config, days=30):
        """Backtest a strategy on historical data"""
        try:
            # Get historical price data
            price_history = self.price_oracle.get_price_history(asset_config['name'], hours=24*days)
            
            if not price_history or len(price_history) < 10:
                return {"error": "Not enough historical data"}
            
            # Simulate strategy
            signals = []
            profits = []
            balance = 1000  # Starting balance
            position = 0
            
            for i in range(10, len(price_history)):
                current_data = price_history[:i]
                signal = self.strategy_engine.evaluate(asset_config, current_data)
                signals.append(signal)
                
                current_price = price_history[i][0]
                
                # Simulate trades
                if signal == "BUY" and position == 0:
                    position = balance / current_price
                    balance = 0
                elif signal == "SELL" and position > 0:
                    balance = position * current_price
                    position = 0
                    
                profits.append(balance + (position * current_price if position > 0 else 0))
            
            # Calculate metrics
            final_value = balance + (position * price_history[-1][0] if position > 0 else 0)
            total_return = ((final_value - 1000) / 1000) * 100
            
            return {
                "final_value": final_value,
                "total_return": total_return,
                "signals": signals,
                "equity_curve": profits
            }
            
        except Exception as e:
            logger.error(f"Error in backtest: {e}")
            return {"error": str(e)}

# Initialize bot
try:
    bot = StellarHarvestBot()
    config_complete = bot.is_config_complete()
    
    if config_complete and bot_status == "stopped":
        interval = bot.config['schedule_interval']
        scheduler.add_job(bot.check_and_harvest, 'interval', seconds=interval, id='harvest_job')
        
        # Add health check job
        scheduler.add_job(
            lambda: logger.info("Bot health check: OK"), 
            'interval', 
            seconds=bot.config.get('health_check_interval', 300), 
            id='health_check_job'
        )
        
        # Add portfolio update job
        scheduler.add_job(
            bot.portfolio_manager.update_portfolio,
            'interval',
            minutes=5,
            id='portfolio_update_job'
        )
        
        if not scheduler.running:
            scheduler.start()
        bot_status = "running"
        logger.info("Bot started automatically due to complete config")
        
except Exception as e:
    logger.error(f"Failed to initialize bot: {e}")
    class DummyBot:
        def __init__(self):
            self.config = {
                'assets': [{
                    'name': 'KALE',
                    'contract_id': 'CA3D5KRYM6CB7OWQ6TWYRR3Z4T7GNZLKERYNZGGA5SOAOPIFY6YQGAXE',
                    'threshold_price': 1.05,
                    'strategy': 'simple_threshold',
                    'allocation': 0.5
                }]
            }
            self.keypair = None
            self.strategies = {'KALE': 'simple_threshold'}
            self.portfolio = {}
        
        def get_account_balance(self):
            return 0
            
        def is_config_complete(self):
            return False
            
        def get_transaction_history(self, limit=10):
            return []
            
        def get_performance_history(self, days=7):
            return []
            
        def get_price_from_reflector(self):
            return 0
            
        def invoke_harvest_contract(self, asset_config):
            return False, "Bot not initialized"
            
        def setup_strategies(self):
            pass
            
        def save_config(self, new_config):
            self.config = new_config
    
    class DummyNotificationManager:
        def notify(self, message, level="INFO"):
            pass  # Do nothing for dummy notifications

    bot = DummyBot()

# Flask Routes
@app.route('/')
def index():
    """Main dashboard page"""
    balance = bot.get_account_balance()
    public_key = bot.keypair.public_key if bot.keypair else 'Not set'
    transactions = bot.get_transaction_history(5)
    performance = bot.get_performance_history(7)
    
    global config_complete
    config_complete = bot.is_config_complete()
    
    return render_template('index.html', 
                         status=bot_status,
                         balance=balance,
                         config=bot.config,
                         current_prices=current_prices,
                         portfolio_value=portfolio_value,
                         last_harvest=last_harvest_time,
                         public_key=public_key,
                         config_complete=config_complete,
                         transactions=transactions,
                         performance=performance,
                         strategies=bot.strategies)

@app.route('/api/status')
def api_status():
    """API endpoint for bot status"""
    balance = bot.get_account_balance()
    return jsonify({
        'status': bot_status,
        'balance': balance,
        'current_prices': current_prices,
        'portfolio_value': portfolio_value,
        'last_harvest': last_harvest_time,
        'config_complete': config_complete
    })

@app.route('/api/start', methods=['POST'])
def api_start():
    """API endpoint to start the bot"""
    global bot_status
    
    if bot_status == "running":
        return jsonify({'success': False, 'message': 'Bot is already running'})
    
    if not bot.is_config_complete():
        return jsonify({'success': False, 'message': 'Configuration is not complete'})
    
    try:
        interval = bot.config['schedule_interval']
        scheduler.add_job(bot.check_and_harvest, 'interval', seconds=interval, id='harvest_job')
        
        scheduler.add_job(
            lambda: logger.info("Bot health check: OK"), 
            'interval', 
            seconds=bot.config.get('health_check_interval', 300), 
            id='health_check_job'
        )
        
        scheduler.add_job(
            bot.portfolio_manager.update_portfolio,
            'interval',
            minutes=5,
            id='portfolio_update_job'
        )
        
        if not scheduler.running:
            scheduler.start()
        
        bot_status = "running"
        logger.info("Bot started")
        bot.notification_manager.notify("Bot started successfully")
        return jsonify({'success': True, 'message': 'Bot started successfully'})
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    """API endpoint to stop the bot"""
    global bot_status
    
    if bot_status == "stopped":
        return jsonify({'success': False, 'message': 'Bot is already stopped'})
    
    try:
        scheduler.remove_job('harvest_job')
        scheduler.remove_job('health_check_job')
        scheduler.remove_job('portfolio_update_job')
        bot_status = "stopped"
        logger.info("Bot stopped")
        bot.notification_manager.notify("Bot stopped")
        return jsonify({'success': True, 'message': 'Bot stopped successfully'})
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    """API endpoint to get or update configuration"""
    if request.method == 'GET':
        return jsonify(bot.config)
    else:
        try:
            new_config = request.get_json()
            bot.save_config(new_config)
            
            global config_complete
            config_complete = bot.is_config_complete()
            
            logger.info("Configuration updated")
            bot.notification_manager.notify("Configuration updated")
            return jsonify({'success': True, 'message': 'Configuration updated', 'config_complete': config_complete})
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return jsonify({'success': False, 'message': str(e)})

@app.route('/api/logs')
def api_logs():
    """API endpoint to get recent logs"""
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-100:]
        return jsonify({'logs': lines})
    except Exception as e:
        return jsonify({'logs': [f"Error reading logs: {e}"]})

@app.route('/api/transactions')
def api_transactions():
    """API endpoint to get transaction history"""
    try:
        limit = request.args.get('limit', 10, type=int)
        transactions = bot.get_transaction_history(limit)
        return jsonify({'transactions': transactions})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/performance')
def api_performance():
    """API endpoint to get performance data"""
    try:
        days = request.args.get('days', 7, type=int)
        performance = bot.get_performance_history(days)
        return jsonify({'performance': performance})
    except Exception as e:
        return jsonify({'error': str(e)})

@app.route('/api/manual-harvest', methods=['POST'])
def api_manual_harvest():
    """API endpoint to manually trigger a harvest"""
    try:
        asset_name = request.json.get('asset', 'KALE')
        asset_config = next((asset for asset in bot.config.get('assets', []) if asset['name'] == asset_name), None)
        
        if not asset_config:
            return jsonify({'success': False, 'message': f'Asset {asset_name} not found in config'})
        
        success, result = bot.invoke_harvest_contract(asset_config)
        if success:
            global last_harvest_time
            last_harvest_time = time.time()
            return jsonify({'success': True, 'message': 'Manual harvest executed', 'tx_hash': result})
        else:
            return jsonify({'success': False, 'message': f'Harvest failed: {result}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/backtest', methods=['POST'])
def api_backtest():
    """API endpoint to backtest a strategy"""
    try:
        asset_name = request.json.get('asset', 'KALE')
        days = request.json.get('days', 30)
        
        asset_config = next((asset for asset in bot.config.get('assets', []) if asset['name'] == asset_name), None)
        
        if not asset_config:
            return jsonify({'success': False, 'message': f'Asset {asset_name} not found in config'})
        
        result = bot.backtest_strategy(asset_config, days)
        
        if 'error' in result:
            return jsonify({'success': False, 'message': result['error']})
        
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    try:
        print("Starting Comprehensive Stellar Smart Harvest Bot...")
        print(f"Dashboard available at: http://localhost:5000")
        if bot.keypair:
            print(f"Public Key: {bot.keypair.public_key}")
        print("Press Ctrl+C to stop the bot")
        
        app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\nShutting down...")
        scheduler.shutdown()
    except Exception as e:
        print(f"Error starting bot: {e}")
        scheduler.shutdown()