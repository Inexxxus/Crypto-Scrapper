#!/usr/bin/env python3
"""
Crypto Tracker with Modern UI
- Fetches live crypto data from CoinGecko API
- Displays famous coins (BTC, ETH, SOL, DOGE, ADA, XRP)
- Modern Material Design using qt-material
"""

import sys
import requests
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt
import qt_material


# Famous coins to track
COINS = ["bitcoin", "ethereum", "solana", "dogecoin", "cardano", "ripple"]

API_URL = "https://api.coingecko.com/api/v3/coins/markets"


class CryptoTracker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🚀 Crypto Tracker")
        self.resize(800, 400)

        layout = QVBoxLayout()

        self.title = QLabel("📊 Live Crypto Prices")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 22px; font-weight: bold; margin: 10px;")
        layout.addWidget(self.title)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Coin", "Price (USD)", "Market Cap", "24h Change (%)", "Symbol"])
        layout.addWidget(self.table)

        # Refresh Button
        self.refresh_btn = QPushButton("🔄 Refresh Data")
        self.refresh_btn.clicked.connect(self.load_data)
        layout.addWidget(self.refresh_btn)

        self.setLayout(layout)

        # Load data on start
        self.load_data()

    def load_data(self):
        try:
            response = requests.get(API_URL, params={
                "vs_currency": "usd",
                "ids": ",".join(COINS)
            })
            data = response.json()

            self.table.setRowCount(len(data))

            for row, coin in enumerate(data):
                self.table.setItem(row, 0, QTableWidgetItem(coin["name"]))
                self.table.setItem(row, 1, QTableWidgetItem(f"${coin['current_price']:,}"))
                self.table.setItem(row, 2, QTableWidgetItem(f"${coin['market_cap']:,}"))
                self.table.setItem(row, 3, QTableWidgetItem(f"{coin['price_change_percentage_24h']:.2f}%"))
                self.table.setItem(row, 4, QTableWidgetItem(coin["symbol"].upper()))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch data:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    qt_material.apply_stylesheet(app, theme="dark_teal.xml")  # Modern Dark Theme
    window = CryptoTracker()
    window.show()
    sys.exit(app.exec())
