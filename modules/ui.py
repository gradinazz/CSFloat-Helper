import os
import time
import urllib.error
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QFormLayout, QDialog, QSpacerItem, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, QSettings, QPersistentModelIndex, QSize
from datetime import datetime, timezone
from collections import defaultdict

from modules.api import get_user_info, get_inventory_data, get_stall_data, sell_item, delete_item, change_price
from modules.utils import load_config, cache_image, calculate_days_on_sale

CSFLOAT_LOGO_PATH = "csfloat_logo.png"


class SteamInventoryApp(QMainWindow):
    max_price = 10000000  # Максимальная цена в центах (10000000 = $100000.00)
    min_price = 3  # Минимальная цена в центах ($0.03)

    def __init__(self, api_keys):
        super().__init__()
        self.api_keys = api_keys
        self.settings = QSettings("MyCompany", "SteamInventoryApp")
        self.default_api_key = self.settings.value("default_api_key", api_keys[
            0])  # Загружаем последний выбранный ключ или первый ключ по умолчанию
        self.user_infos = []  # Список для хранения информации о пользователях

        self.initUI()
        self.load_data()  # Загружаем данные при инициализации

        self.setWindowTitle("CSFloat Helper")
        self.setFixedSize(740, 750)

        self.price_sort_order = Qt.SortOrder.AscendingOrder
        self.days_sort_order = Qt.SortOrder.AscendingOrder
        self.name_sort_order = Qt.SortOrder.AscendingOrder
        self.float_sort_order = Qt.SortOrder.AscendingOrder
        self.last_sorted_column = None
        self.last_sort_order = None

        self.inventory = []
        self.stall = []

    def set_default_api_key(self, api_key):
        self.default_api_key = api_key
        self.settings.setValue("default_api_key", api_key)  # Сохраняем выбранный ключ
        self.clear_data()  # Очищаем старые данные перед загрузкой новых
        self.load_inventory()  # Перезагружаем инвентарь с новым API ключом
        self.update_avatar()  # Обновляем аватарку с новым API ключом
        if hasattr(self, 'avatar_info_dialog') and self.avatar_info_dialog.isVisible():
            self.avatar_info_dialog.close()  # Закрываем окно show_avatar_info, если оно существует и открыто

    def show_avatar_info(self):
        self.avatar_info_dialog = QDialog(self)
        self.avatar_info_dialog.setWindowTitle("Change account")
        outer_layout = QVBoxLayout(self.avatar_info_dialog)

        horizontal_layout = None  # Переменная для отслеживания текущего горизонтального макета

        # Проходим по всем API-ключам и загружаем информацию
        for i, user_info in enumerate(self.user_infos):
            if i % 2 == 0:  # Каждые два элемента создаем новый горизонтальный макет
                horizontal_layout = QHBoxLayout()
                outer_layout.addLayout(horizontal_layout)

            avatar_url = user_info.get("avatar")
            avatar_path = cache_image(avatar_url) if avatar_url else None
            vertical_layout = QVBoxLayout()

            if avatar_path:
                # Создаем вертикальные спейсер для отступа сверху
                vertical_layout.addSpacerItem(
                    QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

                avatar_button = QPushButton(self.avatar_info_dialog)
                avatar_button.setFixedSize(100, 100)
                avatar_button.setIcon(QIcon(avatar_path))
                avatar_button.setIconSize(QSize(100, 100))
                avatar_button.setFlat(True)  # Убираем границы кнопки
                avatar_button.setStyleSheet("background-color: transparent;")  # Убираем фон кнопки
                vertical_layout.addWidget(avatar_button, alignment=Qt.AlignmentFlag.AlignHCenter)

                # Создаем вертикальные спейсеры для отступа снизу
                vertical_layout.addSpacerItem(
                    QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

                username_label = QLabel(user_info.get("username", "Unknown"))
                vertical_layout.addWidget(username_label, alignment=Qt.AlignmentFlag.AlignHCenter)

                balance_label = QLabel(f"Balance: {user_info.get('balance', 0) / 100:.2f}$")
                vertical_layout.addWidget(balance_label, alignment=Qt.AlignmentFlag.AlignHCenter)

                set_default_button = QPushButton("Change to this account", self.avatar_info_dialog)
                set_default_button.clicked.connect(lambda _, key=user_info['api_key']: self.set_default_api_key(key))
                vertical_layout.addWidget(set_default_button, alignment=Qt.AlignmentFlag.AlignHCenter)

            horizontal_layout.addLayout(vertical_layout)

        self.avatar_info_dialog.exec()

    def initUI(self):
        central_widget = QWidget(self)
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

        # Кнопка для отображения аватарки (замаскированная как кнопка)
        self.avatar_info_button = QPushButton(self)
        self.avatar_info_button.setFixedSize(70, 70)
        self.avatar_info_button.setIconSize(QSize(70, 70))
        self.avatar_info_button.setFlat(True)  # Убираем границы кнопки
        self.avatar_info_button.clicked.connect(self.show_avatar_info)
        self.avatar_info_button.move(640, 20)  # Устанавливаем координаты

        self.update_avatar()  # Устанавливаем аватарку при загрузке

        # Настраиваем таблицу инвентаря
        self.inventory_table = QTableWidget(self)
        self.inventory_table.setColumnCount(9)
        self.inventory_table.setHorizontalHeaderLabels([
            "Name", "Stickers", "Float Value", "Days on Sale", "Price", "Listing ID", "Asset ID", "Created At",
            "Price Value"
        ])
        self.inventory_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.inventory_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.inventory_table.setSortingEnabled(True)
        self.inventory_table.horizontalHeader().setSectionsClickable(True)
        self.inventory_table.horizontalHeader().setSortIndicatorShown(True)

        # Устанавливаем таблицу ниже элементов фильтрации и кнопок
        self.inventory_table.setFixedSize(700, 600)  # Размер таблицы
        self.inventory_table.move(20, 100)  # Координаты таблицы

        self.inventory_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.inventory_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.inventory_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.inventory_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.inventory_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.inventory_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        self.inventory_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.inventory_table.setColumnHidden(7, True)
        self.inventory_table.setColumnHidden(8, True)
        self.inventory_table.horizontalHeader().sectionClicked.connect(self.handle_header_click)

        self.load_column_widths()

    def load_data(self):
        # Загрузка данных для всех ключей
        self.user_infos = []
        valid_api_keys = [key for key in self.api_keys if key != "YOUR_API_KEY"]

        if not valid_api_keys:
            QMessageBox.critical(self, "Error", "No valid API keys found. Please update your configuration.")
            return

        for api_key in valid_api_keys:
            user_info = get_user_info(api_key)
            if user_info:
                user_info['api_key'] = api_key
                # Преобразуем "know_your_customer" в более понятный формат
                if user_info.get("know_your_customer") == "uninitiated":
                    user_info["know_your_customer"] = "No"
                elif user_info.get("know_your_customer") == "approved":
                    user_info["know_your_customer"] = "Yes"
                self.user_infos.append(user_info)
            else:
                QMessageBox.warning(self, "Error", f"Failed to load user information for API key: {api_key}")

        if not self.user_infos:
            QMessageBox.critical(self, "Error", "No valid user information loaded. Please check your API keys.")
            return

        # Если default_api_key не в списке загруженных, выбираем первый из загруженных
        if not any(info['api_key'] == self.default_api_key for info in self.user_infos):
            self.default_api_key = self.user_infos[0]['api_key']

        # Загружаем инвентарь для дефолтного API ключа
        self.load_inventory()
        # Обновляем аватарку для дефолтного API ключа
        self.update_avatar()

    def update_avatar(self):
        if not self.user_infos:
            return

        # Используем информацию из первого элемента списка, который соответствует дефолтному API ключу
        user_info = next(info for info in self.user_infos if info['api_key'] == self.default_api_key)
        avatar_url = user_info.get("avatar")
        avatar_path = cache_image(avatar_url) if avatar_url else None
        if avatar_path:
            self.avatar_info_button.setIcon(QIcon(avatar_path))

    def clear_data(self):
        self.inventory = []  # Очищаем список инвентаря
        self.stall = []  # Очищаем список предметов на продаже
        self.inventory_table.clearContents()  # Очищаем таблицу инвентаря

    def load_stall_data(self):
        if not self.user_infos:
            return

        user_info = next((info for info in self.user_infos if info['api_key'] == self.default_api_key), None)
        if not user_info:
            return

        steam_id = user_info.get("steam_id")
        if steam_id:
            self.stall = get_stall_data(self.default_api_key, steam_id)
            self.populate_inventory_table()  # Обновляем таблицу с учетом новых данных
        else:
            self.stall = []  # Если steam_id не найден, очищаем stall

    def load_inventory(self):
        # Отключаем сортировку на время загрузки данных
        self.inventory_table.setSortingEnabled(False)

        # Загружаем данные
        self.inventory = get_inventory_data(self.default_api_key)
        if self.inventory is None:
            self.inventory = []  # Если инвентарь не был загружен, создаем пустой список

        # Загружаем информацию о продаже для текущего ключа
        self.load_stall_data()

        # Включаем сортировку после загрузки данных
        self.inventory_table.setSortingEnabled(True)

    def handle_header_click(self, logicalIndex):
        if logicalIndex == 0:
            self.name_sort_order = Qt.SortOrder.DescendingOrder if self.name_sort_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
            self.inventory_table.sortItems(logicalIndex, self.name_sort_order)
            self.last_sorted_column = logicalIndex
            self.last_sort_order = self.name_sort_order
        elif logicalIndex == 2:
            self.float_sort_order = Qt.SortOrder.DescendingOrder if self.float_sort_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
            self.inventory_table.sortItems(logicalIndex, self.float_sort_order)
            self.last_sorted_column = logicalIndex
            self.last_sort_order = self.float_sort_order
        elif logicalIndex == 4:
            self.price_sort_order = Qt.SortOrder.DescendingOrder if self.price_sort_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
            self.inventory_table.sortItems(8, self.price_sort_order)
            self.last_sorted_column = 8
            self.last_sort_order = self.price_sort_order
        elif logicalIndex == 3:
            self.days_sort_order = Qt.SortOrder.DescendingOrder if self.days_sort_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
            self.inventory_table.sortItems(7, self.days_sort_order)
            self.last_sorted_column = 7
            self.last_sort_order = self.days_sort_order
        else:
            self.inventory_table.sortItems(logicalIndex)
            self.last_sorted_column = logicalIndex
            self.last_sort_order = self.inventory_table.horizontalHeader().sortIndicatorOrder()

    def apply_last_sort(self):
        if self.last_sorted_column is not None and self.last_sort_order is not None:
            self.inventory_table.sortItems(self.last_sorted_column, self.last_sort_order)

    def populate_inventory_table(self):
        self.inventory_table.setRowCount(0)  # Очистка таблицы перед заполнением

        stall_dict = {item['item']['asset_id']: item for item in self.stall}  # Создаем словарь по asset_id

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
                sticker_path = cache_image(sticker_icon_url)
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
            float_value_item = QTableWidgetItem(f"{float_value:.14f}" if float_value is not None else "")
            self.inventory_table.setItem(row_position, 2, float_value_item)

            stall_item = stall_dict.get(asset_id)
            if stall_item:
                days_on_sale = calculate_days_on_sale(stall_item['created_at'])
                days_on_sale_item = QTableWidgetItem(days_on_sale)
                self.inventory_table.setItem(row_position, 3, days_on_sale_item)

                created_at_item = QTableWidgetItem(stall_item['created_at'])
                self.inventory_table.setItem(row_position, 7, created_at_item)

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

                price_value_item = QTableWidgetItem()
                price_value_item.setData(Qt.ItemDataRole.DisplayRole, stall_item['price'])
                price_value_item.setData(Qt.ItemDataRole.UserRole, stall_item['price'])
                self.inventory_table.setItem(row_position, 8, price_value_item)
            else:
                self.inventory_table.setItem(row_position, 3, QTableWidgetItem(""))
                self.inventory_table.setItem(row_position, 4, QTableWidgetItem(""))
                self.inventory_table.setItem(row_position, 5, QTableWidgetItem(""))
                self.inventory_table.setColumnHidden(5, True)

            asset_id_item = QTableWidgetItem(asset_id)
            self.inventory_table.setItem(row_position, 6, asset_id_item)
            self.inventory_table.setColumnHidden(6, True)

        self.inventory_table.setColumnHidden(8, True)

    def load_column_widths(self):
        for i in range(self.inventory_table.columnCount()):
            width = self.settings.value(f"column_width_{i}", type=int)
            if width:
                self.inventory_table.setColumnWidth(i, width)

    def save_column_widths(self):
        for i in range(self.inventory_table.columnCount()):
            self.settings.setValue(f"column_width_{i}", self.inventory_table.columnWidth(i))

    def closeEvent(self, event):
        self.save_column_widths()
        event.accept()

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
        reply = QMessageBox.question(self, "Confirmation", message,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes

    def sell_items(self):
        # Проверяем, содержит ли поле для цены знак %
        price_input = self.price_input.text().strip()
        if "%" in price_input:
            QMessageBox.warning(self, "Warning", "Please remove the '%' sign from the price field before selling.")
            return  # Прекращаем выполнение функции, пока пользователь не уберет знак %

        selected_indexes = self.inventory_table.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "Warning", "Please select items to sell.")
            return

        successful_sales = []
        already_listed_items = []

        selected_asset_ids = set()
        for index in selected_indexes:
            row = index.row()
            if not self.inventory_table.isRowHidden(row):
                asset_id_item = self.inventory_table.item(row, 6)
                if asset_id_item and asset_id_item.text():
                    selected_asset_ids.add(asset_id_item.text())

        items_to_sell = []
        for row in range(self.inventory_table.rowCount()):
            asset_id_item = self.inventory_table.item(row, 6)
            if asset_id_item and asset_id_item.text() in selected_asset_ids:
                item_name = self.inventory_table.item(row, 0).text()

                # Проверка на наличие данных в колонках 7 или 8 (предмет уже продается)
                created_at_item = self.inventory_table.item(row, 7)
                price_value_item = self.inventory_table.item(row, 8)
                if created_at_item and created_at_item.text() or price_value_item and price_value_item.text():
                    already_listed_items.append(item_name)
                    continue

                if not price_input:
                    QMessageBox.warning(self, "Warning", "Price field must be filled.")
                    return

                try:
                    price = float(price_input)
                    if price < self.min_price / 100:
                        QMessageBox.warning(self, "Warning", f"Price cannot be lower than ${self.min_price / 100:.2f}.")
                        return
                    if price * 100 > self.max_price:
                        QMessageBox.warning(self, "Warning",
                                            f"Maximum allowed price is ${self.max_price / 100:.2f} USD")
                        return
                    price = int(price * 100)
                except ValueError as e:
                    QMessageBox.warning(self, "Error", f"Invalid price input: {e}")
                    return

                items_to_sell.append((row, asset_id_item.text(), item_name, price))

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

        for row, asset_id, item_name, price in items_to_sell:
            try:
                response = sell_item(self.default_api_key, asset_id, price)
                listing_id = response.get("id") if response else None
                if listing_id:
                    successful_sales.append((item_name, price / 100))
                    self.update_item_as_sold(row, price, listing_id)
                    time.sleep(0.1)
            except ValueError as ve:
                QMessageBox.warning(self, "Warning", str(ve))
                return
            except urllib.error.HTTPError as http_err:
                QMessageBox.warning(self, "Error", f"HTTP error occurred: {http_err}")
                return
            except Exception as e:
                QMessageBox.warning(self, "Error", f"{str(e)}")
                return

        if successful_sales:
            self.show_grouped_operations(successful_sales)

        if already_listed_items:
            QMessageBox.warning(self, "Warning",
                                "The following items are already listed:\n" + "\n".join(already_listed_items))

    def change_item_price(self):
        selected_indexes = self.inventory_table.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "Warning", "Please select items to change the price.")
            return

        items_to_change = []

        selected_asset_ids = set()
        for index in selected_indexes:
            row = index.row()
            if not self.inventory_table.isRowHidden(row):
                asset_id_item = self.inventory_table.item(row, 6)
                if asset_id_item and asset_id_item.text():
                    selected_asset_ids.add(asset_id_item.text())

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

                # Получаем текущую цену
                current_price = float(current_price_widget.layout().itemAt(1).widget().text().strip().replace("$", ""))

                try:
                    price_input = self.price_input.text().strip()
                    if not price_input:
                        QMessageBox.warning(self, "Warning", "Price field must be filled.")
                        return

                    # Проверяем, указано ли процентное изменение
                    if price_input.endswith('%'):
                        percentage_str = price_input[:-1].strip()

                        # Проверка на случай, если указано только "%" без числа
                        if not percentage_str:
                            QMessageBox.warning(self, "Warning", "Please enter a number before the '%' symbol.")
                            return

                        # Попытка преобразовать строку в число для процента
                        try:
                            percentage_change = float(percentage_str)
                        except ValueError:
                            QMessageBox.warning(self, "Warning", "Only numbers are accepted for percentage changes.")
                            return

                        # Если введен 0%, предупреждаем, что цена не изменится
                        if percentage_change == 0:
                            QMessageBox.warning(self, "Warning", "Price will not change.")
                            return

                        is_increase = percentage_change > 0

                        # Рассчитываем новую цену в зависимости от процента
                        if is_increase:
                            new_price = current_price * (1 + percentage_change / 100)
                        else:
                            new_price = current_price * (
                                        1 + percentage_change / 100)  # Правильная обработка отрицательного процента

                        # Округляем новую цену до целого числа в центах
                        new_price_cents = int(round(new_price * 100))

                        # Проверяем, изменилась ли цена
                        if new_price_cents == int(current_price * 100):
                            QMessageBox.warning(self, "Warning", "Price will not change.")
                            return

                    # Проверяем, если число начинается с + или -
                    elif price_input.startswith('+') or price_input.startswith('-'):
                        try:
                            change_value = float(price_input)  # Преобразуем изменение в число
                        except ValueError:
                            QMessageBox.warning(self, "Error",
                                                "Only valid numeric values are accepted for price changes.")
                            return

                        # Рассчитываем новую цену
                        new_price = current_price + change_value

                        # Округляем цену до целого числа (в центах)
                        new_price_cents = int(round(new_price * 100))

                        # Проверяем, изменилась ли цена
                        if new_price_cents == int(current_price * 100):
                            QMessageBox.warning(self, "Warning", "Price will not change.")
                            return

                    else:
                        # Проверка, является ли введенное значение числом
                        try:
                            new_price = float(price_input)
                        except ValueError:
                            QMessageBox.warning(self, "Error", "Only numbers or percentage changes are accepted.")
                            return

                    if new_price * 100 < self.min_price:
                        QMessageBox.warning(self, "Warning", f"Price cannot be lower than ${self.min_price / 100:.2f}.")
                        return
                    if new_price * 100 > self.max_price:
                        QMessageBox.warning(self, "Warning",
                                            f"Maximum allowed price is ${self.max_price / 100:.2f} USD")
                        return

                    # Округляем цену до целого числа (в центах)
                    new_price = int(round(new_price * 100))

                except ValueError as e:
                    QMessageBox.warning(self, "Error", f"Invalid price input: {e}")
                    return

                # Добавляем элемент в список для изменения цены
                items_to_change.append((row, asset_id_item.text(), item_name, current_price, new_price / 100))

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

        for row, asset_id, item_name, current_price, new_price in items_to_change:
            listing_id = self.inventory_table.item(row, 5).text()
            if listing_id:
                try:
                    response = change_price(self.default_api_key, listing_id, int(new_price * 100))
                    if response:
                        successful_changes.append((item_name, current_price, new_price))
                        self.update_item_price(row, int(new_price * 100))
                        time.sleep(0.1)
                except ValueError as ve:
                    QMessageBox.warning(self, "Warning", str(ve))
                    return
                except urllib.error.HTTPError as http_err:
                    QMessageBox.warning(self, "Error", f"HTTP error occurred: {http_err}")
                    return
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"An unexpected error occurred: {str(e)}")
                    return

        if successful_changes:
            self.show_price_change_operations(successful_changes)

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

        created_at_item = QTableWidgetItem(datetime.now(timezone.utc).isoformat())
        self.inventory_table.setItem(row, 7, created_at_item)

        price_value_item = QTableWidgetItem()
        price_value_item.setData(Qt.ItemDataRole.DisplayRole, price)
        price_value_item.setData(Qt.ItemDataRole.UserRole, price)
        self.inventory_table.setItem(row, 8, price_value_item)

        if self.last_sorted_column is not None and self.last_sort_order is not None:
            self.inventory_table.sortItems(self.last_sorted_column, self.last_sort_order)
        self.apply_last_sort()

    def delist_items(self):
        selected_indexes = self.inventory_table.selectionModel().selectedRows()
        if not selected_indexes:
            QMessageBox.warning(self, "Warning", "Please select items to delist.")
            return

        items_to_delist = []
        persistent_indexes = []

        for index in selected_indexes:
            row = index.row()
            if not self.inventory_table.isRowHidden(row):
                persistent_index = QPersistentModelIndex(self.inventory_table.model().index(row, 0))
                persistent_indexes.append(persistent_index)
                listing_id = self.inventory_table.item(row, 5).text()
                item_name = self.inventory_table.item(row, 0).text()
                items_to_delist.append((persistent_index, listing_id, item_name))

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

        self.inventory_table.setSortingEnabled(False)

        items_delisted = []
        for persistent_index, listing_id, item_name in items_to_delist:
            row = persistent_index.row()
            response = delete_item(self.default_api_key, listing_id)
            if response:
                items_delisted.append(item_name)
                self.update_item_as_unsold(row)
                time.sleep(0.1)
            else:
                QMessageBox.warning(self, "Error", f"Failed to delist item {item_name}.")

        if items_delisted:
            self.show_delisted_items(items_delisted)

        self.inventory_table.setSortingEnabled(True)
        self.inventory_table.model().layoutChanged.emit()

        self.apply_last_sort()

    def update_item_as_unsold(self, row):
        self.inventory_table.setItem(row, 3, QTableWidgetItem(""))
        self.inventory_table.setCellWidget(row, 4, QWidget())
        self.inventory_table.setItem(row, 5, QTableWidgetItem(""))
        self.inventory_table.setItem(row, 7, QTableWidgetItem(""))
        self.inventory_table.setItem(row, 8, QTableWidgetItem(""))
        self.inventory_table.setRowHidden(row, False)

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

    def show_price_change_operations(self, operations):
        grouped_operations = defaultdict(int)

        for item_name, old_price, new_price in operations:
            key = (item_name, old_price, new_price)
            grouped_operations[key] += 1

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

        created_at_item = QTableWidgetItem(datetime.now(timezone.utc).isoformat())
        self.inventory_table.setItem(row, 7, created_at_item)

        price_value_item = QTableWidgetItem()
        price_value_item.setData(Qt.ItemDataRole.DisplayRole, new_price)
        price_value_item.setData(Qt.ItemDataRole.UserRole, new_price)
        self.inventory_table.setItem(row, 8, price_value_item)

        if self.last_sorted_column is not None and self.last_sort_order is not None:
            self.inventory_table.sortItems(self.last_sorted_column, self.last_sort_order)
        self.apply_last_sort()

    def show_user_info(self):
        user_info = next(info for info in self.user_infos if info['api_key'] == self.default_api_key)
        if not user_info:
            QMessageBox.warning(self, "Warning", "User info not loaded.")
            return

        total_exhibited = sum(item['price'] for item in self.stall) / 100

        dialog = QDialog(self)
        dialog.setWindowTitle("User Information")
        layout = QFormLayout(dialog)

        statistics = user_info.get("statistics", {})

        layout.addRow("Steam ID:", QLabel(user_info.get("steam_id", "N/A")))
        layout.addRow("Username:", QLabel(user_info.get("username", "N/A")))
        layout.addRow("KYC:", QLabel(user_info.get("know_your_customer", "N/A")))
        layout.addRow("Balance:", QLabel(f"{user_info.get('balance', 0) / 100:.2f}$"))
        layout.addRow("Total Sales:", QLabel(f"{statistics.get('total_sales', 0) / 100:.2f}$"))
        layout.addRow("Total Purchases:", QLabel(f"{statistics.get('total_purchases', 0) / 100:.2f}$"))
        layout.addRow("Median Trade Time:", QLabel(f"{statistics.get('median_trade_time', 0) / 60:.0f} minutes"))
        layout.addRow("Total Avoided Trades:", QLabel(str(statistics.get("total_avoided_trades", 0))))
        layout.addRow("Total Failed Trades:", QLabel(str(statistics.get("total_failed_trades", 0))))
        layout.addRow("Total Verified Trades:", QLabel(str(statistics.get("total_verified_trades", 0))))
        layout.addRow("Total Trades:", QLabel(str(statistics.get("total_trades", 0))))
        layout.addRow("Total Exhibited:", QLabel(f"{total_exhibited:.2f}$"))

        dialog.exec()
