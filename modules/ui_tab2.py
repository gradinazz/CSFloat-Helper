# modules/ui_tab2.py
from PyQt6.QtCore import Qt, QSettings, QSize, pyqtSlot
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QWidget, QTableWidget, QTableWidgetItem, QPushButton, QAbstractItemView, QHeaderView, QLabel, QCheckBox, QMessageBox, QHBoxLayout
from modules.api import get_buy_orders, delete_order_by_id
from modules.workers import ApiWorker

import os
import re
import logging
from datetime import datetime, timezone
import pandas as pd
from collections import defaultdict

# Настройка логирования
logging.basicConfig(filename='app.log', level=logging.ERROR,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Получение текущего каталога скрипта
script_dir = os.path.dirname(os.path.abspath(__file__))

# Конструирование путей к CSV файлам относительно каталога скрипта
skins_csv_path = os.path.join(script_dir, '..', 'utils', 'skins_base.csv')
stickers_csv_path = os.path.join(script_dir, '..', 'utils', 'stickers_base.csv')

# Загрузка CSV файлов
try:
    skins_df = pd.read_csv(skins_csv_path)
    stickers_df = pd.read_csv(stickers_csv_path)
except Exception as e:
    logging.error(f"Error loading CSV files: {str(e)}")
    skins_df = pd.DataFrame()
    stickers_df = pd.DataFrame()

# Карта соответствия редкости
rarity_map = {
    0: "Consumer (Common)",
    1: "Industrial (Un-common)",
    2: "Mil-spec (Rare)",
    3: "Restricted (Mythical)",
    4: "Classified (Legendary)",
    5: "Covert (Ancient)",
    6: "Contraband (Immortal)"
}

class Tab2(QWidget):
    def __init__(self, api_keys, icon_path, parent=None):
        super().__init__(parent)
        self.api_keys = api_keys
        self.icon_path = icon_path

        # Инициализация QSettings для хранения предпочтений
        self.settings = QSettings("MyCompany", "SteamInventoryApp")

        # Загрузка CSV файлов в экземпляр класса
        self.skins_df = skins_df
        self.stickers_df = stickers_df

        # Инициализация UI
        self.initUI()

    def initUI(self):
                # Создание и позиционирование кнопки "Delete Selected Orders"
        self.delete_button = QPushButton("Delete Selected Orders", self)
        self.delete_button.setFixedSize(150, 40)
        self.delete_button.move(20, 20)
        self.delete_button.clicked.connect(self.delete_selected_order)
        self.delete_button.setStyleSheet("""
            QPushButton {
                border: 1px solid #D1B3FF;
                border-radius: 5px;
                background-color: #F0F0F0;
            }
            QPushButton:pressed {
                background-color: #D1B3FF;
            }
        """)

        # Создание и позиционирование кнопки "Delete All Orders"
        self.delete_all_button = QPushButton("Delete All Orders", self)
        self.delete_all_button.setFixedSize(150, 40)
        self.delete_all_button.move(200, 20)
        self.delete_all_button.clicked.connect(self.delete_all_orders)
        self.delete_all_button.setStyleSheet("""
            QPushButton {
                border: 1px solid #D1B3FF;
                border-radius: 5px;
                background-color: #F0F0F0;
            }
            QPushButton:pressed {
                background-color: #D1B3FF;
            }
        """)

        # Настройка таблицы и позиционирование её на форме
        self.table = QTableWidget(self)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["", "Order", "Qty", "Price", "Time", "Order ID", "API Key"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)

        # Установка размера и позиции таблицы
        self.table.setFixedSize(730, 600)
        self.table.move(20, 132)

        # Отключение изменения размера колонки Lock
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 24)  # Ширина колонки Lock (для чекбокса)

        # Установка иконки для колонки Lock
        lock_icon_path = os.path.join(self.icon_path, 'lock.png')
        if os.path.exists(lock_icon_path):
            lock_icon = QIcon(lock_icon_path)
            self.table.horizontalHeaderItem(0).setIcon(lock_icon)
        else:
            logging.error(f"Lock icon not found at path: {lock_icon_path}")

        # Установка ширины остальных колонок
        self.table.setColumnWidth(1, 530)  # Order
        self.table.setColumnWidth(2, 40)   # Qty
        self.table.setColumnWidth(3, 60)  # Price
        self.table.setColumnWidth(4, 50)  # Time
        self.table.setColumnWidth(5, 100)  # Order ID
        self.table.setColumnWidth(6, 100)  # API Key

        # Скрытие колонок Order ID и API Key
        self.table.setColumnHidden(5, True)  # Order ID
        self.table.setColumnHidden(6, True)  # API Key

        # Загрузка сохранённых ширин колонок
        self.load_column_widths()

    def create_order_row(self, order, api_key):
        """Создание строки ордера для таблицы."""
        row = []

        # Чекбокс блокировки
        lock_checkbox = QCheckBox(self)
        lock_checkbox.setStyleSheet("margin-left: 5px; margin-right: auto;")  # Выравнивание чекбокса влево
        cell_widget = QWidget()
        cell_layout = QHBoxLayout(cell_widget)
        cell_layout.addWidget(lock_checkbox)
        cell_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        row.append(cell_widget)

        # Описание ордера
        if 'expression' in order and order['expression']:
            order_description = self.generate_item_name(order.get('expression'))
        elif 'market_hash_name' in order and order['market_hash_name']:
            # Создание QLabel с [market_hash_name]
            order_description = QLabel(f"[{order['market_hash_name']}]")
            order_description.setFont(self.font())
        else:
            order_description = QLabel("Unknown Order")
            order_description.setFont(self.font())

        if isinstance(order_description, QWidget):
            row.append(order_description)
        else:
            row.append(order_description)

        # Количество
        qty = str(order.get("qty", 1))
        row.append(qty)

        # Цена
        price = f"{order.get('price', 0) / 100:.2f}$"
        row.append(price)

        # Время
        created_at = order.get("created_at", "")
        formatted_date = self.calculate_time_passed(created_at)
        row.append(formatted_date)

        # Order ID (скрытый)
        order_id = order.get("id", "")
        row.append(order_id)

        # API Key (скрытый)
        row.append(api_key)

        return row

    def load_buy_orders(self, threadpool):
        """Асинхронная загрузка buy orders для всех API-ключей."""
        self.table.setRowCount(0)  # Очистка таблицы перед добавлением новых строк

        for api_key in self.api_keys:
            worker = ApiWorker(self.fetch_buy_orders, api_key)
            worker.signals.result.connect(self.handle_buy_orders_result)
            worker.signals.error.connect(self.handle_buy_orders_error)
            threadpool.start(worker)

    def fetch_buy_orders(self, api_key):
        """Получение buy orders через API."""
        buy_orders = get_buy_orders(api_key)
        return {'api_key': api_key, 'buy_orders': buy_orders}

    @pyqtSlot(object)
    def handle_buy_orders_result(self, result):
        """Обработка результатов загрузки buy orders."""
        api_key = result.get('api_key')
        buy_orders = result.get('buy_orders')

        if buy_orders:
            for order in buy_orders:
                row = self.create_order_row(order, api_key)
                self.table.insertRow(self.table.rowCount())
                for j, cell in enumerate(row):
                    if isinstance(cell, QWidget):
                        self.table.setCellWidget(self.table.rowCount() - 1, j, cell)
                    elif isinstance(cell, QLabel):
                        # Для QLabel создаём отдельный QWidget и добавляем в ячейку
                        container = QWidget()
                        layout = QHBoxLayout(container)
                        layout.addWidget(cell)
                        layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        layout.setContentsMargins(0, 0, 0, 0)
                        self.table.setCellWidget(self.table.rowCount() - 1, j, container)
                    else:
                        item = QTableWidgetItem(cell)
                        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                        item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)  # Сделать ячейки только для чтения
                        self.table.setItem(self.table.rowCount() - 1, j, item)
                # Установка высоты строки
                self.table.setRowHeight(self.table.rowCount() - 1, 30)

    @pyqtSlot(tuple)
    def handle_buy_orders_error(self, error):
        """Обработка ошибок при загрузке buy orders."""
        e, traceback_str = error
        logging.error(f"Buy Orders Error: {str(e)}\n{traceback_str}")
        QMessageBox.critical(self, "Buy Orders Error", f"An error occurred while fetching buy orders: {str(e)}")

    def delete_selected_order(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Warning", "No rows selected.")
            return

        # Диалог подтверждения удаления
        confirm_delete = QMessageBox.question(
            self,
            'Confirm Deletion',
            'Are you sure you want to delete the selected orders?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm_delete == QMessageBox.StandardButton.No:
            return  # Отмена удаления пользователем

        # Сбор индексов строк для удаления, отсортированных в обратном порядке
        rows_to_delete = sorted([row.row() for row in selected_rows], reverse=True)

        # Списки для отслеживания удаленных и защищенных ордеров
        deleted_orders = []
        protected_orders = []

        for row_index in rows_to_delete:
            try:
                # Получение чекбокса блокировки из колонки 0
                lock_widget = self.table.cellWidget(row_index, 0)
                lock_checkbox = None
                if lock_widget:
                    layout = lock_widget.layout()
                    if layout:
                        lock_checkbox = layout.itemAt(0).widget()

                if lock_checkbox and lock_checkbox.isChecked():
                    order_name = self.get_order_name(row_index)
                    protected_orders.append(order_name)
                    logging.info(f"Order '{order_name}' is protected and cannot be deleted.")
                    continue  # Пропуск защищенного ордера

                # Получение Order ID и API Key из скрытых колонок
                order_id = self.table.item(row_index, 5).text()
                api_key = self.table.item(row_index, 6).text()

                # Пытаемся удалить ордер через API
                success = delete_order_by_id(order_id, api_key)

                if success:
                    deleted_orders.append(order_id)
                    self.table.removeRow(row_index)
                    logging.info(f"Order '{order_id}' deleted successfully.")
                else:
                    logging.error(f"Failed to delete order '{order_id}'.")
            except Exception as e:
                logging.error(f"Error deleting order at row {row_index}: {str(e)}")

        # Подготовка сообщений для пользователя
        if deleted_orders:
            QMessageBox.information(
                self,
                'Deletion Result',
                f"Deleted Orders: {', '.join(deleted_orders)}."
            )

        if protected_orders:
            QMessageBox.warning(
                self,
                'Protected Orders',
                f"The following orders are protected and could not be deleted:\n{', '.join(protected_orders)}."
            )

        if not deleted_orders and not protected_orders:
            QMessageBox.information(self, 'Deletion Result', 'No orders were deleted.')

    def delete_all_orders(self):
        row_count = self.table.rowCount()

        # Проверка наличия ордеров
        if row_count == 0:
            QMessageBox.warning(self, "Error", "No orders to delete.")
            return

        # Диалог подтверждения удаления всех ордеров
        confirm_delete = QMessageBox.question(
            self,
            'Confirm Deletion',
            'Are you sure you want to delete all orders?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm_delete == QMessageBox.StandardButton.No:
            return  # Отмена удаления пользователем

        # Списки для отслеживания удаленных и пропущенных ордеров
        deleted_orders = []
        skipped_orders = []

        # Проход по всем строкам таблицы с конца к началу
        for row in range(row_count - 1, -1, -1):
            try:
                # Получение чекбокса блокировки из колонки 0
                lock_widget = self.table.cellWidget(row, 0)
                lock_checkbox = None
                if lock_widget:
                    layout = lock_widget.layout()
                    if layout:
                        lock_checkbox = layout.itemAt(0).widget()

                if lock_checkbox and lock_checkbox.isChecked():
                    order_name = self.get_order_name(row)
                    skipped_orders.append(order_name)
                    logging.info(f"Order '{order_name}' is locked, skipping deletion.")
                    continue

                # Получение Order ID и API Key из скрытых колонок
                order_id = self.table.item(row, 5).text()
                api_key = self.table.item(row, 6).text()

                # Пытаемся удалить ордер через API
                success = delete_order_by_id(order_id, api_key)

                if success:
                    deleted_orders.append(order_id)
                    self.table.removeRow(row)
                    logging.info(f"Order '{order_id}' deleted successfully.")
                else:
                    logging.error(f"Failed to delete order '{order_id}'.")
            except Exception as e:
                logging.error(f"Error deleting order at row {row}: {str(e)}")

        # Подготовка сообщения для пользователя
        message = ""
        if deleted_orders:
            message += f"Deleted Orders: {', '.join(deleted_orders)}.\n"
        if skipped_orders:
            message += f"Skipped Locked Orders: {', '.join(skipped_orders)}."

        if message:
            QMessageBox.information(self, 'Deletion Result', message)
        else:
            QMessageBox.information(self, 'Deletion Result', 'No orders were deleted.')

    def parse_expression(self, expression):
        float_value_conditions = []
        conditions = []
        sticker_conditions = []
        has_error = False

        # Парсинг условий для FloatValue
        float_value_match = re.findall(r"FloatValue\s*(<=?|>=?)\s*([\d.]+)", expression)
        min_value = None
        max_value = None
        for operator, value in float_value_match:
            value = float(value)
            if operator in ('<', '<='):
                max_value = value if max_value is None else min(max_value, value)
            elif operator in ('>', '>='):
                min_value = value if min_value is None else max(min_value, value)
        if min_value is not None or max_value is not None:
            float_value_conditions = [f"Float {min_value or 0} - {max_value or 1}"]
        else:
            float_value_conditions = []

        # Парсинг условий для Item
        item_matches = re.findall(r'Item\s*==\s*"([^"]+)"', expression)
        if item_matches:
            conditions.extend(item_matches)

        # Парсинг пар DefIndex и PaintIndex
        condition_matches = re.findall(r"\(DefIndex\s*==\s*(\d+)\s+and\s+PaintIndex\s*==\s*(\d+)\)", expression)
        for def_index, paint_index in condition_matches:
            conditions.append((int(def_index), int(paint_index)))

        # Парсинг условий для стикеров
        sticker_match = re.findall(r"HasSticker\((\d+),\s*(-?\d+),\s*(\d+)\)", expression)
        if sticker_match:
            for sticker_id, slot, qty in sticker_match:
                sticker_name, _ = self.find_sticker_info(sticker_id)
                if sticker_name:
                    sticker_str = sticker_name
                    if slot != '-1':
                        sticker_str += f" Slot: {slot}"
                    if int(qty) > 1:
                        sticker_str += f" x {qty}"
                    sticker_conditions.append(sticker_str)

        # Парсинг условий для PaintSeed
        seed_match = re.search(r"PaintSeed\s*==\s*(\d+)", expression)
        seed_value = seed_match.group(1) if seed_match else None

        # Парсинг условий для StatTrak
        stattrak_match = re.search(r"StatTrak\s*==\s*true", expression)
        stattrak_value = True if stattrak_match else False

        # Парсинг условий для Souvenir
        souvenir_match = re.search(r"Souvenir\s*==\s*true", expression)
        souvenir_value = True if souvenir_match else False

        # Парсинг условий для Rarity
        rarity_match = re.search(r"Rarity\s*==\s*(\d+)", expression)
        rarity_value = int(rarity_match.group(1)) if rarity_match else None

        # Проверка на противоречия
        if stattrak_value and souvenir_value:
            has_error = True
        if rarity_value in [0, 1] and stattrak_value:
            has_error = True

        return (float_value_conditions, conditions, sticker_conditions,
                seed_value, stattrak_value, souvenir_value, rarity_value, has_error)

    def generate_error_indicator(self, text):
        """Генерация индикатора ошибки для некорректных ордеров."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        error_label = QLabel("⚠️")
        error_label.setStyleSheet("color: red;")
        error_label.setToolTip("Order has conflicting attributes.")

        description_label = QLabel(text)
        description_label.setStyleSheet("color: red;")
        description_label.setFont(self.font())

        layout.addWidget(error_label)
        layout.addWidget(description_label)

        return widget

    def generate_item_name(self, expression):
        """Генерация имени предмета на основе выражения"""
        if not expression:
            return None

        (float_value_conditions, conditions, sticker_conditions,
         seed_value, stattrak_value, souvenir_value,
         rarity_value, has_error) = self.parse_expression(expression)

        parts = []

        if float_value_conditions:
            parts.append(f"[{' '.join(float_value_conditions)}]")

        header = ' + '.join(parts)

        if conditions:
            condition_parts = []
            for condition in conditions:
                if isinstance(condition, tuple):
                    def_index, paint_index = condition
                    skin_name = self.find_skin_name(def_index, paint_index)
                elif isinstance(condition, str):
                    skin_name = condition
                else:
                    skin_name = None
                if skin_name:
                    condition_parts.append(skin_name)
            combined_conditions = " / ".join(condition_parts)

            prefix = ""
            if stattrak_value:
                prefix += "[StatTrak]"

            item_part = f"{prefix}[{combined_conditions}]"
        else:
            item_part = ""

        if sticker_conditions:
            sticker_str = " + ".join(sticker_conditions)
            sticker_part = f"[{sticker_str}]"
        else:
            sticker_part = ""

        final_description = ' + '.join(filter(None, [header, item_part, sticker_part]))

        if has_error:
            return self.generate_error_indicator(final_description)

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        app_font = self.font()

        description_label = QLabel(final_description)
        description_label.setFont(app_font)
        layout.addWidget(description_label)

        return widget

    def find_skin_name(self, def_index=None, paint_index=None):
        """Поиск имени скина по DefIndex и PaintIndex."""
        try:
            if def_index is not None and paint_index is not None:
                match = self.skins_df[(self.skins_df['DefIndex'] == def_index) &
                                      (self.skins_df['PaintIndex'] == paint_index)]
            elif def_index is not None:
                match = self.skins_df[self.skins_df['DefIndex'] == def_index]
            else:
                match = pd.DataFrame()
            if not match.empty:
                return match.iloc[0]['Name']
        except Exception as e:
            logging.error(f"Error finding skin name with DefIndex={def_index} PaintIndex={paint_index}: {str(e)}")
        return None

    def find_sticker_info(self, sticker_id):
        """Поиск информации о стикере по его ID."""
        try:
            result = self.stickers_df[self.stickers_df['id'] == int(sticker_id)]
            if not result.empty:
                return result.iloc[0]['name'], result.iloc[0]['image']
        except Exception as e:
            logging.error(f"Error finding sticker info for ID={sticker_id}: {str(e)}")
        return None, None

    def get_order_name(self, row_index):
        """Получение имени ордера из колонки 'Order'."""
        order_widget = self.table.cellWidget(row_index, 1)
        if order_widget:
            # Предполагается, что виджет содержит QLabel с описанием
            layout = order_widget.layout()
            if layout:
                label = layout.itemAt(0).widget()
                if isinstance(label, QLabel):
                    return label.text()
        # Если виджет не используется, получить текст из QTableWidgetItem
        order_item = self.table.item(row_index, 1)
        return order_item.text() if order_item else "Unknown Order"

    def calculate_time_passed(self, iso_date):
        """Вычисление времени, прошедшего с момента создания ордера."""
        try:
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = now - dt
            return f"{delta.days}d {delta.seconds // 3600}h"
        except Exception as e:
            logging.error(f"Error calculating time passed for date '{iso_date}': {str(e)}")
            return "Unknown Time"

    def load_column_widths(self):
        """Load the saved column widths."""
        for i in range(1, self.table.columnCount()):  # Start from 1 to skip the locked column
            width = self.settings.value(f"tab2_column_width_{i}", type=int)
            if width:
                self.table.setColumnWidth(i, width)

    def save_column_widths(self):
        for i in range(self.table.columnCount()):
            self.settings.setValue(f"tab2_column_width_{i}", self.table.columnWidth(i))

    def closeEvent(self, event):
        self.save_column_widths()
        event.accept()
