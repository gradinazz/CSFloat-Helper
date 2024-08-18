import sys
from PyQt6.QtWidgets import QApplication
from modules.ui import SteamInventoryApp
from modules.utils import load_config

def main():
    config = load_config()
    api_keys = config.get("api_keys", [])
    if not api_keys:
        print("No API keys found in the config file.")
        return

    app = QApplication(sys.argv)
    window = SteamInventoryApp(api_keys=api_keys)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
