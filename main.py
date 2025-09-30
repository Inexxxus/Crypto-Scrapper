#!/usr/bin/env python3
"""
Crypto Tracker with Modern UI + Daily Trend Charts
- Fetches live crypto data from CoinGecko API
- Displays 20+ popular coins
- Modern Material Design using qt-material
- Shows 7-day daily line chart with % changes for selected coin
"""

import sys
import requests
import pandas as pd

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView
)
from PySide6.QtCore import Qt

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import qt_material


# Popular coins to track (CoinGecko IDs!)
COINS = [
    "bitcoin", "ethereum", "solana", "dogecoin", "cardano", "ripple",
    "polkadot", "litecoin", "tron", "polygon", "avalanche-2", "chainlink",
    "uniswap", "stellar", "internet-computer", "vechain", "cosmos",
    "filecoin", "aptos", "arbitrum"
]

API_URL = "https://api.coingecko.com/api/v3/coins/markets"
MARKET_CHART_URL = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"


class MplCanvas(FigureCanvas):
    """Matplotlib Canvas for embedding charts in Qt."""
    def __init__(self, parent=None, width=7, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi, facecolor="#121212")
        self.axes = fig.add_subplot(111)
        self.axes.set_facecolor("#121212")
        super().__init__(fig)


class CryptoTracker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🚀 Crypto Tracker with Charts")
        self.resize(1200, 700)

        layout = QVBoxLayout()

        self.title = QLabel("📊 Live Crypto Prices + 7-Day Daily Trends")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("font-size: 22px; font-weight: bold; margin: 10px;")
        layout.addWidget(self.title)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Coin", "Price (USD)", "Market Cap", "24h Change (%)",
            "7d Change (%)", "24h Volume", "Circulating Supply", "Total Supply"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.cellClicked.connect(self.show_chart)  # click row to show chart
        layout.addWidget(self.table)

        # Refresh Button
        self.refresh_btn = QPushButton("🔄 Refresh Data")
        self.refresh_btn.clicked.connect(self.load_data)
        layout.addWidget(self.refresh_btn)

        # Chart Canvas
        self.canvas = MplCanvas(self, width=8, height=4, dpi=100)
        layout.addWidget(self.canvas)

        self.setLayout(layout)

        # Load data on start
        self.load_data()

    def load_data(self):
        try:
            response = requests.get(API_URL, params={
                "vs_currency": "usd",
                "ids": ",".join(COINS),
                "price_change_percentage": "24h,7d"
            })
            data = response.json()

            self.table.setRowCount(len(data))

            for row, coin in enumerate(data):
                # Store coin ID in the "Coin" column as hidden data
                item = QTableWidgetItem(coin["name"])
                item.setData(Qt.UserRole, coin["id"])  # CoinGecko ID
                self.table.setItem(row, 0, item)

                self.table.setItem(row, 1, QTableWidgetItem(f"${coin['current_price']:,}"))
                self.table.setItem(row, 2, QTableWidgetItem(f"${coin['market_cap']:,}"))
                self.table.setItem(row, 3, QTableWidgetItem(f"{coin['price_change_percentage_24h']:.2f}%"))
                self.table.setItem(row, 4, QTableWidgetItem(f"{coin.get('price_change_percentage_7d_in_currency', 0):.2f}%"))
                self.table.setItem(row, 5, QTableWidgetItem(f"${coin['total_volume']:,}"))
                self.table.setItem(row, 6, QTableWidgetItem(f"{coin.get('circulating_supply', 0):,.0f}"))
                self.table.setItem(row, 7, QTableWidgetItem(f"{coin.get('total_supply', 0) or '∞'}"))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch data:\n{e}")

    def show_chart(self, row, _col):
        """Show daily trend line chart with % changes when a coin is clicked."""
        coin_id = self.table.item(row, 0).data(Qt.UserRole)  # Use CoinGecko ID

        try:
            url = MARKET_CHART_URL.format(id=coin_id)
            response = requests.get(url, params={"vs_currency": "usd", "days": 7, "interval": "daily"})
            data = response.json()

            if "prices" not in data:
                raise ValueError("No chart data available")

            # Convert to DataFrame
            df = pd.DataFrame(data["prices"], columns=["timestamp", "price"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)

            # Compute daily percentage change
            df["pct_change"] = df["price"].pct_change() * 100

            # Clear and draw line chart
            self.canvas.axes.clear()
            self.canvas.axes.plot(df.index, df["price"], marker="o", color="cyan", label="Price")

            # Add up/down markers
            for i in range(1, len(df)):
                change = df["pct_change"].iloc[i]
                date = df.index[i]
                price = df["price"].iloc[i]
                if change >= 0:
                    self.canvas.axes.text(date, price, f"▲ {change:.2f}%", color="lime", fontsize=8, ha="center")
                else:
                    self.canvas.axes.text(date, price, f"▼ {change:.2f}%", color="red", fontsize=8, ha="center")

            self.canvas.axes.set_title(f"{coin_id.capitalize()} - Last 7 Days Trend", color="white", fontsize=12)
            self.canvas.axes.set_ylabel("Price (USD)", color="white")
            self.canvas.axes.grid(True, linestyle="--", alpha=0.4)
            self.canvas.axes.tick_params(colors="white")
            self.canvas.axes.legend(facecolor="#121212", edgecolor="white")

            self.canvas.draw()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch chart:\n{e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    qt_material.apply_stylesheet(app, theme="dark_teal.xml")  # Modern Dark Theme
    window = CryptoTracker()
    window.show()
    sys.exit(app.exec())
