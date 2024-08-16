import sys
from PyQt6.QtWidgets import QApplication
from modules.ui import SteamInventoryApp
from modules.utils import load_config

def main():
    config = load_config()
    if not config:
        print("Config file not found. Please ensure config.json exists and contains the required API key.")
        sys.exit(1)

    app = QApplication(sys.argv)
    window = SteamInventoryApp(api_key=config.get("api_key"))
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
