#!/usr/bin/env python3
"""
Crypto Tracker — Modern UI with:
- Chart range dropdown (7/30/90/365 days)
- Column sorting
- Color-coded 24h % change
- Toggle: Table view <-> Compact Card/Grid view (shows icons)
- Coin icons fetched from CoinGecko & cached in-memory
- Dark/Light theme toggle (qt-material)
- Chart (line) for selected coin (matplotlib embedded)
- Uses CoinGecko 'markets' + 'market_chart' endpoints

Save as crypto_tracker.py and run:
  python crypto_tracker.py
"""

import sys
import io
import requests
import pandas as pd
from functools import partial

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QHeaderView, QLineEdit, QHBoxLayout,
    QComboBox, QStackedLayout, QScrollArea, QGridLayout, QFrame, QSizePolicy
)
from PySide6.QtGui import QPixmap, QColor, QIcon
from PySide6.QtCore import Qt, QTimer

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

import qt_material

# ---------- Config ----------
COINS = [
    "bitcoin", "ethereum", "solana", "dogecoin", "cardano", "ripple",
    "polkadot", "litecoin", "tron", "polygon", "avalanche-2", "chainlink",
    "uniswap", "stellar", "internet-computer", "vechain", "cosmos",
    "filecoin", "aptos", "arbitrum"
]
API_URL = "https://api.coingecko.com/api/v3/coins/markets"
MARKET_CHART_URL = "https://api.coingecko.com/api/v3/coins/{id}/market_chart"
AUTO_REFRESH_INTERVAL_MS = 60_000  # 60s
DEFAULT_THEME = "dark"  # "dark" or "light"
# ----------------------------

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=8, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi, facecolor="#121212")
        self.axes = fig.add_subplot(111)
        self.axes.set_facecolor("#121212")
        super().__init__(fig)

