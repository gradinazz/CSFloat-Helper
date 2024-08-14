import sys
import requests
import json
import os
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QFormLayout, QDialog
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt, QSettings, QPersistentModelIndex  # Добавлен QPersistentModelIndex
from datetime import datetime, timezone
from collections import defaultdict

# Constants for API endpoints
API_USER_INFO = "https://csfloat.com/api/v1/me"
API_INVENTORY = "https://csfloat.com/api/v1/me/inventory"
API_STALL = "https://csfloat.com/api/v1/users/{steam_id}/stall?limit=999"
LISTINGS_URL = "https://csfloat.com/api/v1/listings"

# Load API key from config file
CONFIG_FILE = "config.json"

# Cache directory for storing images
CACHE_DIR = "cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

CSFLOAT_LOGO_PATH = "csfloat_logo.png"  # Путь к логотипу CSFloat

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return None

config = load_config()
if not config:
    print("Config file not found. Please ensure config.json exists and contains the required API key.")
    sys.exit(1)

API_KEY = config.get("api_key")
if not API_KEY:
    print("API key is missing in config.json.")
    sys.exit(1)

def get_user_info(api_key):
    headers = {'Authorization': api_key}
    url = API_USER_INFO
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        user_info = response.json().get("user", {})
        return {
            "steam_id": user_info.get("steam_id"),
            "username": user_info.get("username"),
            "balance": user_info.get("balance"),
            "total_sales": user_info.get("statistics", {}).get("total_sales"),
            "total_purchases": user_info.get("statistics", {}).get("total_purchases"),
            "median_trade_time": user_info.get("statistics", {}).get("median_trade_time"),
            "total_avoided_trades": user_info.get("statistics", {}).get("total_avoided_trades"),
            "total_failed_trades": user_info.get("statistics", {}).get("total_failed_trades"),
            "total_verified_trades": user_info.get("statistics", {}).get("total_verified_trades"),
            "total_trades": user_info.get("statistics", {}).get("total_trades"),
        }
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        print(f"Other error occurred: {err}")
        return None

def get_inventory_data(api_key):
    url_inventory = API_INVENTORY
    headers = {"Authorization": api_key}
    try:
        response_inventory = requests.get(url_inventory, headers=headers)
        response_inventory.raise_for_status()
        
        inventory_data = response_inventory.json()
        if isinstance(inventory_data, list):
            return inventory_data
        elif isinstance(inventory_data, dict):
            return inventory_data.get('items', [])
        else:
            print("Unexpected response format.")
            return []
        
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        print(f"Other error occurred: {err}")
        return None

def get_stall_data(api_key, steam_id):
    url_stall = API_STALL.format(steam_id=steam_id)
    headers = {"Authorization": api_key}
    try:
        response_stall = requests.get(url_stall, headers=headers)
        response_stall.raise_for_status()
        return response_stall.json().get("data", [])
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        print(f"Other error occurred: {err}")
        return None

