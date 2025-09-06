# Stellar Smart Harvest Bot  

A sophisticated bot that monitors asset prices using the Reflector oracle and automatically executes harvest operations on the Stellar network when price thresholds are met.  

---

## Features  
- **Real-time Price Monitoring**: Uses Reflector network oracle for accurate price data  
- **Automated Harvesting**: Executes smart contract functions when price thresholds are met  
- **Web-based Dashboard**: Easy-to-use interface for monitoring and control  
- **Secure Key Management**: Encrypted private key storage  
- **Configurable Settings**: Flexible configuration for different assets and thresholds  
- **Auto-start Functionality**: Automatically starts when configuration is complete  

---

## Prerequisites  
- **Python 3.8+**  
- **Stellar Testnet account** (automatically created and funded)  
- **Basic understanding of Stellar smart contracts**  

---

## Installation  

### Clone the repository
```bash
git clone https://github.com/SA-Msweli/harvest.git
cd harvest
```

### Create a virtual environment and install dependencies
```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Run the application
```bash
python app.py
```

Open your browser and navigate to:  
👉 [http://localhost:5000](http://localhost:5000)  

---

## Configuration  

The bot will automatically create a default configuration file (`config.json`) with the following settings:  

```json
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
```

You can modify these settings through the web interface or by editing the configuration file directly.  

---

## Usage  

1. **Initial Setup**: The bot automatically creates a Stellar account and funds it using Friendbot (Testnet only).  
2. **Configuration**: Complete the required configuration through the web interface.  
3. **Monitoring**: The bot continuously monitors prices using the Reflector oracle.  
4. **Automated Harvesting**: When the price meets your threshold, the bot executes the harvest function.  

---

## Project Structure  

```
harvest/
├── app.py            # Main application file
├── config.json       # Configuration file (auto-generated)
├── secret.key        # Encryption key (auto-generated)
├── harvest_bot.log   # Log file (auto-generated)
├── templates/
│   └── index.html    # Web interface template
└── requirements.txt  # Python dependencies
```

---

## Key Components  
- **Reflector Integration**: Real-time price data from the Reflector network  
- **Smart Contract Interaction**: Direct interaction with KALE smart contracts  
- **Encrypted Storage**: Secure storage of private keys  
- **Web Dashboard**: Real-time monitoring and control interface  
- **Scheduled Operations**: Configurable monitoring intervals  

---

## Security Notes  
- Private keys are encrypted using Fernet symmetric encryption.  
- **Never commit** `secret.key` or `config.json` with sensitive data to version control.  
- The bot is designed for **Testnet use** — exercise caution when adapting for Mainnet.  

---

## Troubleshooting  
- **Connection Issues**: Ensure you have a stable internet connection.  
- **Configuration Errors**: Delete `config.json` to reset to default settings.  
- **Port Conflicts**: The app runs on port `5000` by default — change if needed.  

---

## Contributing  
Contributions are welcome! Please feel free to submit a Pull Request.  

---

## License  

This project is licensed under the **MIT License**.  

```
MIT License

Copyright (c) 2025 Sphelele Msweli

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## .gitignore  

To avoid committing sensitive files, add a `.gitignore` file with the following:  

```
# Virtual environment
venv/
__pycache__/

# Secrets and configs
secret.key
config.json
harvest_bot.log

# System files
*.pyc
.DS_Store
```

---

## Resources  
- [Stellar SDK Documentation](https://developers.stellar.org/)  
- [Reflector Network](#)  
- [KALE on Stellar](#)  

---

## Support  
For support or questions, please open an issue on GitHub or contact the development team.  
