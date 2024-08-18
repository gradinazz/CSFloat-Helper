![enter image description here](https://img001.prntscr.com/file/img001/5jc2VPmeRQSsCN_kEjXa9A.png)
## Installation

### Requirements

-   **Python 3.7 or higher**: Make sure you have Python version 3.7 or higher installed. You can download Python from the [official website](https://www.python.org/).

### Installing Python

1.  Download and install Python from the [official website](https://www.python.org/downloads/).
2.  Ensure that Python and `pip` (Python package manager) are added to your system path.

### Installing Dependencies

1.  Ensure you are in the root directory of the project where the `requirements.txt` file is located.
    
2.  Install the dependencies:
    
    `pip install -r requirements.txt`
    

### Configuration Setup

1.  Modify the `config.json` file in the root directory of the project with the following content:
    
    `{ "api_keys": [ "YOUR_API_KEY", "YOUR_API_KEY" ] }`
    
2.  Replace `"YOUR_API_KEY"` with your actual API key, and you can use multiple keys.
    

## Running the Script

To run the program, use the following command:

`python csfloat_helper.py`

If you prefer to use a bat file for quick launch on Windows, you can use the run_csfloat_helper.bat file located in the project root:

`./run_csfloat_helper.bat`

## Features

### User Interface

-   **Graphical Interface**: The application provides a user-friendly graphical interface for managing the CSFloat inventory.
-   **Filters**: Ability to filter items by name, stickers, and float value.

### Data Loading

-   **Inventory**: The script loads data about the inventory and items listed for sale via the CSFloat API.

### Data Display

-   **Inventory Table**: The application displays the user's inventory in a table with information about the item name, stickers, float value, days listed for sale, price.

### Data Filtering

-   **Dynamic Filtering**: Ability to filter the inventory by item name, sticker, and float value.

### Item Management

-   **Item Sale**: Listing selected items for sale with a specified price.
-   **Remove from Sale**: Removing selected items from sale.
-   **Price Change**: Changing the price of items that are already listed for sale.

### User Information

-   **Displaying Information**: The application allows you to obtain and display information about the user, such as Steam ID, username, balance, total number of sales and purchases, and other data.

## Contributing to the Project

If you have suggestions for improvements or find bugs, please create a Pull Request or Issue on GitHub.