def sell_item(api_key, asset_id, price, marketplace="steam"):
    if not asset_id or not isinstance(price, int) or price <= 0:
        print(f"Invalid asset_id or price: asset_id={asset_id}, price={price}")
        return None

    data = {
        "asset_id": asset_id,
        "price": price,
        "type": "buy_now"
    }

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(LISTINGS_URL, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as http_err:
        print(f"Error during sale: {http_err}, Response: {response.text}")
        return None
    except Exception as err:
        print(f"An error occurred: {err}")
        return None

def delete_item(api_key, listing_id):
    url = f"{LISTINGS_URL}/{listing_id}"
    headers = {
        "Authorization": api_key
    }

    try:
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        print(f"An error occurred: {err}")
        return None

def change_price(api_key, listing_id, new_price):
    url = f"{LISTINGS_URL}/{listing_id}"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    data = {"price": new_price}

    try:
        response = requests.patch(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        print(f"An error occurred: {err}")
        return None

class SteamInventoryApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Steam Inventory")
        self.setFixedSize(740, 750)

        self.settings = QSettings("MyCompany", "SteamInventoryApp")  # Инициализация QSettings

        self.user_info = None
        self.steam_id = None
        self.inventory = []
        self.stall = []

        self.initUI()  # Инициализация интерфейса
        self.load_data()  # Загрузка данных после инициализации интерфейса

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        self.name_filter = QLineEdit(self)
        self.name_filter.setPlaceholderText("Filter by Name")
        self.name_filter.move(20, 20)
        self.name_filter.setFixedSize(150, 30)
        self.name_filter.textChanged.connect(self.apply_filters)
        
        self.sticker_filter = QLineEdit(self)
        self.sticker_filter.setPlaceholderText("Filter by Sticker")
        self.sticker_filter.move(20, 60)
        self.sticker_filter.setFixedSize(150, 30)
        self.sticker_filter.textChanged.connect(self.apply_filters)
        
        self.float_min_filter = QLineEdit(self)
        self.float_min_filter.setPlaceholderText("Min Float")
        self.float_min_filter.move(200, 20)
        self.float_min_filter.setFixedSize(70, 30)
        self.float_min_filter.textChanged.connect(self.apply_filters)
        
        self.float_max_filter = QLineEdit(self)
        self.float_max_filter.setPlaceholderText("Max Float")
        self.float_max_filter.move(200, 60)
        self.float_max_filter.setFixedSize(70, 30)
        self.float_max_filter.textChanged.connect(self.apply_filters)
        
        self.price_input = QLineEdit(self)
        self.price_input.setPlaceholderText("Price")
        self.price_input.move(300, 20)
        self.price_input.setFixedSize(70, 30)
        
        self.sell_button = QPushButton("Sell", self)
        self.sell_button.move(400, 20)
        self.sell_button.setFixedSize(80, 30)
        self.sell_button.clicked.connect(self.sell_items)
        
        self.delist_button = QPushButton("Delist", self)
        self.delist_button.move(400, 60)
        self.delist_button.setFixedSize(80, 30)
        self.delist_button.clicked.connect(self.delist_items)
        
        self.change_price_button = QPushButton("Change Price", self)
        self.change_price_button.move(510, 20)
        self.change_price_button.setFixedSize(100, 30)
        self.change_price_button.clicked.connect(self.change_item_price)
        
        self.user_info_button = QPushButton("User Info", self)
        self.user_info_button.move(510, 60)
        self.user_info_button.setFixedSize(100, 30)
        self.user_info_button.clicked.connect(self.show_user_info)

        # Table Widget for displaying inventory
        self.inventory_table = QTableWidget(self)
        self.inventory_table.setColumnCount(7)
        self.inventory_table.setHorizontalHeaderLabels([
            "Name", "Stickers", "Float Value", "Days on Sale", "Price", "Listing ID", "Asset ID"
        ])
        self.inventory_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.inventory_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.inventory_table.setSortingEnabled(True)
        self.inventory_table.horizontalHeader().setSectionsClickable(True)
        self.inventory_table.horizontalHeader().setSortIndicatorShown(True)

        # Set position and size of the table
        self.inventory_table.move(20, 100)
        self.inventory_table.setFixedSize(700, 600)

        # Set column resize mode individually
        self.inventory_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.inventory_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.inventory_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.inventory_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.inventory_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.inventory_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.inventory_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)

        self.load_column_widths()  # Загрузка ширины колонок при запуске

    def load_data(self):
        self.user_info = get_user_info(API_KEY)
        if self.user_info:
            self.steam_id = self.user_info.get("steam_id")
            self.inventory = get_inventory_data(API_KEY)
            self.stall = get_stall_data(API_KEY, self.steam_id)
            self.populate_inventory_table()

    def populate_inventory_table(self):
        self.inventory_table.setRowCount(0)

        stall_dict = {item['item']['asset_id']: item for item in self.stall}

        for item in self.inventory:
            row_position = self.inventory_table.rowCount()
            self.inventory_table.insertRow(row_position)

            asset_id = item.get("asset_id")
            market_hash_name = item.get("market_hash_name")

            name_item = QTableWidgetItem(market_hash_name)
            self.inventory_table.setItem(row_position, 0, name_item)

            stickers = item.get("stickers", [])
            sticker_widgets = []
            for sticker in stickers:
                sticker_icon_url = sticker.get("icon_url")
                sticker_path = self.cache_image(sticker_icon_url)
                if sticker_path:
                    pixmap = QPixmap(sticker_path)
                    sticker_label = QLabel(self)
                    sticker_label.setPixmap(pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio))
                    sticker_label.setToolTip(sticker.get("name", "Unknown"))
                    sticker_widgets.append(sticker_label)

            sticker_layout = QHBoxLayout()
            for widget in sticker_widgets:
                sticker_layout.addWidget(widget)
            sticker_layout.addStretch()
            sticker_widget = QWidget()
            sticker_widget.setLayout(sticker_layout)
            self.inventory_table.setCellWidget(row_position, 1, sticker_widget)

            float_value = item.get('float_value')
            if float_value is not None:
                float_value_item = QTableWidgetItem(f"{float_value:.14f}")
            else:
                float_value_item = QTableWidgetItem("")
            self.inventory_table.setItem(row_position, 2, float_value_item)

            stall_item = stall_dict.get(asset_id)
            if stall_item:
                days_on_sale = self.calculate_days_on_sale(stall_item['created_at'])
                days_on_sale_item = QTableWidgetItem(days_on_sale)
                self.inventory_table.setItem(row_position, 3, days_on_sale_item)

                price = f"{stall_item['price'] / 100:.2f}$"
                price_widget = QWidget()
                price_layout = QHBoxLayout(price_widget)
                price_layout.setContentsMargins(0, 0, 0, 0)

                csfloat_logo = QLabel()
                csfloat_logo.setPixmap(QPixmap(CSFLOAT_LOGO_PATH).scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio))
                price_layout.addWidget(csfloat_logo)

                price_label = QLabel(f" {price}")
                price_layout.addWidget(price_label)

                price_layout.addStretch()
                self.inventory_table.setCellWidget(row_position, 4, price_widget)

                listing_id_item = QTableWidgetItem(stall_item['id'])
                self.inventory_table.setItem(row_position, 5, listing_id_item)
                self.inventory_table.setColumnHidden(5, True)
            else:
                self.inventory_table.setItem(row_position, 3, QTableWidgetItem(""))
                self.inventory_table.setItem(row_position, 4, QTableWidgetItem(""))
                self.inventory_table.setItem(row_position, 5, QTableWidgetItem(""))
                self.inventory_table.setColumnHidden(5, True)

            asset_id_item = QTableWidgetItem(asset_id)
            self.inventory_table.setItem(row_position, 6, asset_id_item)
            self.inventory_table.setColumnHidden(6, True)

    def load_column_widths(self):
        """Загрузка ширины колонок из настроек."""
        for i in range(self.inventory_table.columnCount()):
            width = self.settings.value(f"column_width_{i}", type=int)
            if width:
                self.inventory_table.setColumnWidth(i, width)

    def save_column_widths(self):
        """Сохранение ширины колонок в настройки."""
        for i in range(self.inventory_table.columnCount()):
            self.settings.setValue(f"column_width_{i}", self.inventory_table.columnWidth(i))

    def closeEvent(self, event):
        self.save_column_widths()  # Сохранение ширины колонок при закрытии
        event.accept()  # Закрываем окно
                
    def cache_image(self, url):
        if not url:
            return None

        file_name = url.split("/")[-1]
        file_path = os.path.join(CACHE_DIR, file_name)
        if not os.path.exists(file_path):
            try:
                response = requests.get(url)
                with open(file_path, 'wb') as file:
                    file.write(response.content)
            except requests.RequestException as e:
                print(f"Failed to download image from {url}: {e}")
                return None
        return file_path

    def calculate_days_on_sale(self, created_at):
        try:
            created_at_datetime = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            delta = now - created_at_datetime
            days = delta.days
            hours = delta.seconds // 3600
            return f"{days}d {hours}h"
        except ValueError as e:
            print(f"Error parsing date: {e}")
            return ""

    def apply_filters(self):
        name_filter = self.name_filter.text().lower()
        sticker_filter = self.sticker_filter.text().lower()
        try:
            min_float = float(self.float_min_filter.text()) if self.float_min_filter.text() else None
            max_float = float(self.float_max_filter.text()) if self.float_max_filter.text() else None
        except ValueError:
            min_float = None
            max_float = None

        for row in range(self.inventory_table.rowCount()):
            name_item = self.inventory_table.item(row, 0).text().lower()
            float_value_item = self.inventory_table.item(row, 2).text()
            float_value_item = float(float_value_item) if float_value_item else None

            stickers_widget = self.inventory_table.cellWidget(row, 1)
            sticker_names = ""
            if stickers_widget:
                for i in range(stickers_widget.layout().count()):
                    sticker_label = stickers_widget.layout().itemAt(i).widget()
                    if sticker_label and sticker_label.toolTip():
                        sticker_names += sticker_label.toolTip().lower()

            matches_name = name_filter in name_item
            matches_sticker = sticker_filter in sticker_names
            matches_float = (
                (min_float is None or (float_value_item is not None and float_value_item >= min_float)) and
                (max_float is None or (float_value_item is not None and float_value_item <= max_float))
            )

            self.inventory_table.setRowHidden(row, not (matches_name and matches_sticker and matches_float))
            
    def show_confirmation_dialog(self, message):
        reply = QMessageBox.question(self, "Confirmation", message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes
                        
    def sell_items(self):
        selected_indexes = self.inventory_table.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "Warning", "Please select items to sell.")
            return
        
        successful_sales = []
        already_listed_items = []
        
        # Получаем уникальные Asset ID для явно выбранных строк (видимых)
        selected_asset_ids = set()
        for index in selected_indexes:
            row = index.row()
            if not self.inventory_table.isRowHidden(row):  # Проверка видимости строки
                asset_id_item = self.inventory_table.item(row, 6)
                if asset_id_item and asset_id_item.text():
                    selected_asset_ids.add(asset_id_item.text())
    
        # Проходим по всей таблице и проверяем, какие строки соответствуют выбранным Asset ID
        items_to_sell = []
        for row in range(self.inventory_table.rowCount()):
            asset_id_item = self.inventory_table.item(row, 6)
            if asset_id_item and asset_id_item.text() in selected_asset_ids:
                item_name = self.inventory_table.item(row, 0).text()
                price_input = self.price_input.text().strip()
    
                if not price_input:
                    QMessageBox.warning(self, "Warning", "Price field must be filled.")
                    return
    
                try:
                    price = float(price_input)
                    if price < 0.03:
                        QMessageBox.warning(self, "Warning", "Price cannot be lower than $0.03.")
                        return
                    price = int(price * 100)  # Convert to cents
                except ValueError as e:
                    QMessageBox.warning(self, "Error", f"Invalid price input: {e}")
                    return
                
                items_to_sell.append((row, asset_id_item.text(), item_name, price))
        
        # Подтверждение перед продажей
        if items_to_sell:
            grouped_operations = defaultdict(int)
            for _, _, item_name, price in items_to_sell:
                grouped_operations[(item_name, price)] += 1
            
            confirm_message = "You are about to sell the following items:\n"
            for (item_name, price), count in grouped_operations.items():
                if count > 1:
                    confirm_message += f"{count}x {item_name} for {price / 100:.2f}$\n"
                else:
                    confirm_message += f"{item_name} for {price / 100:.2f}$\n"
            
            if not self.show_confirmation_dialog(confirm_message.strip()):
                return
    
        # Продажа предметов
        for row, asset_id, item_name, price in items_to_sell:
            response = sell_item(API_KEY, asset_id, price)
            if response:
                if "code" in response and response["code"] == 4:
                    QMessageBox.warning(self, "Warning", "The sale price is too high. You need to complete KYC and onboard with Stripe to list this item.")
                    return
    
                listing_id = response.get("id")
                successful_sales.append((item_name, price / 100))
                self.update_item_as_sold(row, price, listing_id)
                time.sleep(0.1)  # Задержка 100 мс
            else:
                already_listed_items.append(item_name)
    
        if successful_sales:
            self.show_grouped_operations(successful_sales)
    
        if already_listed_items:
            QMessageBox.warning(self, "Warning", "The following items are already listed:\n" + "\n".join(already_listed_items))
    
    def show_grouped_operations(self, operations):
        grouped_operations = defaultdict(int)
        
        for item_name, price in operations:
            grouped_operations[(item_name, price)] += 1
        
        messages = []
        for (item_name, price), count in grouped_operations.items():
            if count > 1:
                messages.append(f"{count}x {item_name} {price:.2f}$")
            else:
                messages.append(f"{item_name} {price:.2f}$")
        
        final_message = "\n".join(messages)
        QMessageBox.information(self, "Items Sold", final_message)
           
    def update_item_as_sold(self, row, price, listing_id):
        days_on_sale_item = QTableWidgetItem("0d 0h")
        self.inventory_table.setItem(row, 3, days_on_sale_item)

        price_widget = QWidget()
        price_layout = QHBoxLayout(price_widget)
        price_layout.setContentsMargins(0, 0, 0, 0)

        csfloat_logo = QLabel()
        csfloat_logo.setPixmap(QPixmap(CSFLOAT_LOGO_PATH).scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio))
        price_layout.addWidget(csfloat_logo)

        price_label = QLabel(f" {price / 100:.2f}$")
        price_layout.addWidget(price_label)

        price_layout.addStretch()
        self.inventory_table.setCellWidget(row, 4, price_widget)

        listing_id_item = QTableWidgetItem(listing_id)
        self.inventory_table.setItem(row, 5, listing_id_item)

    def delist_items(self):
        selected_indexes = self.inventory_table.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "Warning", "Please select items to delist.")
            return
    
        items_to_delist = []
    
        # Получаем уникальные Asset ID для явно выбранных строк (видимых)
        selected_asset_ids = set()
        for index in selected_indexes:
            row = index.row()
            if not self.inventory_table.isRowHidden(row):  # Проверка видимости строки
                asset_id_item = self.inventory_table.item(row, 6)
                if asset_id_item and asset_id_item.text():
                    selected_asset_ids.add(asset_id_item.text())
    
        # Проходим по всей таблице и проверяем, какие строки соответствуют выбранным Asset ID
        for row in range(self.inventory_table.rowCount()):
            asset_id_item = self.inventory_table.item(row, 6)
            if asset_id_item and asset_id_item.text() in selected_asset_ids:
                listing_id = self.inventory_table.item(row, 5).text()
                item_name = self.inventory_table.item(row, 0).text()
                if not listing_id:
                    QMessageBox.warning(self, "Warning", f"Selected item {item_name} is not listed for sale.")
                    continue
    
                items_to_delist.append((row, listing_id, item_name))
    
        # Подтверждение перед снятием с продажи
        if items_to_delist:
            grouped_items = defaultdict(int)
            for _, _, item_name in items_to_delist:
                grouped_items[item_name] += 1
    
            confirm_message = "You are about to delist the following items:\n"
            for item_name, count in grouped_items.items():
                if count > 1:
                    confirm_message += f"{count}x {item_name}\n"
                else:
                    confirm_message += f"{item_name}\n"
    
            if not self.show_confirmation_dialog(confirm_message.strip()):
                return
    
        # Снятие предметов с продажи
        items_delisted = []
        for row, listing_id, item_name in items_to_delist:
            response = delete_item(API_KEY, listing_id)
            if response:
                items_delisted.append(item_name)  # Добавляем только название предмета
                self.update_item_as_unsold(row)
                time.sleep(0.1)  # Задержка 100 мс
            else:
                QMessageBox.warning(self, "Error", f"Failed to delist item {item_name}.")
    
        if items_delisted:
            self.show_delisted_items(items_delisted)
    
    def show_delisted_items(self, items):
        grouped_items = defaultdict(int)
    
        for item in items:
            grouped_items[item] += 1
    
        messages = []
        for item, count in grouped_items.items():
            if count > 1:
                messages.append(f"{count}x {item}")
            else:
                messages.append(item)
    
        final_message = "\n".join(messages)
        QMessageBox.information(self, "Items Delisted", final_message)

    def update_item_as_unsold(self, row):
        self.inventory_table.setItem(row, 3, QTableWidgetItem(""))  # Убираем информацию о днях на продаже
        self.inventory_table.setCellWidget(row, 4, QWidget())  # Убираем цену и лого
        self.inventory_table.setItem(row, 5, QTableWidgetItem(""))  # Убираем listing_id

    def change_item_price(self):
        selected_indexes = self.inventory_table.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "Warning", "Please select items to change the price.")
            return
        
        items_to_change = []
        
        # Получаем уникальные Asset ID для явно выбранных строк (видимых)
        selected_asset_ids = set()
        for index in selected_indexes:
            row = index.row()
            if not self.inventory_table.isRowHidden(row):  # Проверка видимости строки
                asset_id_item = self.inventory_table.item(row, 6)
                if asset_id_item and asset_id_item.text():
                    selected_asset_ids.add(asset_id_item.text())
    
        # Проходим по всей таблице и проверяем, какие строки соответствуют выбранным Asset ID
        for row in range(self.inventory_table.rowCount()):
            asset_id_item = self.inventory_table.item(row, 6)
            if asset_id_item and asset_id_item.text() in selected_asset_ids:
                listing_id = self.inventory_table.item(row, 5).text()
                if not listing_id:
                    QMessageBox.warning(self, "Warning", "Price can only be changed for listed items.")
                    continue
    
                item_name = self.inventory_table.item(row, 0).text()
                current_price_widget = self.inventory_table.cellWidget(row, 4)
                if not current_price_widget:
                    QMessageBox.warning(self, "Warning", "Unable to retrieve current price widget.")
                    continue
    
                current_price = float(current_price_widget.layout().itemAt(1).widget().text().strip().replace("$", ""))
    
                try:
                    price_input = self.price_input.text().strip()
                    if not price_input:
                        QMessageBox.warning(self, "Warning", "Price field must be filled.")
                        return
    
                    new_price = float(price_input)
                    if new_price < 0.03:
                        QMessageBox.warning(self, "Warning", "Price cannot be lower than $0.03.")
                        return
    
                    new_price = int(new_price * 100)  # Convert to cents
                except ValueError as e:
                    QMessageBox.warning(self, "Error", f"Invalid price input: {e}")
                    return
    
                items_to_change.append((row, asset_id_item.text(), item_name, current_price, new_price / 100))
        
        # Подтверждение перед изменением цены
        if items_to_change:
            grouped_operations = defaultdict(int)
            for _, _, item_name, current_price, new_price in items_to_change:
                grouped_operations[(item_name, current_price, new_price)] += 1
    
            confirm_message = "You are about to change the price for the following items:\n"
            for (item_name, current_price, new_price), count in grouped_operations.items():
                if count > 1:
                    confirm_message += f"{count}x {item_name} {current_price:.2f}$ → {new_price:.2f}$\n"
                else:
                    confirm_message += f"{item_name} {current_price:.2f}$ → {new_price:.2f}$\n"
    
            if not self.show_confirmation_dialog(confirm_message.strip()):
                return
    
        successful_changes = []
        
        # Изменение цены на предметы
        for row, asset_id, item_name, current_price, new_price in items_to_change:
            listing_id = self.inventory_table.item(row, 5).text()
            if listing_id:
                response = change_price(API_KEY, listing_id, int(new_price * 100))
                if response:
                    successful_changes.append((item_name, current_price, new_price))
                    self.update_item_price(row, int(new_price * 100))
                    time.sleep(0.1)  # Задержка 100 мс
    
        if successful_changes:
            self.show_price_change_operations(successful_changes)
    
    def show_price_change_operations(self, operations):
        grouped_operations = defaultdict(int)
        
        # Группируем предметы по названию, старой и новой цене
        for item_name, old_price, new_price in operations:
            key = (item_name, old_price, new_price)
            grouped_operations[key] += 1
    
        # Формируем сообщение
        messages = []
        for (item_name, old_price, new_price), count in grouped_operations.items():
            if count > 1:
                messages.append(f"{count}x {item_name} {old_price:.2f}$ → {new_price:.2f}$")
            else:
                messages.append(f"{item_name} {old_price:.2f}$ → {new_price:.2f}$")
    
        final_message = "\n".join(messages)
        QMessageBox.information(self, "Price Change Confirmation", f"Price changed for items:\n{final_message}")
            
    def update_item_price(self, row, new_price):
        price_widget = QWidget()
        price_layout = QHBoxLayout(price_widget)
        price_layout.setContentsMargins(0, 0, 0, 0)

        csfloat_logo = QLabel()
        csfloat_logo.setPixmap(QPixmap(CSFLOAT_LOGO_PATH).scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio))
        price_layout.addWidget(csfloat_logo)

        price_label = QLabel(f" {new_price / 100:.2f}$")
        price_layout.addWidget(price_label)

        price_layout.addStretch()
        self.inventory_table.setCellWidget(row, 4, price_widget)

    def show_user_info(self):
        if not self.user_info:
            QMessageBox.warning(self, "Warning", "User info not loaded.")
            return
            # Подсчитайте общую сумму выставленных скинов
        total_exhibited = sum(item['price'] for item in self.stall) / 100  # Суммируем цены всех выставленных скинов
    
        dialog = QDialog(self)
        dialog.setWindowTitle("User Information")
        layout = QFormLayout(dialog)

        layout.addRow("Steam ID:", QLabel(self.user_info.get("steam_id", "N/A")))
        layout.addRow("Username:", QLabel(self.user_info.get("username", "N/A")))
        layout.addRow("Balance:", QLabel(f"{self.user_info.get('balance', 0) / 100:.2f}$"))
        layout.addRow("Total Sales:", QLabel(f"{self.user_info.get('total_sales', 0) / 100:.2f}$"))
        layout.addRow("Total Purchases:", QLabel(f"{self.user_info.get('total_purchases', 0) / 100:.2f}$"))
        layout.addRow("Median Trade Time:", QLabel(f"{self.user_info.get('median_trade_time', 0) / 60:.0f} minutes"))
        layout.addRow("Total Avoided Trades:", QLabel(str(self.user_info.get("total_avoided_trades", 0))))
        layout.addRow("Total Failed Trades:", QLabel(str(self.user_info.get("total_failed_trades", 0))))
        layout.addRow("Total Verified Trades:", QLabel(str(self.user_info.get("total_verified_trades", 0))))
        layout.addRow("Total Trades:", QLabel(str(self.user_info.get("total_trades", 0))))
        layout.addRow("Total Exhibited:", QLabel(f"{total_exhibited:.2f}$"))  # Добавляем строку с общей суммой цен
         
        dialog.exec()

def main():
    app = QApplication(sys.argv)
    window = SteamInventoryApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
