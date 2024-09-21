# csfloat_helper.py
import sys
from PyQt6.QtWidgets import QApplication
from modules.ui import SteamInventoryApp
from modules.utils import load_config

def main():
    app = QApplication(sys.argv)

    # Загрузка конфигурации и API-ключей
    config = load_config()
    api_keys = config.get("api_keys", [])
    if not api_keys:
        print("No API keys found in the config file.")
        sys.exit(1)

    # Создание окна и загрузка данных
    window = SteamInventoryApp(api_keys=api_keys)
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