class CryptoTracker(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🚀 Crypto Tracker")
        self.theme = DEFAULT_THEME
        self.icon_cache = {}  # id -> QPixmap

        # Main layout
        main = QVBoxLayout()
        header = QHBoxLayout()

        title = QLabel("📊 Crypto Tracker — Prices & Trends")
        title.setStyleSheet("font-size:20px; font-weight:700;")
        header.addWidget(title, 1)

        # Theme toggle
        self.theme_btn = QPushButton("🌙 Dark" if self.theme=="dark" else "🔆 Light")
        self.theme_btn.clicked.connect(self.toggle_theme)
        header.addWidget(self.theme_btn)

        # View toggle (table <-> cards)
        self.view_btn = QPushButton("📇 Cards View")
        self.view_btn.clicked.connect(self.toggle_view)
        header.addWidget(self.view_btn)

        main.addLayout(header)

        # Controls row: search, refresh, chart range dropdown
        ctrl_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Search coins by name or symbol...")
        self.search.textChanged.connect(self.filter_table)
        ctrl_row.addWidget(self.search, 2)

        self.range_dropdown = QComboBox()
        self.range_dropdown.addItems(["7 days", "30 days", "90 days", "365 days"])
        self.range_dropdown.setCurrentIndex(0)
        ctrl_row.addWidget(QLabel("Chart range:"))
        ctrl_row.addWidget(self.range_dropdown)

        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self.load_data)
        ctrl_row.addWidget(self.refresh_btn)

        main.addLayout(ctrl_row)

        # Stacked layout for Table vs Cards
        self.stack = QStackedLayout()

        # --- Table widget ---
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Coin", "Price (USD)", "Market Cap", "24h Change (%)",
            "7d Change (%)", "24h Volume", "Circulating Supply", "Total Supply"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.cellClicked.connect(self.on_coin_selected)
        # Enable sorting
        self.table.setSortingEnabled(True)

        # Put table into a container so it can match stacked layout interface
        self.table_container = QWidget()
        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(0,0,0,0)
        table_layout.addWidget(self.table)
        self.table_container.setLayout(table_layout)
        self.stack.addWidget(self.table_container)

        # --- Cards (grid) view inside scroll area ---
        self.cards_widget = QWidget()
        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(12)
        self.cards_widget.setLayout(self.cards_layout)
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setWidget(self.cards_widget)
        self.stack.addWidget(self.cards_scroll)

        # Add stacked layout to main
        main.addLayout(self.stack)

        # Chart canvas
        self.canvas = MplCanvas(self, width=8, height=4, dpi=100)
        main.addWidget(self.canvas)

        # status label
        self.status_label = QLabel("")
        main.addWidget(self.status_label)

        self.setLayout(main)

        # Auto-refresh timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.load_data)
        self.timer.start(AUTO_REFRESH_INTERVAL_MS)

        # Load initial data
        self.all_data = []
        self.load_data()

    # -------------------------
    # Theme handling
    # -------------------------
    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.apply_theme()
        self.theme_btn.setText("🌙 Dark" if self.theme=="dark" else "🔆 Light")

    def apply_theme(self):
        if self.theme == "dark":
            qt_material.apply_stylesheet(QApplication.instance(), theme="dark_teal.xml")
        else:
            qt_material.apply_stylesheet(QApplication.instance(), theme="light_blue.xml")
        # update canvas colors
        self.canvas.figure.set_facecolor("#121212" if self.theme=="dark" else "#ffffff")
        self.canvas.axes.set_facecolor("#121212" if self.theme=="dark" else "#ffffff")
        self.canvas.draw_idle()

    # -------------------------
    # Data fetching & populate
    # -------------------------
    def load_data(self):
        try:
            self.status_label.setText("Fetching market data...")
            QApplication.processEvents()
            resp = requests.get(API_URL, params={
                "vs_currency": "usd",
                "ids": ",".join(COINS),
                "price_change_percentage": "24h,7d"
            }, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            self.all_data = data
            self.populate_table_and_cards(data)
            self.status_label.setText("Last update: fetched {} coins".format(len(data)))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to fetch data:\n{e}")
            self.status_label.setText("Failed to fetch data")

    def populate_table_and_cards(self, data):
        # TABLE
        self.table.setSortingEnabled(False)  # disable while populating
        self.table.setRowCount(len(data))
        for r, coin in enumerate(data):
            # Coin name item (store coin id)
            name_item = QTableWidgetItem(coin["name"])
            name_item.setData(Qt.UserRole, coin["id"])
            # Also store symbol for search
            name_item.setData(Qt.UserRole + 1, coin.get("symbol", "").lower())
            self.table.setItem(r, 0, name_item)

            # Price (display formatted, provide numeric in EditRole for sorting)
            price_val = float(coin.get("current_price") or 0.0)
            price_item = QTableWidgetItem(f"${price_val:,.2f}")
            price_item.setData(Qt.EditRole, price_val)
            self.table.setItem(r, 1, price_item)

            # Market cap
            mcap_val = float(coin.get("market_cap") or 0)
            mcap_item = QTableWidgetItem(f"${mcap_val:,.0f}")
            mcap_item.setData(Qt.EditRole, mcap_val)
            self.table.setItem(r, 2, mcap_item)

            # 24h change
            pct24 = coin.get("price_change_percentage_24h") or 0.0
            pct24_item = QTableWidgetItem(f"{pct24:+.2f}%")
            pct24_item.setData(Qt.EditRole, float(pct24))
            # color coding
            if pct24 > 0:
                pct24_item.setForeground(QColor("lime"))
            elif pct24 < 0:
                pct24_item.setForeground(QColor("red"))
            self.table.setItem(r, 3, pct24_item)

            # 7d change (from API field if exists)
            pct7 = coin.get("price_change_percentage_7d_in_currency")
            pct7 = float(pct7) if pct7 is not None else 0.0
            pct7_item = QTableWidgetItem(f"{pct7:+.2f}%")
            pct7_item.setData(Qt.EditRole, float(pct7))
            self.table.setItem(r, 4, pct7_item)

            # 24h volume
            vol_val = float(coin.get("total_volume") or 0)
            vol_item = QTableWidgetItem(f"${vol_val:,.0f}")
            vol_item.setData(Qt.EditRole, vol_val)
            self.table.setItem(r, 5, vol_item)

            # circulating supply
            circ = coin.get("circulating_supply") or 0
            circ_item = QTableWidgetItem(f"{circ:,.0f}")
            circ_item.setData(Qt.EditRole, float(circ or 0))
            self.table.setItem(r, 6, circ_item)

            # total supply
            total_supply = coin.get("total_supply")
            total_text = f"{total_supply:,.0f}" if total_supply else "∞"
            ts_item = QTableWidgetItem(total_text)
            ts_item.setData(Qt.EditRole, float(total_supply or 0))
            self.table.setItem(r, 7, ts_item)

        self.table.setSortingEnabled(True)  # re-enable sorting

        # CARDS view
        # Clear existing cards
        for i in reversed(range(self.cards_layout.count())):
            w = self.cards_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        cols = 4
        row = col = 0
        for coin in data:
            card = self._create_card(coin)
            self.cards_layout.addWidget(card, row, col)
            col += 1
            if col >= cols:
                col = 0
                row += 1

    # -------------------------
    # Card builder
    # -------------------------
    def _create_card(self, coin):
        frame = QFrame()
        frame.setFrameShape(QFrame.Box)
        frame.setLineWidth(1)
        frame.setFixedWidth(250)
        frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)

        # Icon + name row
        top = QHBoxLayout()
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(36,36)
        pix = self._get_icon(coin)
        if pix:
            icon_lbl.setPixmap(pix.scaled(36,36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        top.addWidget(icon_lbl)

        name = QLabel(f"{coin['name']} ({coin.get('symbol','').upper()})")
        name.setStyleSheet("font-weight:600;")
        top.addWidget(name)
        layout.addLayout(top)

        # Price
        price = float(coin.get("current_price") or 0)
        p_lbl = QLabel(f"Price: ${price:,.2f}")
        layout.addWidget(p_lbl)

        # 24h change (colored)
        pct24 = coin.get("price_change_percentage_24h") or 0.0
        p24 = QLabel(f"24h: {pct24:+.2f}%")
        if pct24 > 0:
            p24.setStyleSheet("color: lime; font-weight:600;")
        elif pct24 < 0:
            p24.setStyleSheet("color: red; font-weight:600;")
        layout.addWidget(p24)

        # Market cap
        mcap = float(coin.get("market_cap") or 0)
        layout.addWidget(QLabel(f"Market Cap: ${mcap:,.0f}"))

        # View details button
        btn = QPushButton("View 30/selected-range Trend")
        btn.clicked.connect(partial(self._card_clicked, coin))
        layout.addWidget(btn)

        frame.setLayout(layout)
        return frame

    def _card_clicked(self, coin):
        # find index of coin in table and select row so user knows which coin is selected
        coin_id = coin.get("id")
        for r in range(self.table.rowCount()):
            item = self.table.item(r,0)
            if item and item.data(Qt.UserRole) == coin_id:
                self.table.selectRow(r)
                self.on_coin_selected(r, 0)
                break

    # -------------------------
    # Icon fetching & caching
    # -------------------------
    def _get_icon(self, coin):
        cid = coin.get("id")
        if not cid:
            return None
        if cid in self.icon_cache:
            return self.icon_cache[cid]
        url = coin.get("image")
        if not url:
            return None
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            pix = QPixmap()
            pix.loadFromData(r.content)
            self.icon_cache[cid] = pix
            return pix
        except Exception:
            return None

    # -------------------------
    # Search/filter
    # -------------------------
    def filter_table(self, text):
        txt = text.lower().strip()
        if not txt:
            # show all
            self.populate_table_and_cards(self.all_data)
            return
        filtered = []
        for coin in self.all_data:
            name = coin.get("name","").lower()
            symbol = coin.get("symbol","").lower()
            if txt in name or txt in symbol:
                filtered.append(coin)
        self.populate_table_and_cards(filtered)

    # -------------------------
    # View toggle
    # -------------------------
    def toggle_view(self):
        idx = self.stack.currentIndex()
        idx = 1 if idx == 0 else 0
        self.stack.setCurrentIndex(idx)
        self.view_btn.setText("📋 Table View" if idx == 1 else "📇 Cards View")

    # -------------------------
    # Chart / selection handling
    # -------------------------
    def on_coin_selected(self, row, _col):
        # get coin id stored in UserRole
        item = self.table.item(row, 0)
        if not item:
            return
        coin_id = item.data(Qt.UserRole)
        coin_name = item.text()
        # chart days from dropdown
        days_text = self.range_dropdown.currentText()
        days_map = {"7 days": 7, "30 days": 30, "90 days": 90, "365 days": 365}
        days = days_map.get(days_text, 7)
        try:
            self.status_label.setText(f"Fetching chart for {coin_name} ({coin_id})...")
            QApplication.processEvents()
            url = MARKET_CHART_URL.format(id=coin_id)
            resp = requests.get(url, params={"vs_currency": "usd", "days": days, "interval": "daily"}, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            if "prices" not in data or not data["prices"]:
                raise ValueError("No price data returned")
            df = pd.DataFrame(data["prices"], columns=["timestamp","price"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            df["pct_change"] = df["price"].pct_change() * 100

            # draw simple modern line with markers and annotations for pct change
            ax = self.canvas.axes
            ax.clear()
            if self.theme == "dark":
                ax.set_facecolor("#121212")
            else:
                ax.set_facecolor("#ffffff")
            ax.plot(df.index, df["price"], marker="o", linewidth=1.5, label="Price")
            for i in range(1, len(df)):
                ch = df["pct_change"].iloc[i]
                dt = df.index[i]
                pr = df["price"].iloc[i]
                if ch >= 0:
                    ax.text(dt, pr, f"▲{ch:.2f}%", color="lime", fontsize=8, ha="center")
                else:
                    ax.text(dt, pr, f"▼{ch:.2f}%", color="red", fontsize=8, ha="center")

            ax.set_title(f"{coin_name} — Last {days} days", color="white" if self.theme=="dark" else "black")
            ax.set_ylabel("Price (USD)")
            ax.grid(True, linestyle="--", alpha=0.4)
            ax.tick_params(colors="white" if self.theme=="dark" else "black")
            ax.legend(facecolor="#121212" if self.theme=="dark" else "#ffffff")
            self.canvas.draw()
            self.status_label.setText(f"Showing chart for {coin_name} ({days} days)")
        except Exception as e:
            QMessageBox.critical(self, "Error loading chart", str(e))
            self.status_label.setText("Failed to load chart")

# -------------------------
# Run app
# -------------------------
def main():
    app = QApplication(sys.argv)
    # Apply default theme
    if DEFAULT_THEME == "dark":
        qt_material.apply_stylesheet(app, theme="dark_teal.xml")
    else:
        qt_material.apply_stylesheet(app, theme="light_blue.xml")

    w = CryptoTracker()
    w.showMaximized()  # start maximized but keep title bar
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

# -------------------------
# Packaging notes (PyInstaller)
# -------------------------
# To build a single-file Windows .exe:
#   pip install pyinstaller
#   pyinstaller --noconfirm --onefile --windowed crypto_tracker.py
#
# For macOS .app:
#   pyinstaller --noconfirm --onefile --windowed --name "CryptoTracker" crypto_tracker.py
#
# You may need to include matplotlib/Qt hooks and extra data; test the frozen app and refer to
# PyInstaller docs for adding hiddenimports or data files (qt_material themes).
#
# -------------------------
# Web version (next steps)
# -------------------------
# To port to web later: create a REST API (Python backend) that calls CoinGecko and a React/Next frontend
# that fetches the API, shows the table/cards, and uses a charting lib (e.g. Chart.js, Recharts, TradingView).
