# modules/ui_tab1.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox, QFormLayout, QDialog, QSpacerItem, QSizePolicy, QCompleter, QListWidget, QListView
from PyQt6.QtGui import QPixmap, QIcon, QColor, QBrush, QFont, QPainter
from PyQt6.QtCore import Qt, QSettings, QPersistentModelIndex, QSize, pyqtSignal, pyqtSlot
from datetime import datetime, timezone
from collections import defaultdict

from modules.api import get_user_info, get_inventory_data, get_stall_data, sell_item, delete_item, change_price
from modules.utils import load_config, cache_image, calculate_days_on_sale
from modules.workers import ApiWorker
import os
import logging
import time
import re

RARITY_COLOR_MAP = {
    1: QColor(176, 195, 217),  # Consumer Grade (Светло-серый)
    2: QColor(94, 152, 217),   # Industrial Grade (Голубой)
    3: QColor(75, 105, 255),   # Mil-Spec Grade (Синий)
    4: QColor(136, 71, 255),   # Restricted (Фиолетовый)
    5: QColor(211, 44, 230),   # Classified (Розовый)
    6: QColor(235, 75, 75),    # Covert (Красный)
    7: QColor(228, 174, 57),   # Contraband (Золотой)
    8: QColor("orange")         # Дополнительный уровень
}



