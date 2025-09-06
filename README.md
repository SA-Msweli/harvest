# Stellar Smart Harvest Bot

A **mini local app** that demonstrates composability on Stellar by combining **Reflector price feeds** with **KALE smart contracts**.  
The bot runs locally, fetches online price data via Reflector, and automatically executes on-chain harvest operations on Stellar Testnet when configured price thresholds are met.

---

## ✨ Features

- **Local-First Demo**: Runs entirely on your machine, no external hosting required.
- **Real-Time Price Monitoring**: Uses Reflector network oracle for live price feeds (classic assets, FX pairs, CEX/DEX rates, KALE).
- **Automated Harvesting**: Executes KALE contract harvest functions when thresholds are reached.
- **Web Dashboard**: Local Flask-based UI for monitoring and control.
- **Configurable Settings**: Modify thresholds, asset pairs, and scheduling via the dashboard or `config.json`.
- **Auto-Setup**: Creates and funds a Testnet account automatically.

---

## 🛠 Prerequisites

- **Python 3.8+**
- **Stellar Testnet account** (automatically created by Friendbot)
- **Basic knowledge of Stellar smart contracts**

---

## 🚀 Installation

Clone the repository:

```bash
git clone https://github.com/SA-Msweli/harvest.git
cd harvest
```

Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Run the application:

```bash
python app.py
```

Open your browser at **http://localhost:5000**

---

## ⚙️ Configuration

The app generates a default `config.json` with:

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

Modify via the web dashboard or directly in the file.  
Reflector supports multiple feeds, so you can experiment with **XLM/USD, BTC/USD, USD/EUR**, etc.

---

## ▶️ Usage

1. **Initial Setup**: App creates and funds a Testnet account.  
2. **Configure**: Set asset pair + threshold in the dashboard.  
3. **Monitor**: The app fetches live price data from Reflector.  
4. **Harvest**: If price meets your conditions, the bot executes the KALE harvest transaction on Stellar Testnet.  

---

## 📂 Project Structure

```
harvest/
├── app.py              # Main application file
├── config.json         # Auto-generated configuration
├── secret.key          # Local encryption key (auto-generated)
├── harvest_bot.log     # Log file (auto-generated)
├── templates/
│   └── index.html      # Web dashboard UI
└── requirements.txt    # Python dependencies
```

---

## 🔑 Security Notes

- Private keys are encrypted with **Fernet symmetric encryption**.
- Do **not** commit `secret.key` or `config.json` to version control.
- Designed for **Testnet**; use caution when adapting to Mainnet.

---

## 🛠 Troubleshooting

- **Connection issues** → check internet & Horizon URL.  
- **Bad config** → delete `config.json` to reset.  
- **Port conflicts** → app defaults to port `5000`.  

---

## 🤝 Contributing

Contributions are welcome! Fork, improve, and submit a PR.

---

## 📜 License

MIT License

---

## 📚 Resources

- [Stellar SDK Docs](https://developers.stellar.org/docs)  
- [Reflector Network](https://reflector.network)  
- [KALE on Stellar](https://kaleonstellar.com)  

---

## 💬 Support

Open an issue on GitHub or reach out to the dev team.
