##Stellar Smart Harvest Bot
A sophisticated bot that monitors asset prices using the Reflector oracle and automatically executes harvest operations on the Stellar network when price thresholds are met.

##Features
Real-time Price Monitoring: Uses Reflector network oracle for accurate price data

Automated Harvesting: Executes smart contract functions when price thresholds are met

Web-based Dashboard: Easy-to-use interface for monitoring and control

Secure Key Management: Encrypted private key storage

Configurable Settings: Flexible configuration for different assets and thresholds

Auto-start Functionality: Automatically starts when configuration is complete

##Prerequisites
**Python 3.8+
**Stellar Testnet account (automatically created and funded)
**Basic understanding of Stellar smart contracts

##Installation
###Clone the repository:

bash
git clone https://github.com/SA-Msweli/harvest.git
cd harvest
Create a virtual environment and install dependencies:

bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
Run the application:

bash
python app.py
Open your browser and navigate to http://localhost:5000

##Configuration
The bot will automatically create a default configuration file (config.json) with the following settings:

json
{
  "network": "testnet",
  "horizon_url": "https://horizon-testnet.stellar.org",
  "asset_pair": "KALE/USD",
  "threshold_price": 1.05,
  "kale_contract_id": "CA3D5KRYM6CB7OWQ6TWYRR3Z4T7GNZLKERYNZGGA5SOAOPIFY6YQGAXE",
  "reflector_asset": "KALE",
  "reflector_quote_asset": "USD",
  "schedule_interval": 30,
  "min_balance": 2.0
}
You can modify these settings through the web interface or by editing the configuration file directly.

##Usage
Initial Setup: The bot will automatically create a Stellar account and fund it using Friendbot (Testnet only)

Configuration: Complete the required configuration through the web interface

Monitoring: The bot will continuously monitor prices using the Reflector oracle

Automated Harvesting: When the price meets your threshold, the bot will execute the harvest function

##Project Structure
text
harvest/
├── app.py                 # Main application file
├── config.json           # Configuration file (auto-generated)
├── secret.key            # Encryption key (auto-generated)
├── harvest_bot.log       # Log file (auto-generated)
├── templates/
│   └── index.html        # Web interface template
└── requirements.txt      # Python dependencies

##Key Components
Reflector Integration: Real-time price data from the Reflector network

Smart Contract Interaction: Direct interaction with KALE smart contracts

Encrypted Storage: Secure storage of private keys

Web Dashboard: Real-time monitoring and control interface

Scheduled Operations: Configurable monitoring intervals

##Security Notes
Private keys are encrypted using Fernet symmetric encryption

Never commit secret.key or config.json with sensitive data to version control

The bot is designed for Testnet use - exercise caution when adapting for Mainnet

##Troubleshooting
Connection Issues: Ensure you have a stable internet connection

Configuration Errors: Delete config.json to reset to default settings

Port Conflicts: The app runs on port 5000 by default - change if needed

##Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

##License
This project is open source and available under the MIT License.

##Resources
**Stellar SDK Documentation
**Reflector Network
**KALE on Stellar

##Support
For support or questions, please open an issue on GitHub or contact the development team.