class Tab1(QWidget):
    api_key_changed = pyqtSignal(str)
    max_price = 10000000
    min_price = 3

    DEFAULT_COLUMN_WIDTHS = [
        275,  # 0: Name
        140,  # 1: Stickers
        125,  # 2: Float Value
        60,  # 3: On sale
        80,  # 4: Price
        100,  # 5: Listing ID (скрытая)
        100,  # 6: Asset ID (скрытая)
        100,  # 7: Created At (скрытая)
        100,  # 8: Price Value (скрытая)
        100,  # 9: API Key (скрытая)
        100,  # 10: Collection (скрытая)
        100,  # 11: Rarity (скрытая)
        100  # 12: Wear Condition (скрытая)
    ]

    def __init__(self, api_keys, icon_path, tab2, parent=None):
        super().__init__(parent)
        self.api_keys = api_keys
        self.icon_path = icon_path
        self.tab2 = tab2
        self.settings = QSettings("MyCompany", "SteamInventoryApp")
        self.default_api_key = self.settings.value("default_api_key", api_keys[0])
        self.user_infos = []
        self.inventory = []
        self.stall = []
        self.selected_conditions = set()
        self.selected_rarities = set()  # Хранит выбранные редкости

        # Определение основного шрифта
        self.app_font = QFont('Oswald')
        self.app_font.setPointSize(11)
        self.setFont(self.app_font)  # Устанавливаем шрифт на родительском виджете

        self.initUI()
        # цветные иконки
        self.inventory_table.verticalHeader().setDefaultSectionSize(30)
        self.inventory_table.setIconSize(QSize(10, 30))

        self.price_sort_order = Qt.SortOrder.AscendingOrder
        self.days_sort_order = Qt.SortOrder.AscendingOrder
        self.name_sort_order = Qt.SortOrder.AscendingOrder
        self.float_sort_order = Qt.SortOrder.AscendingOrder
        self.last_sorted_column = None
        self.last_sort_order = None


    def initUI(self):
        central_widget = QWidget(self)
        main_layout = QVBoxLayout(central_widget)
        self.setLayout(main_layout)

        # Создание кнопок фильтрации по редкости
        self.rarity_buttons = []
        x_start = 200  # Начальная координата X
        y_start = 88  # Координата Y для кнопок редкости
        spacing = 3  # Расстояние между кнопками

        for rarity, color in RARITY_COLOR_MAP.items():
            button = QPushButton(self)
            button.setCheckable(True)
            button.setFixedSize(20, 20)  # Размер 24x24
            button.setStyleSheet(f"""
                QPushButton {{
                    border: 3px solid {color.name()};  /* Яркий контур */
                    border-radius: 10px;               /* Половина размера для круга */
                    background-color: {color.lighter(150).name()};  /* Светлый центр */
                    padding-left: 3px;  /* Сдвиг содержимого на 3 пикселя влево */
                }}
                QPushButton::checked {{
                    background-color: {color.darker(135).name()};  /* Сделаем фон еще темнее для заметности */
                    padding-left: 0px;  /* Убираем дополнительный отступ при выборе */
                }}
            """)

            button.rarity = rarity
            button.toggled.connect(self.update_rarity_filters)
            button.move(x_start, y_start)
            self.rarity_buttons.append(button)
            x_start += button.width() + spacing

        # Фильтр по имени
        self.name_filter = QLineEdit(self)
        self.name_filter.setPlaceholderText("Filter by Name")
        self.name_filter.move(20, 20)
        self.name_filter.setFixedSize(150, 24)
        self.name_filter.textChanged.connect(self.apply_filters)
        self.name_filter.setStyleSheet("""
            QLineEdit {
                border: 1px solid #D1B3FF;
                border-radius: 5px;
                padding: 2px 10px 2px 5px;
            }
            QLineEdit:focus {
                border: 1px solid #4147D5;
            }
        """)

        # Добавляем поле ввода с возможностью выбора и автозаполнения
        self.create_completer_input()

        # Фильтр по стикерам
        self.sticker_filter = QLineEdit(self)
        self.sticker_filter.setPlaceholderText("Filter by Sticker")
        self.sticker_filter.move(20, 54)
        self.sticker_filter.setFixedSize(150, 24)
        self.sticker_filter.textChanged.connect(self.apply_filters)
        self.sticker_filter.setStyleSheet("""
            QLineEdit {
                border: 1px solid #D1B3FF;
                border-radius: 5px;
                padding: 2px 10px 2px 5px;
            }
            QLineEdit:focus {
                border: 1px solid #4147D5;
            }
        """)

        # Фильтры по Float
        self.float_min_filter = QLineEdit(self)
        self.float_min_filter.setPlaceholderText("Min Float")
        self.float_min_filter.move(200, 20)
        self.float_min_filter.setFixedSize(75, 24)
        self.float_min_filter.textChanged.connect(self.apply_filters)
        self.float_min_filter.setStyleSheet("""
            QLineEdit {
                border: 1px solid #D1B3FF;
                border-radius: 5px;
                padding: 2px 10px 2px 5px;
            }
            QLineEdit:focus {
                border: 1px solid #4147D5;
            }
        """)

        self.float_max_filter = QLineEdit(self)
        self.float_max_filter.setPlaceholderText("Max Float")
        self.float_max_filter.move(305, 20)
        self.float_max_filter.setFixedSize(75, 24)
        self.float_max_filter.textChanged.connect(self.apply_filters)
        self.float_max_filter.setStyleSheet("""
            QLineEdit {
                border: 1px solid #D1B3FF;
                border-radius: 5px;
                padding: 2px 10px 2px 5px;
            }
            QLineEdit:focus {
                border: 1px solid #4147D5;
            }
        """)

        # Поле ввода для цены
        self.price_input = QLineEdit(self)
        self.price_input.setPlaceholderText("Price")
        self.price_input.move(410, 20)
        self.price_input.setFixedSize(75, 24)
        self.price_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #D1B3FF;
                border-radius: 5px;
                padding: 2px 10px 2px 5px;
            }
            QLineEdit:focus {
                border: 1px solid #4147D5;
            }
        """)

        # Кнопки "Sell", "Change Price", "Delist", "User Info", "Avatar Info"
        self.sell_button = QPushButton(self)
        self.sell_button.setIcon(QIcon(os.path.join(self.icon_path, 'sell.png')))
        self.sell_button.setIconSize(QSize(50, 50))
        self.sell_button.setFixedSize(50, 50)
        self.sell_button.move(515, 20)
        self.sell_button.setStyleSheet("border: none;")
        self.sell_button.clicked.connect(self.sell_items)
        self.sell_button.setToolTip("Sell selected items")

        self.change_price_button = QPushButton(self)
        self.change_price_button.setIcon(QIcon(os.path.join(self.icon_path, 'change.png')))
        self.change_price_button.setIconSize(QSize(50, 50))
        self.change_price_button.setFixedSize(50, 50)
        self.change_price_button.move(575, 20)
        self.change_price_button.setStyleSheet("border: none;")
        self.change_price_button.clicked.connect(self.change_item_price)
        self.change_price_button.setToolTip("Change price of selected item")

        self.delist_button = QPushButton(self)
        self.delist_button.setIcon(QIcon(os.path.join(self.icon_path, 'delist.png')))
        self.delist_button.setIconSize(QSize(50, 50))
        self.delist_button.setFixedSize(50, 50)
        self.delist_button.move(635, 20)
        self.delist_button.setStyleSheet("border: none;")
        self.delist_button.clicked.connect(self.delist_items)
        self.delist_button.setToolTip("Delist selected items")

        self.user_info_button = QPushButton(self)
        self.user_info_button.setIcon(QIcon(os.path.join(self.icon_path, 'info.png')))
        self.user_info_button.setIconSize(QSize(50, 50))
        self.user_info_button.setFixedSize(50, 50)
        self.user_info_button.move(695, 20)
        self.user_info_button.setStyleSheet("border: none;")
        self.user_info_button.clicked.connect(self.show_user_info)
        self.user_info_button.setToolTip("Show user info")

        self.update_avatar()

        # Настройка таблицы инвентаря
        self.inventory_table = QTableWidget(self)
        self.inventory_table.setColumnCount(13)  # Увеличено с 12 до 13
        self.inventory_table.setHorizontalHeaderLabels([
            "Name", "Stickers", "Float Value", "On sale", "Price", "Listing ID", "Asset ID", "Created At",
            "Price Value", "API Key", "Collection", "Rarity", "Wear Condition"  # Добавлена колонка Wear Condition
        ])

        # Применение шрифта для заголовков таблицы
        header_font = QFont('Oswald')
        header_font.setPointSize(11)
        self.inventory_table.horizontalHeader().setFont(header_font)
        self.inventory_table.horizontalHeader().setStyleSheet(
            "QHeaderView::section { font-family: Oswald; font-size: 11pt; }")

        self.inventory_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.inventory_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.inventory_table.setSortingEnabled(True)
        self.inventory_table.horizontalHeader().setSectionsClickable(True)
        self.inventory_table.horizontalHeader().setSortIndicatorShown(True)

        self.inventory_table.horizontalHeader().setStyleSheet("color: #4147D5")

        # Установка режима изменения размера колонок
        for i in range(13):  # Updated to 13 columns
            if i < 5:
                self.inventory_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            else:
                self.inventory_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)

        # Скрытие некоторых колонок
        self.inventory_table.setColumnHidden(7, True)
        self.inventory_table.setColumnHidden(8, True)
        self.inventory_table.setColumnHidden(5, True)  # Listing ID
        self.inventory_table.setColumnHidden(6, True)  # Asset ID
        self.inventory_table.setColumnHidden(9, True)  # API Key
        self.inventory_table.setColumnHidden(10, True)  # Collection
        self.inventory_table.setColumnHidden(11, True)  # Rarity
        self.inventory_table.setColumnHidden(12, True)  # Wear Condition

        self.inventory_table.horizontalHeader().sectionClicked.connect(self.handle_header_click)

        # Установка размера и позиции таблицы
        self.inventory_table.setFixedSize(730, 600)
        self.inventory_table.move(20, 132)  # Располагаем таблицу ниже кнопок редкости

        # Настройка политики размера таблицы
        self.inventory_table.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # **Добавление стиля для удаления левого отступа**
        self.inventory_table.setStyleSheet("""
                QTableWidget::item {
                    padding-left: 0px;
                }
            """)

        self.load_column_widths()

        # **Call the method to create condition buttons**
        self.create_condition_buttons()

    def create_completer_input(self):
        layout = QHBoxLayout()

        # Поле ввода
        self.test_line_edit = QLineEdit(self)
        self.test_line_edit.setPlaceholderText("Filter by Collections")
        self.test_line_edit.setFixedSize(150, 24)  # Уменьшаем ширину поля для ввода
        app_font = QFont('Oswald')
        app_font.setPointSize(11)  # Перенесено для правильного размера шрифта
        self.test_line_edit.setFont(app_font)

        self.test_line_edit.setStyleSheet("""
            QLineEdit {
                border: 1px solid #D1B3FF;
                border-radius: 5px;
                padding-left: 5px;  /* Отступ слева на 5 пикселей */
                font-size: 11pt;  /* Размер шрифта для введенного текста */
            }
            QLineEdit::placeholder {
                color: #A0A0A0;  /* Цвет текста заполнителя */
                font-size: 10pt;  /* Размер шрифта для текста заполнителя */
                font-family: 'Oswald';  /* Пример шрифта */
            }
            QLineEdit:focus {
                border: 1px solid #4147D5;
            }
        """)

        # Список коллекций для автозаполнения
        items = [
            "2018 Inferno Collection", "2018 Nuke Collection", "2021 Dust 2 Collection", "2021 Mirage Collection",
            "2021 Train Collection", "2021 Vertigo Collection", "Alpha Collection", "Ancient Collection",
            "Anubis Collection", "Arms Deal 2 Collection", "Arms Deal 3 Collection", "Arms Deal Collection",
            "Assault Collection", "Aztec Collection", "Baggage Collection", "Bank Collection", "Blacksite Collection",
            "Bravo Collection", "Breakout Collection", "CS20 Collection", "Cache Collection", "Canals Collection",
            "Chop Shop Collection", "Chroma 2 Collection", "Chroma 3 Collection", "Chroma Collection",
            "Clutch Collection",
            "Cobblestone Collection", "Control Collection", "Danger Zone Collection", "Dreams & Nightmares Collection",
            "Dust 2 Collection", "Dust Collection", "Falchion Collection", "Fracture Collection", "Gamma 2 Collection",
            "Gamma Collection", "Glove Collection", "Gods and Monsters Collection", "Havoc Collection",
            "Horizon Collection", "Huntsman Collection", "Inferno Collection", "Italy Collection",
            "Kilowatt Collection",
            "Lake Collection", "Militia Collection", "Mirage Collection", "Norse Collection", "Nuke Collection",
            "Office Collection", "Operation Broken Fang Collection", "Operation Hydra Collection",
            "Operation Riptide Collection",
            "Overpass Collection", "Phoenix Collection", "Prisma 2 Collection", "Prisma Collection",
            "Recoil Collection",
            "Revolution Collection", "Revolver Case Collection", "Rising Sun Collection", "Safehouse Collection",
            "Shadow Collection", "Shattered Web Collection", "Snakebite Collection", "Spectrum 2 Collection",
            "Spectrum Collection", "St. Marc Collection", "Train Collection", "Vanguard Collection",
            "Vertigo Collection",
            "Wildfire Collection", "Winter Offensive Collection", "X-Ray Collection", "eSports 2013 Collection",
            "eSports 2013 Winter Collection", "eSports 2014 Summer Collection"
        ]

        # Создаем QCompleter для автозаполнения
        completer = QCompleter(items, self)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)

        # Устанавливаем игнорирование регистра символов
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        # Создаем QListView и устанавливаем шрифт для выпадающего списка
        completer_popup = QListView()
        completer_popup.setFont(app_font)
        completer.setPopup(completer_popup)

        self.test_line_edit.setCompleter(completer)

        # Подключаем сигнал завершения выбора
        completer.activated.connect(self.on_item_selected)

        # Подключаем сигнал textChanged для обновления фильтров при изменении текста
        self.test_line_edit.textChanged.connect(self.apply_filters)

        # Кнопка для открытия выпадающего списка
        self.dropdown_button = QPushButton("▼", self)
        self.dropdown_button.setFixedSize(24, 24)  # Стандартный размер кнопки
        self.dropdown_button.setFont(app_font)

        self.dropdown_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;  /* Прозрачный фон */
                color: #4147D5;  /* Цвет текста */
                border: none;  /* Убираем границы */
            }
        """)

        # Подключаем кнопку с отладочным сообщением
        self.dropdown_button.clicked.connect(self.test_line_edit.completer().complete)

        # Добавляем в горизонтальный лейаут поле ввода и кнопку
        layout.addWidget(self.test_line_edit)
        layout.addWidget(self.dropdown_button)

        layout.setContentsMargins(0, 0, 0, 0)  # Убираем отступы
        layout.setSpacing(0)  # Убираем расстояние между элементами

        # Устанавливаем лейаут в нужное место
        container = QWidget(self)
        container.setLayout(layout)
        container.move(20, 88)
        container.setFixedSize(150, 24)  # Устанавливаем контейнер шириной 150 пикселей

    def create_condition_buttons(self):
        """Создаёт пять кнопок для фильтрации по состоянию предметов с обновленным стилем и отступами."""
        self.condition_buttons = []
        button_labels = ["FN", "MW", "FT", "WW", "BS"]
        wear_conditions = {
            "FN": "Factory New",
            "MW": "Minimal Wear",
            "FT": "Field-Tested",
            "WW": "Well-Worn",
            "BS": "Battle-Scarred"
        }

        button_start_x = 200
        button_start_y = 54
        button_width = 36  # Ширина кнопки в пикселях
        button_height = 24  # Высота кнопки в пикселях

        for i, label in enumerate(button_labels):
            button = QPushButton(label, self)
            button.setCheckable(True)
            button.setFixedSize(button_width, button_height)
            button.setFont(self.app_font)  # Используем наследуемый шрифт

            # Настройка стиля с учётом скругления углов и соответствующих цветов
            if i == 0:
                # Первая кнопка с скруглением левых углов
                style = f"""
                    QPushButton {{
                        border: 1px solid #D1B3FF;  /* Цвет границы, совпадает с полями ввода */
                        border-top-left-radius: 5px;
                        border-bottom-left-radius: 5px;
                        background-color: #FFFFFF;   /* Белый фон */
                        color: #4147D5;              /* Цвет текста */
                    }}
                    QPushButton::checked {{
                        background-color: #4147D5;   /* Синий фон при нажатии */
                        color: #FFFFFF;              /* Белый текст при нажатии */
                    }}
                    QPushButton:hover {{
                        background-color: #E0E0E0;   /* Светло-серый фон при наведении */
                    }}
                """
            elif i == len(button_labels) - 1:
                # Последняя кнопка с скруглением правых углов
                style = f"""
                    QPushButton {{
                        border: 1px solid #D1B3FF;
                        border-top-right-radius: 5px;
                        border-bottom-right-radius: 5px;
                        background-color: #FFFFFF;
                        color: #4147D5;
                    }}
                    QPushButton::checked {{
                        background-color: #4147D5;
                        color: #FFFFFF;
                    }}
                    QPushButton:hover {{
                        background-color: #E0E0E0;
                    }}
                """
            else:
                # Средние кнопки без скругления углов
                style = f"""
                    QPushButton {{
                        border: 1px solid #D1B3FF;
                        background-color: #FFFFFF;
                        color: #4147D5;
                    }}
                    QPushButton::checked {{
                        background-color: #4147D5;
                        color: #FFFFFF;
                    }}
                    QPushButton:hover {{
                        background-color: #E0E0E0;
                    }}
                """

            button.setStyleSheet(style)
            button.move(button_start_x, button_start_y)
            button.wear_condition = wear_conditions[label]
            button.toggled.connect(self.update_condition_filters)
            self.condition_buttons.append(button)
            button_start_x += button_width

    def on_item_selected(self, text):
        """Обрабатывает выбор элемента из автозаполнения."""
        self.test_line_edit.setText(text)
        self.apply_filters()  # Применяем фильтр после выбора элемента

    def filter_dropdown(self, text):
        """Фильтрует элементы в списке на основе ввода пользователя."""
        for i in range(self.dropdown_list.count()):
            item = self.dropdown_list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def toggle_dropdown(self, text):
        """Отображает или скрывает выпадающий список."""
        if text:
            # Перемещаем выпадающий список над таблицей
            self.dropdown_list.move(self.test_line_edit.x(), self.test_line_edit.y() + self.test_line_edit.height())
            self.dropdown_list.raise_()  # Поднимаем выпадающий список поверх других элементов
            self.dropdown_list.show()
        else:
            self.dropdown_list.hide()

    def on_item_clicked(self, item):
        """Заполняет поле ввода выбранным элементом из выпадающего списка."""
        self.test_line_edit.setText(item.text())
        self.dropdown_list.hide()

    def load_data(self, threadpool):
        """Асинхронная загрузка данных для всех API-ключей."""
        self.user_infos = []
        self.inventory = []
        self.stall = []

        for api_key in self.api_keys:
            worker = ApiWorker(self.fetch_user_and_inventory, api_key)
            worker.signals.result.connect(self.handle_api_result)
            worker.signals.error.connect(self.handle_api_error)
            threadpool.start(worker)

    def fetch_user_and_inventory(self, api_key):
        """Получение информации о пользователе и инвентаре."""
        user_info = get_user_info(api_key)
        inventory = get_inventory_data(api_key)
        return {'api_key': api_key, 'user_info': user_info, 'inventory': inventory}

    @pyqtSlot(object)
    def handle_api_result(self, result):
        """Обработка результатов API-запросов."""
        api_key = result.get('api_key')
        user_info = result.get('user_info')
        inventory = result.get('inventory')

        if user_info:
            user_info['api_key'] = api_key
            self.user_infos.append(user_info)

            if inventory:
                for item in inventory:
                    item['api_key'] = api_key
                    self.inventory.append(item)

        if len(self.user_infos) == len(self.api_keys):
            self.load_stall_data()
            self.populate_inventory_table()

    @pyqtSlot(tuple)
    def handle_api_error(self, error):
        """Обработка ошибок API-запросов."""
        e, traceback_str = error
        logging.error(f"API Error: {str(e)}\n{traceback_str}")
        QMessageBox.critical(self, "API Error", f"An error occurred while fetching data: {str(e)}")

    def create_color_icon(self, color: QColor, width: int = 5, height: int = 30) -> QIcon:
        """
        Создает иконку с цветным прямоугольником.

        :param color: Цвет прямоугольника.
        :param width: Ширина прямоугольника в пикселях.
        :param height: Высота прямоугольника в пикселях.
        :return: QIcon с цветным прямоугольником.
        """
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.GlobalColor.transparent)  # Создаем прозрачный фон
        painter = QPainter(pixmap)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(0, 0, width, height)  # Рисуем прямоугольник
        painter.end()
        return QIcon(pixmap)

    def create_rarity_filters(self):
        """
        Создаёт 8 круглых кнопок для фильтрации по редкости.
        """
        rarity_layout = QHBoxLayout()
        rarity_layout.setSpacing(10)  # Расстояние между кнопками
        rarity_layout.setContentsMargins(0, 0, 0, 0)

        self.selected_rarities = set()  # Набор выбранных редкостей

        for rarity, color in RARITY_COLOR_MAP.items():
            button = QPushButton(self)
            button.setCheckable(True)
            button.setFixedSize(30, 30)  # Размер кнопки
            button.setStyleSheet(f"""
                QPushButton {{
                    border: 2px solid {color.name()};  /* Яркий контур */
                    border-radius: 15px;              /* Закруглённые углы для круга */
                    background-color: {color.lighter(150).name()};  /* Светлый центр */
                }}
                QPushButton::checked {{
                    background-color: {color.name()};  /* Заполненный цвет при выборе */
                }}
            """)
            button.setToolTip(f"Rarity {rarity}")  # Подсказка при наведении

            # Сохраняем редкость в свойства кнопки
            button.rarity = rarity

            # Подключаем сигнал
            button.toggled.connect(self.update_rarity_filters)

            rarity_layout.addWidget(button)

        # Создаём контейнер для кнопок и добавляем его в основной layout
        container = QWidget(self)
        container.setLayout(rarity_layout)
        container.setFixedHeight(40)  # Высота контейнера

        # Добавляем контейнер в основной вертикальный layout
        self.layout().addWidget(container, alignment=Qt.AlignmentFlag.AlignLeft)

    @pyqtSlot(bool)
    def update_rarity_filters(self, checked):
        """
        Обновляет фильтры по редкости на основе выбранных кнопок.
        """
        button = self.sender()
        if button:
            if checked:
                self.selected_rarities.add(button.rarity)
            else:
                self.selected_rarities.discard(button.rarity)
            self.apply_filters()

    @pyqtSlot(bool)
    def update_condition_filters(self, checked):
        """Обновляет фильтры по состоянию на основе выбранных кнопок."""
        button = self.sender()
        if button:
            if checked:
                self.selected_conditions.add(button.wear_condition)
            else:
                self.selected_conditions.discard(button.wear_condition)
            self.apply_filters()

    def clear_data(self):
        self.inventory = []  # Очищаем список инвентаря
        self.stall = []  # Очищаем список предметов на продаже
        self.inventory_table.clearContents()  # Очищаем таблицу инвентаря

    def load_stall_data(self):
        """Load stall data for all API keys."""
        self.stall = []  # Clear the previous stall data

        # Fetch stall data for each API key
        for api_key in self.api_keys:
            user_info = next((info for info in self.user_infos if info['api_key'] == api_key), None)
            if user_info:
                steam_id = user_info.get("steam_id")
                if steam_id:
                    stall_data = get_stall_data(api_key, steam_id)  # Fetch stall data from the API
                    if stall_data:
                        self.stall.extend(stall_data)  # Add stall data to the combined list

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

    def apply_last_sort(self):
        if self.last_sorted_column is not None and self.last_sort_order is not None:
            self.inventory_table.sortItems(self.last_sorted_column, self.last_sort_order)

    def populate_inventory_table(self):
        """Populate the inventory table with combined data from all API keys."""
        self.inventory_table.setRowCount(0)  # Очищаем таблицу перед добавлением новых строк

        # Создаем словарь для быстрого поиска данных о продаже
        stall_dict = {item['item']['asset_id']: item for item in self.stall} if self.stall else {}

        for item in self.inventory:
            row_position = self.inventory_table.rowCount()
            self.inventory_table.insertRow(row_position)

            asset_id = item.get("asset_id")
            market_hash_name = item.get("market_hash_name", "")

            # Получение значения Rarity
            rarity_value = int(item.get("rarity", 1))  # Предполагаем, что 1 - минимальное значение
            color = RARITY_COLOR_MAP.get(rarity_value, QColor("white"))  # По умолчанию белый

            # Создание иконки цвета
            color_icon = self.create_color_icon(color)  # Прямоугольная иконка

            # Создание QTableWidgetItem с иконкой и текстом
            name_item = QTableWidgetItem(market_hash_name)
            name_item.setIcon(color_icon)
            name_item.setFont(self.font())  # Используем наследуемый шрифт
            name_item.setTextAlignment(
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)  # Выравнивание текста влево

            self.inventory_table.setItem(row_position, 0, name_item)

            # Stickers (колонка 1: Stickers)
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

            # Float Value (колонка 2: Float Value)
            float_value = item.get('float_value')
            float_value_text = f"{float_value:.14f}" if float_value is not None else ""
            float_value_item = QTableWidgetItem(float_value_text)
            float_value_item.setFont(self.font())  # Применяем шрифт
            self.inventory_table.setItem(row_position, 2, float_value_item)

            # Добавление данных о продаже, если доступны
            stall_item = stall_dict.get(asset_id)
            if stall_item:
                # Days on Sale (колонка 3: Days on Sale)
                days_on_sale = calculate_days_on_sale(stall_item['created_at'])
                days_on_sale_item = QTableWidgetItem(days_on_sale)
                days_on_sale_item.setFont(self.font())  # Применяем шрифт
                self.inventory_table.setItem(row_position, 3, days_on_sale_item)

                # Price (колонка 4: Price)
                price = f"{stall_item['price'] / 100:.2f}$"
                price_widget = QWidget()
                price_layout = QHBoxLayout(price_widget)
                price_layout.setContentsMargins(0, 0, 0, 0)

                csfloat_logo = QLabel()
                csfloat_logo.setPixmap(QPixmap(os.path.join(self.icon_path, "csfloat_logo.png")).scaled(20, 20,
                                                                                                        Qt.AspectRatioMode.KeepAspectRatio))
                price_layout.addWidget(csfloat_logo)

                price_label = QLabel(f" {price}")
                price_label.setFont(self.font())  # Применяем шрифт
                price_layout.addWidget(price_label)

                price_layout.addStretch()
                self.inventory_table.setCellWidget(row_position, 4, price_widget)

                # Listing ID (колонка 5: Listing ID)
                listing_id_item = QTableWidgetItem(stall_item['id'])
                listing_id_item.setFont(self.font())  # Применяем шрифт
                self.inventory_table.setItem(row_position, 5, listing_id_item)
                self.inventory_table.setColumnHidden(5, True)  # Скрываем колонку Listing ID

                # Created At (колонка 7: Created At)
                created_at_item = QTableWidgetItem(stall_item['created_at'])
                created_at_item.setFont(self.font())  # Применяем шрифт
                self.inventory_table.setItem(row_position, 7, created_at_item)

                # Price Value (колонка 8: Price Value)
                price_value_item = QTableWidgetItem()
                price_value_item.setData(Qt.ItemDataRole.DisplayRole, stall_item['price'])
                price_value_item.setData(Qt.ItemDataRole.UserRole, stall_item['price'])
                price_value_item.setFont(self.font())  # Применяем шрифт
                self.inventory_table.setItem(row_position, 8, price_value_item)
            else:
                # Заполняем пустыми ячейками, если данных о продаже нет
                empty_item = QTableWidgetItem("")
                empty_item.setFont(self.font())  # Применяем шрифт
                self.inventory_table.setItem(row_position, 3, empty_item)
                self.inventory_table.setItem(row_position, 4, QTableWidgetItem(""))
                self.inventory_table.setItem(row_position, 5, QTableWidgetItem(""))
                self.inventory_table.setColumnHidden(5, True)  # Скрываем колонку Listing ID

            # API Key (колонка 9: API Key)
            api_key = item.get("api_key", "N/A")
            api_key_item = QTableWidgetItem(api_key)
            api_key_item.setFont(self.font())  # Применяем шрифт
            self.inventory_table.setItem(row_position, 9, api_key_item)

            # Присваиваем значение переменной collection
            collection = item.get("collection", "N/A")

            # Удаляем префикс "The ", если он присутствует
            collection = re.sub(r'^The\s+', '', collection)

            # Создаем элемент таблицы с обновленным значением collection
            collection_item = QTableWidgetItem(collection)
            collection_item.setFont(self.font())  # Применяем шрифт
            self.inventory_table.setItem(row_position, 10, collection_item)

            # Rarity (колонка 11: Rarity)
            rarity = str(item.get("rarity", "N/A"))
            rarity_item = QTableWidgetItem(rarity)
            rarity_item.setFont(self.font())  # Применяем шрифт
            self.inventory_table.setItem(row_position, 11, rarity_item)

            # Добавление Wear Condition (колонка 12: Wear Condition)
            # Опция 1: Извлечение из поля 'wear_name'
            wear_name = item.get("wear_name", "N/A")

            # Опция 2: Парсинг из названия предмета, если 'wear_name' отсутствует
            if wear_name == "N/A":
                match = re.search(r'\((.*?)\)', market_hash_name)
                wear_name = match.group(1) if match else "N/A"

            wear_condition_item = QTableWidgetItem(wear_name)
            wear_condition_item.setFont(self.font())  # Применяем шрифт
            self.inventory_table.setItem(row_position, 12, wear_condition_item)
            self.inventory_table.setColumnHidden(12, True)  # Скрываем колонку Wear Condition

            # Asset ID (колонка 6: Asset ID, скрытая)
            asset_id_item = QTableWidgetItem(asset_id)
            asset_id_item.setFont(self.font())  # Применяем шрифт
            self.inventory_table.setItem(row_position, 6, asset_id_item)
            self.inventory_table.setColumnHidden(6, True)  # Скрываем колонку Asset ID

    def load_column_widths(self):
        for i in range(self.inventory_table.columnCount()):
            # Пытаемся получить сохранённую ширину колонки
            width = self.settings.value(f"column_width_{i}", type=int)
            if width:
                self.inventory_table.setColumnWidth(i, width)
            else:
                # Если ширина не сохранена, устанавливаем дефолтную
                self.inventory_table.setColumnWidth(i, self.DEFAULT_COLUMN_WIDTHS[i])

    def save_column_widths(self):
        for i in range(self.inventory_table.columnCount()):
            self.settings.setValue(f"column_width_{i}", self.inventory_table.columnWidth(i))

    def closeEvent(self, event):
        self.save_column_widths()
        event.accept()

    @pyqtSlot()
    def apply_filters(self):
        name_filter = self.name_filter.text().lower()
        sticker_filter = self.sticker_filter.text().lower()
        selected_rarities = self.selected_rarities  # Хранит выбранные редкости
        selected_conditions = self.selected_conditions  # Хранит выбранные условия

        # Фильтр по коллекции с удалением лишних пробелов
        collection_filter = self.test_line_edit.text().strip().lower()

        try:
            min_float = float(self.float_min_filter.text()) if self.float_min_filter.text() else None
            max_float = float(self.float_max_filter.text()) if self.float_max_filter.text() else None
        except ValueError:
            min_float = None
            max_float = None

        for row in range(self.inventory_table.rowCount()):
            # Получаем значения из таблицы
            name_item = self.inventory_table.item(row, 0).text().lower()
            float_value_text = self.inventory_table.item(row, 2).text()
            float_value = float(float_value_text) if float_value_text else None

            # Получение редкости из скрытой колонки 11
            rarity_item = self.inventory_table.item(row, 11)
            rarity = int(rarity_item.text()) if rarity_item and rarity_item.text().isdigit() else None

            # Получение wear_condition из скрытой колонки 12
            wear_condition_item = self.inventory_table.item(row, 12)
            wear_condition = wear_condition_item.text() if wear_condition_item else "N/A"

            # Фильтрация по редкости
            if selected_rarities:
                matches_rarity = rarity in selected_rarities
            else:
                matches_rarity = True  # Если ничего не выбрано, не фильтруем по редкости

            # Фильтрация по состоянию
            if selected_conditions:
                matches_condition = wear_condition in selected_conditions
            else:
                matches_condition = True  # Если ничего не выбрано, не фильтруем по состоянию

            # Фильтрация по стикерам
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
                    (min_float is None or (float_value is not None and float_value >= min_float)) and
                    (max_float is None or (float_value is not None and float_value <= max_float))
            )

            # Фильтрация по коллекции
            if collection_filter:
                collection_item = self.inventory_table.item(row, 10).text().lower()
                matches_collection = (collection_item == collection_filter)
            else:
                matches_collection = True  # Если фильтр коллекции не задан, не фильтруем по ней

            # Установка видимости строки на основе всех фильтров
            self.inventory_table.setRowHidden(row, not (
                    matches_name and
                    matches_sticker and
                    matches_float and
                    matches_rarity and
                    matches_collection and
                    matches_condition
            ))

            # Отладочное сообщение
            # print(f"Row {row}: collection_filter='{collection_filter}', collection_item='{collection_item}', matches_collection={matches_collection}")

        # Переустанавливаем сортировку после фильтрации
        if self.last_sorted_column is not None and self.last_sort_order is not None:
            self.inventory_table.sortItems(self.last_sorted_column, self.last_sort_order)

    def show_confirmation_dialog(self, message):
        reply = QMessageBox.question(self, "Confirmation", message,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return reply == QMessageBox.StandardButton.Yes

    def sell_items(self):
        # Check if the price input contains a '%' sign
        price_input = self.price_input.text().strip()
        if "%" in price_input:
            QMessageBox.warning(self, "Warning", "Please remove the '%' sign from the price field before selling.")
            return

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
                asset_id_item = self.inventory_table.item(row, 6)  # Asset ID in column 6
                if asset_id_item and asset_id_item.text():
                    selected_asset_ids.add(asset_id_item.text())

        items_to_sell = []
        for row in range(self.inventory_table.rowCount()):
            asset_id_item = self.inventory_table.item(row, 6)  # Asset ID in column 6
            if asset_id_item and asset_id_item.text() in selected_asset_ids:
                item_name = self.inventory_table.item(row, 0).text()

                # Check if the item is already listed
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

                api_key_item = self.inventory_table.item(row, 9)  # Fetch the API key from column 9
                if api_key_item:
                    api_key = api_key_item.text()
                    items_to_sell.append((row, asset_id_item.text(), item_name, price, api_key))

        if items_to_sell:
            grouped_operations = defaultdict(int)
            for _, _, item_name, price, _ in items_to_sell:
                grouped_operations[(item_name, price)] += 1

            confirm_message = "You are about to sell the following items:\n"
            for (item_name, price), count in grouped_operations.items():
                if count > 1:
                    confirm_message += f"{count}x {item_name} for {price / 100:.2f}$\n"
                else:
                    confirm_message += f"{item_name} for {price / 100:.2f}$\n"

            if not self.show_confirmation_dialog(confirm_message.strip()):
                return

        for row, asset_id, item_name, price, api_key in items_to_sell:
            try:
                response = sell_item(api_key, asset_id, price)  # Pass the correct API key
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

                # Get current price
                current_price = float(current_price_widget.layout().itemAt(1).widget().text().strip().replace("$", ""))

                try:
                    price_input = self.price_input.text().strip()
                    if not price_input:
                        QMessageBox.warning(self, "Warning", "Price field must be filled.")
                        return

                    # Handle percentage change
                    if price_input.endswith('%'):
                        percentage_str = price_input[:-1].strip()

                        if not percentage_str:
                            QMessageBox.warning(self, "Warning", "Please enter a number before the '%' symbol.")
                            return

                        try:
                            percentage_change = float(percentage_str)
                        except ValueError:
                            QMessageBox.warning(self, "Warning", "Only numbers are accepted for percentage changes.")
                            return

                        if percentage_change == 0:
                            QMessageBox.warning(self, "Warning", "Price will not change.")
                            return

                        is_increase = percentage_change > 0

                        if is_increase:
                            new_price = current_price * (1 + percentage_change / 100)
                        else:
                            new_price = current_price * (1 + percentage_change / 100)

                        new_price_cents = int(round(new_price * 100))

                        if new_price_cents == int(current_price * 100):
                            QMessageBox.warning(self, "Warning", "Price will not change.")
                            return

                    # Handle direct numeric changes (e.g., "+1" or "-2")
                    elif price_input.startswith('+') or price_input.startswith('-'):
                        try:
                            change_value = float(price_input)
                        except ValueError:
                            QMessageBox.warning(self, "Error",
                                                "Only valid numeric values are accepted for price changes.")
                            return

                        new_price = current_price + change_value
                        new_price_cents = int(round(new_price * 100))

                        if new_price_cents == int(current_price * 100):
                            QMessageBox.warning(self, "Warning", "Price will not change.")
                            return

                    # Handle exact price input
                    else:
                        try:
                            new_price = float(price_input)
                        except ValueError:
                            QMessageBox.warning(self, "Error", "Only numbers or percentage changes are accepted.")
                            return

                    # Ensure the new price is within valid bounds
                    if new_price * 100 < self.min_price:
                        QMessageBox.warning(self, "Warning", f"Price cannot be lower than ${self.min_price / 100:.2f}.")
                        return
                    if new_price * 100 > self.max_price:
                        QMessageBox.warning(self, "Warning",
                                            f"Maximum allowed price is ${self.max_price / 100:.2f} USD")
                        return

                    # Round new price to nearest cent
                    new_price = int(round(new_price * 100))

                except ValueError as e:
                    QMessageBox.warning(self, "Error", f"Invalid price input: {e}")
                    return

                # Fetch API key from column 9
                api_key_item = self.inventory_table.item(row, 9)
                if api_key_item:
                    api_key = api_key_item.text()
                else:
                    QMessageBox.warning(self, "Error", "API key is missing for the selected item.")
                    continue

                # Add to the list of items to change price
                items_to_change.append((row, asset_id_item.text(), item_name, current_price, new_price / 100, api_key))

        # Confirm changes
        if items_to_change:
            grouped_operations = defaultdict(int)
            for _, _, item_name, current_price, new_price, _ in items_to_change:
                grouped_operations[(item_name, current_price, new_price)] += 1

            confirm_message = "You are about to change the price for the following items:\n"
            for (item_name, current_price, new_price), count in grouped_operations.items():
                if count > 1:
                    confirm_message += f"{count}x {item_name} {current_price:.2f}$ → {new_price:.2f}$\n"
                else:
                    confirm_message += f"{item_name} {current_price:.2f}$ → {new_price:.2f}$\n"

            if not self.show_confirmation_dialog(confirm_message.strip()):
                return

        # Process successful changes
        successful_changes = []
        for row, asset_id, item_name, current_price, new_price, api_key in items_to_change:
            listing_id = self.inventory_table.item(row, 5).text()
            if listing_id:
                try:
                    response = change_price(api_key, listing_id, int(new_price * 100))  # Use the correct API key
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
        # Создание и установка элемента Days on Sale (колонка 3)
        days_on_sale_item = QTableWidgetItem("0d 0h")
        days_on_sale_item.setFont(self.app_font)  # Устанавливаем стандартный шрифт
        days_on_sale_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.inventory_table.setItem(row, 3, days_on_sale_item)

        # Создание виджета для Price (колонка 4)
        price_widget = QWidget()
        price_layout = QHBoxLayout(price_widget)
        price_layout.setContentsMargins(0, 0, 0, 0)

        # Добавление иконки CSFloat
        csfloat_logo = QLabel()
        csfloat_logo.setPixmap(QPixmap(os.path.join(self.icon_path, "csfloat_logo.png")).scaled(20, 20,
                                                                                                Qt.AspectRatioMode.KeepAspectRatio))
        price_layout.addWidget(csfloat_logo)

        # Создание и установка QLabel для цены с установленным шрифтом
        price_label = QLabel(f" {price / 100:.2f}$")
        price_label.setFont(self.app_font)  # Устанавливаем стандартный шрифт
        price_layout.addWidget(price_label)

        price_layout.addStretch()
        self.inventory_table.setCellWidget(row, 4, price_widget)

        # Создание и установка элемента Listing ID (колонка 5)
        listing_id_item = QTableWidgetItem(listing_id)
        listing_id_item.setFont(self.app_font)  # Устанавливаем стандартный шрифт
        listing_id_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.inventory_table.setItem(row, 5, listing_id_item)
        self.inventory_table.setColumnHidden(5, True)  # Скрываем колонку Listing ID

        # Создание и установка элемента Created At (колонка 7)
        created_at_item = QTableWidgetItem(datetime.now(timezone.utc).isoformat())
        created_at_item.setFont(self.app_font)  # Устанавливаем стандартный шрифт
        created_at_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.inventory_table.setItem(row, 7, created_at_item)

        # Создание и установка элемента Price Value (колонка 8)
        price_value_item = QTableWidgetItem()
        price_value_item.setData(Qt.ItemDataRole.DisplayRole, price)
        price_value_item.setData(Qt.ItemDataRole.UserRole, price)
        price_value_item.setFont(self.app_font)  # Устанавливаем стандартный шрифт
        self.inventory_table.setItem(row, 8, price_value_item)

        # Применение сортировки после обновления
        if self.last_sorted_column is not None and self.last_sort_order is not None:
            self.inventory_table.sortItems(self.last_sorted_column, self.last_sort_order)
        self.apply_last_sort()

    def update_item_price(self, row, new_price):
        # Создание виджета для Price (колонка 4)
        price_widget = QWidget()
        price_layout = QHBoxLayout(price_widget)
        price_layout.setContentsMargins(0, 0, 0, 0)

        # Добавление иконки CSFloat
        csfloat_logo = QLabel()
        csfloat_logo.setPixmap(QPixmap(os.path.join(self.icon_path, "csfloat_logo.png")).scaled(20, 20,
                                                                                                Qt.AspectRatioMode.KeepAspectRatio))
        price_layout.addWidget(csfloat_logo)

        # Создание и установка QLabel для новой цены с установленным шрифтом
        price_label = QLabel(f" {new_price / 100:.2f}$")
        price_label.setFont(self.app_font)  # Устанавливаем стандартный шрифт
        price_layout.addWidget(price_label)

        price_layout.addStretch()
        self.inventory_table.setCellWidget(row, 4, price_widget)

        # Создание и установка элемента Created At (колонка 7)
        created_at_item = QTableWidgetItem(datetime.now(timezone.utc).isoformat())
        created_at_item.setFont(self.app_font)  # Устанавливаем стандартный шрифт
        created_at_item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self.inventory_table.setItem(row, 7, created_at_item)

        # Создание и установка элемента Price Value (колонка 8)
        price_value_item = QTableWidgetItem()
        price_value_item.setData(Qt.ItemDataRole.DisplayRole, new_price)
        price_value_item.setData(Qt.ItemDataRole.UserRole, new_price)
        price_value_item.setFont(self.app_font)  # Устанавливаем стандартный шрифт
        self.inventory_table.setItem(row, 8, price_value_item)

        # Применение сортировки после обновления
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

                # Fetch listing ID (column 5)
                listing_id = self.inventory_table.item(row, 5).text()
                # Check if listing_id exists (item is being sold)
                if not listing_id:
                    QMessageBox.warning(self, "Warning", "Cannot delist item that is not listed.")
                    continue

                # Fetch the item name (column 0)
                item_name = self.inventory_table.item(row, 0).text()

                # Fetch the API key from column 9
                api_key_item = self.inventory_table.item(row, 9)
                if api_key_item:
                    api_key = api_key_item.text()
                else:
                    QMessageBox.warning(self, "Error", "API key is missing for the selected item.")
                    continue

                # Add to the list of items to delist
                items_to_delist.append((persistent_index, listing_id, item_name, api_key))

        if items_to_delist:
            grouped_items = defaultdict(int)
            for _, _, item_name, _ in items_to_delist:
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
        for persistent_index, listing_id, item_name, api_key in items_to_delist:
            row = persistent_index.row()
            try:
                # Send delist request with the correct API key
                response = delete_item(api_key, listing_id)
                if response:
                    items_delisted.append(item_name)
                    self.update_item_as_unsold(row)  # Mark item as unsold in the table
                    time.sleep(0.1)
                else:
                    QMessageBox.warning(self, "Error", f"Failed to delist item {item_name}.")
            except ValueError as ve:
                QMessageBox.warning(self, "Warning", str(ve))
                return
            except urllib.error.HTTPError as http_err:
                QMessageBox.warning(self, "Error", f"HTTP error occurred: {http_err}")
                return
            except Exception as e:
                QMessageBox.warning(self, "Error", f"An unexpected error occurred: {str(e)}")
                return

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

    def update_avatar(self):
        if not self.user_infos:
            return

        # Используем информацию из первого элемента списка, который соответствует дефолтному API ключу
        user_info = next(info for info in self.user_infos if info['api_key'] == self.default_api_key)
        avatar_url = user_info.get("avatar")
        avatar_path = cache_image(avatar_url) if avatar_url else None
        if avatar_path:
            self.avatar_info_button.setIcon(QIcon(avatar_path))

    def show_user_info_dialog(self, title="Account Information"):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)

        label_font = QFont('Oswald', 11)  # Шрифт для всех меток и значений

        outer_layout = QHBoxLayout()

        for user_info in self.user_infos:
            vertical_layout = QVBoxLayout()

            # Аватар пользователя
            avatar_url = user_info.get("avatar")
            avatar_path = cache_image(avatar_url) if avatar_url else None
            if avatar_path:
                avatar_label = QLabel(self)
                avatar_label.setFixedSize(100, 100)
                avatar_pixmap = QPixmap(avatar_path)
                avatar_label.setPixmap(avatar_pixmap.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio))
                vertical_layout.addWidget(avatar_label, alignment=Qt.AlignmentFlag.AlignHCenter)

            # Информация о пользователе
            form_layout = QFormLayout()

            # Устанавливаем шрифт для меток и значений
            def create_labeled_row(label_text, value_text):
                label = QLabel(label_text)
                label.setFont(label_font)
                value = QLabel(value_text)
                value.setFont(label_font)
                form_layout.addRow(label, value)

            create_labeled_row("Steam ID:", user_info.get("steam_id", "N/A"))
            create_labeled_row("Username:", user_info.get("username", "N/A"))
            create_labeled_row("KYC:", user_info.get("know_your_customer", "N/A"))
            create_labeled_row("Balance:", f"{user_info.get('balance', 0) / 100:.2f}$")

            statistics = user_info.get("statistics", {})

            create_labeled_row("Total Sales:", f"{statistics.get('total_sales', 0) / 100:.2f}$")
            create_labeled_row("Total Purchases:", f"{statistics.get('total_purchases', 0) / 100:.2f}$")
            create_labeled_row("Median Trade Time:", f"{statistics.get('median_trade_time', 0) / 60:.0f} minutes")
            create_labeled_row("Total Avoided Trades:", str(statistics.get("total_avoided_trades", 0)))
            create_labeled_row("Total Failed Trades:", str(statistics.get("total_failed_trades", 0)))
            create_labeled_row("Total Verified Trades:", str(statistics.get("total_verified_trades", 0)))
            create_labeled_row("Total Trades:", str(statistics.get("total_trades", 0)))

            total_exhibited = f"{sum(item['price'] for item in self.stall if item.get('user_id') == user_info.get('steam_id')) / 100:.2f}$"
            create_labeled_row("Total Exhibited:", total_exhibited)

            vertical_layout.addLayout(form_layout)
            outer_layout.addLayout(vertical_layout)

        layout.addLayout(outer_layout)
        dialog.setLayout(layout)
        dialog.exec()

    def show_avatar_info(self):
        self.show_user_info_dialog(title="Account Information")

    def show_user_info(self):
        self.show_user_info_dialog(title="User Information")
