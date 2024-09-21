# modules/ui.py
import os
from PyQt6.QtWidgets import QMainWindow, QApplication, QTabWidget
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import QThreadPool, Qt  # Добавлен импорт Qt

from modules.ui_tab1 import Tab1
from modules.ui_tab2 import Tab2

class SteamInventoryApp(QMainWindow):
    def __init__(self, api_keys):
        super().__init__()
        self.api_keys = api_keys

        # Инициализация пула потоков
        self.threadpool = QThreadPool()

        # Путь к иконкам (убедитесь, что путь правильный)
        self.icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'utils', 'icons'))

        self.initUI()

    def initUI(self):
        app_font = QFont('Oswald')
        app_font.setPointSize(11)
        app_font.setWeight(QFont.Weight.Normal)
        self.setFont(app_font)

        # Установка иконки окна
        self.setWindowIcon(QIcon(os.path.join(self.icon_path, 'steam.png')))
        self.setWindowTitle('CSFloat Helper')

        # Создание вкладок
        self.tabs = QTabWidget(self)

        # Инициализация вкладок
        self.tab2 = Tab2(self.api_keys, self.icon_path, parent=self)
        self.tab1 = Tab1(self.api_keys, self.icon_path, self.tab2, parent=self)

        self.tabs.addTab(self.tab1, "Inventory")
        self.tabs.addTab(self.tab2, "Buy Orders")

        self.setCentralWidget(self.tabs)

        # Удаление возможности изменения размера окна через флаги
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.CustomizeWindowHint |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        # Фиксированный размер окна
        fixed_width = 780
        fixed_height = 780
        self.setFixedSize(fixed_width, fixed_height)

        # Загрузка сохранённых ширин колонок
        self.load_column_sizes()

        self.show()

        # Асинхронная загрузка данных после инициализации UI
        self.load_data()

    def load_data(self):
        """Load data for all API keys."""
        self.tab1.load_data(self.threadpool)  # Передача threadpool в Tab1
        self.tab2.load_buy_orders(self.threadpool)  # Передача threadpool в Tab2

    def load_column_sizes(self):
        """Load column widths for both tabs."""
        self.tab1.load_column_widths()
        self.tab2.load_column_widths()

    def save_column_sizes(self):
        """Save column widths for both tabs."""
        self.tab1.save_column_widths()
        self.tab2.save_column_widths()

    def closeEvent(self, event):
        """Handle window close event to save column sizes."""
        self.save_column_sizes()
        event.accept()

    # Опционально: Переопределение метода resizeEvent для предотвращения изменения размера
    def resizeEvent(self, event):
        # Всегда возвращаем окно к фиксированному размеру
        self.resize(self.width(), self.height())
        super().resizeEvent(event)
