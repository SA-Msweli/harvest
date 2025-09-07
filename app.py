#!/usr/bin/env python3
"""
Stellar Smart Harvest Bot with Real Reflector Integration
Enhanced version with better Reflector and KALE integration
"""

import json
import time
import logging
import threading
import requests
import os
from flask import Flask, render_template, jsonify, request
from stellar_sdk import Server, Keypair, TransactionBuilder, Network, Asset
from stellar_sdk import xdr as stellar_xdr
from stellar_sdk.exceptions import NotFoundError, BadResponseError
from apscheduler.schedulers.background import BackgroundScheduler
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Configuration
CONFIG_FILE = "config.json"
LOG_FILE = "harvest_bot.log"
KEY_FILE = "secret.key"

# Global variables
bot_status = "stopped"
logs = []
scheduler = BackgroundScheduler()
current_price = 0
last_harvest_time = None
config_complete = False

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("StellarHarvestBot")

class ReflectorClient:
    """Enhanced client for interacting with Reflector price oracle"""
    
    def __init__(self, network):
        self.network = network
        self.base_url = "https://testnet.reflector.stellar.org" if network == Network.TESTNET_NETWORK_PASSPHRASE else "https://reflector.stellar.org"
        
    def get_price(self, base_asset, quote_asset="USD"):
        """Get current price from Reflector oracle using its API"""
        try:
            # Format asset properly (code:issuer for non-native assets)
            if base_asset != "XLM" and ":" not in base_asset:
                # If we have issuer information, use it
                if hasattr(self, 'base_asset_issuer') and self.base_asset_issuer:
                    base_asset = f"{base_asset}:{self.base_asset_issuer}"
            
            # Use Reflector's API to get the price
            url = f"{self.base_url}/price/{base_asset}/{quote_asset}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                price = float(data.get('price', 0))
                logger.info(f"Reflector price for {base_asset}/{quote_asset}: {price}")
                return price
            else:
                logger.error(f"Reflector API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("Reflector API request timed out")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("Failed to connect to Reflector API")
            return None
        except Exception as e:
            logger.error(f"Error getting price from Reflector: {e}")
            return None
            
    def get_multiple_prices(self, assets, quote_asset="USD"):
        """Get prices for multiple assets at once"""
        prices = {}
        for asset in assets:
            prices[asset] = self.get_price(asset, quote_asset)
        return prices

class StellarHarvestBot:
    def __init__(self):
        self.config = self.load_config()
        self.keypair = self.load_keypair()
        self.server = Server(horizon_url=self.config['horizon_url'])
        self.network = Network.TESTNET_NETWORK_PASSPHRASE if self.config['network'] == 'testnet' else Network.PUBLIC_NETWORK_PASSPHRASE
        self.reflector = ReflectorClient(self.network)
        
        # Set issuer if provided in config
        if 'base_asset_issuer' in self.config and self.config['base_asset_issuer']:
            self.reflector.base_asset_issuer = self.config['base_asset_issuer']
        
    def load_config(self):
        """Load configuration from JSON file"""
        try:
            # Check if file exists and has content
            if not os.path.exists(CONFIG_FILE) or os.path.getsize(CONFIG_FILE) == 0:
                return self.create_default_config()
                
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                
            # Set defaults for new config options
            defaults = {
                "reflector_asset": "KALE",
                "reflector_quote_asset": "USD",
                "base_asset_issuer": "CA3D5KRYM6CB7OWQ6TWYRR3Z4T7GNZLKERYNZGGA5SOAOPIFY6YQGAXE",
                "slippage_tolerance": 0.01,  # 1% slippage tolerance
                "max_retries": 3,
                "health_check_interval": 300  # 5 minutes
            }
            
            for key, value in defaults.items():
                if key not in config:
                    config[key] = value
                    
            return config
        except json.JSONDecodeError:
            # Handle case where config file contains invalid JSON
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
            "base_asset_issuer": "CA3D5KRYM6CB7OWQ6TWYRR3Z4T7GNZLKERYNZGGA5SOAOPIFY6YQGAXE",
            "schedule_interval": 30,
            "min_balance": 2.0,
            "slippage_tolerance": 0.01,
            "max_retries": 3,
            "health_check_interval": 300
        }
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        
        return default_config

    def save_config(self, new_config):
        """Save configuration to JSON file"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(new_config, f, indent=4)
        self.config = new_config
        
        # Update reflector issuer if provided
        if 'base_asset_issuer' in new_config and new_config['base_asset_issuer']:
            self.reflector.base_asset_issuer = new_config['base_asset_issuer']

    def encrypt_key(self, private_key):
        """Encrypt private key for secure storage"""
        if not os.path.exists(KEY_FILE):
            # Generate a new key and save it
            key = Fernet.generate_key()
            with open(KEY_FILE, 'wb') as f:
                f.write(key)
        else:
            # Read the existing key
            with open(KEY_FILE, 'rb') as f:
                key = f.read()
                
        # Ensure the key is properly formatted
        try:
            fernet = Fernet(key)
        except ValueError:
            # If the key is invalid, generate a new one
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
        
        # Ensure the key is valid
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
            # Create new keypair if none exists
            keypair = Keypair.random()
            encrypted_key = self.encrypt_key(keypair.secret)
            self.config['encrypted_private_key'] = encrypted_key
            self.save_config(self.config)
            
            # Fund account on testnet
            if self.config['network'] == 'testnet':
                self.fund_account(keypair)
                
            return keypair

    def fund_account(self, keypair):
        """Fund account using Friendbot on Testnet"""
        try:
            response = requests.get(f"https://friendbot.stellar.org?addr={keypair.public_key}")
            if response.status_code == 200:
                logger.info(f"Account {keypair.public_key} funded successfully")
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
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return 0

    def get_price_from_reflector(self):
        """Get current price from Reflector oracle"""
        try:
            price = self.reflector.get_price(
                self.config['reflector_asset'],
                self.config['reflector_quote_asset']
            )
            return price if price is not None else 0
        except Exception as e:
            logger.error(f"Error getting price from Reflector: {e}")
            return 0

    def invoke_harvest_contract(self):
        """Invoke the harvest function on the KALE contract"""
        try:
            # Get the current account data
            account = self.server.accounts().account_id(self.keypair.public_key).call()
            
            # Build the transaction
            transaction = (
                TransactionBuilder(
                    source_account=account,
                    network_passphrase=self.network,
                    base_fee=100  # Base fee in stroops
                )
                .append_invoke_contract_function_op(
                    contract_id=self.config['kale_contract_id'],
                    function_name="harvest",
                    parameters=[],  # Empty parameters for harvest function
                    source=self.keypair.public_key
                )
                .set_timeout(30)
                .build()
            )
            
            # Sign and submit the transaction
            transaction.sign(self.keypair)
            response = self.server.submit_transaction(transaction)
            
            logger.info(f"Harvest transaction successful: {response['hash']}")
            return True, response['hash']
        except Exception as e:
            logger.error(f"Error invoking harvest contract: {e}")
            return False, str(e)

    def check_and_harvest(self):
        """Check price and execute harvest if threshold is met"""
        global current_price, last_harvest_time
        
        try:
            # Check if we have sufficient balance
            balance = self.get_account_balance()
            if balance < self.config['min_balance']:
                logger.warning(f"Insufficient balance: {balance} XLM. Minimum required: {self.config['min_balance']} XLM")
                return
            
            # Get current price
            current_price = self.get_price_from_reflector()
            logger.info(f"Current price: {current_price}, Threshold: {self.config['threshold_price']}")
            
            # Check if price meets threshold
            if current_price >= self.config['threshold_price']:
                logger.info("Price threshold met, executing harvest...")
                
                # Retry logic
                for attempt in range(self.config['max_retries']):
                    success, result = self.invoke_harvest_contract()
                    if success:
                        last_harvest_time = time.time()
                        logger.info(f"Harvest executed successfully. TX Hash: {result}")
                        break
                    else:
                        logger.error(f"Attempt {attempt + 1} failed: {result}")
                        if attempt < self.config['max_retries'] - 1:
                            time.sleep(2)  # Wait before retrying
                else:
                    logger.error("All harvest attempts failed")
            else:
                logger.info("Price below threshold, no action taken")
                
        except Exception as e:
            logger.error(f"Error in check_and_harvest: {e}")

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
            transactions = self.server.transactions().for_account(self.keypair.public_key).limit(limit).call()
            return transactions['_embedded']['records']
        except Exception as e:
            logger.error(f"Error getting transaction history: {e}")
            return []

# Initialize bot
try:
    bot = StellarHarvestBot()
    config_complete = bot.is_config_complete()
    
    # Auto-start if config is complete
    if config_complete and bot_status == "stopped":
        interval = bot.config['schedule_interval']
        scheduler.add_job(bot.check_and_harvest, 'interval', seconds=interval, id='harvest_job')
        
        # Add health check job
        scheduler.add_job(
            lambda: logger.info("Bot health check: OK"), 
            'interval', 
            seconds=bot.config['health_check_interval'], 
            id='health_check_job'
        )
        
        if not scheduler.running:
            scheduler.start()
        bot_status = "running"
        logger.info("Bot started automatically due to complete config")
        
except Exception as e:
    logger.error(f"Failed to initialize bot: {e}")
    # Create a dummy bot object to prevent further errors
    class DummyBot:
        def __init__(self):
            self.config = {}
            self.keypair = None
        
        def get_account_balance(self):
            return 0
            
        def is_config_complete(self):
            return False
            
        def get_transaction_history(self, limit=10):
            return []
    
    bot = DummyBot()

@app.route('/')
def index():
    """Main dashboard page"""
    balance = bot.get_account_balance()
    public_key = bot.keypair.public_key if bot.keypair else 'Not set'
    transactions = bot.get_transaction_history(5)
    
    # Update config completeness status
    global config_complete
    config_complete = bot.is_config_complete()
    
    return render_template('index.html', 
                         status=bot_status,
                         balance=balance,
                         config=bot.config,
                         current_price=current_price,
                         last_harvest=last_harvest_time,
                         public_key=public_key,
                         config_complete=config_complete,
                         transactions=transactions)

@app.route('/api/status')
def api_status():
    """API endpoint for bot status"""
    balance = bot.get_account_balance()
    return jsonify({
        'status': bot_status,
        'balance': balance,
        'current_price': current_price,
        'last_harvest': last_harvest_time,
        'config_complete': config_complete
    })

@app.route('/api/start', methods=['POST'])
def api_start():
    """API endpoint to start the bot"""
    global bot_status
    
    if bot_status == "running":
        return jsonify({'success': False, 'message': 'Bot is already running'})
    
    # Check if config is complete before starting
    if not bot.is_config_complete():
        return jsonify({'success': False, 'message': 'Configuration is not complete'})
    
    try:
        # Start the scheduler
        interval = bot.config['schedule_interval']
        scheduler.add_job(bot.check_and_harvest, 'interval', seconds=interval, id='harvest_job')
        
        # Add health check job
        scheduler.add_job(
            lambda: logger.info("Bot health check: OK"), 
            'interval', 
            seconds=bot.config['health_check_interval'], 
            id='health_check_job'
        )
        
        if not scheduler.running:
            scheduler.start()
        
        bot_status = "running"
        logger.info("Bot started")
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
        # Remove the jobs
        scheduler.remove_job('harvest_job')
        scheduler.remove_job('health_check_job')
        bot_status = "stopped"
        logger.info("Bot stopped")
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
            
            # Update config completeness status
            global config_complete
            config_complete = bot.is_config_complete()
            
            logger.info("Configuration updated")
            return jsonify({'success': True, 'message': 'Configuration updated', 'config_complete': config_complete})
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return jsonify({'success': False, 'message': str(e)})

@app.route('/api/logs')
def api_logs():
    """API endpoint to get recent logs"""
    try:
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()[-100:]  # Get last 100 lines
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

@app.route('/api/manual-harvest', methods=['POST'])
def api_manual_harvest():
    """API endpoint to manually trigger a harvest"""
    try:
        success, result = bot.invoke_harvest_contract()
        if success:
            global last_harvest_time
            last_harvest_time = time.time()
            return jsonify({'success': True, 'message': 'Manual harvest executed', 'tx_hash': result})
        else:
            return jsonify({'success': False, 'message': f'Harvest failed: {result}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    try:
        # Start Flask app
        print("Starting Stellar Smart Harvest Bot...")
        print(f"Dashboard available at: http://localhost:5000")
        if bot.keypair:
            print(f"Public Key: {bot.keypair.public_key}")
        print("Press Ctrl+C to stop the bot")
        
        app.run(debug=True, use_reloader=False, host='0.0.0.0')
    except KeyboardInterrupt:
        print("\nShutting down...")
        scheduler.shutdown()
    except Exception as e:
        print(f"Error starting bot: {e}")
        scheduler.shutdown()