import json
import urllib.request
import urllib.error
import logging

# Constants for API endpoints
API_USER_INFO = "https://csfloat.com/api/v1/me"
API_INVENTORY = "https://csfloat.com/api/v1/me/inventory"
API_STALL = "https://csfloat.com/api/v1/users/{steam_id}/stall?limit=999"
LISTINGS_URL = "https://csfloat.com/api/v1/listings"
BUY_ORDERS = "https://csfloat.com/api/v1/me/buy-orders?page=0&limit=100&order=desc"
BUY_ORDERS_URL_TEMPLATE = "https://csfloat.com/api/v1/me/buy-orders?page={page}&limit=100&order=desc"
BUY_ORDERS_DELETE_URL = "https://csfloat.com/api/v1/buy-orders/{order_id}"


def get_user_info(api_key):
    """
    Получение информации о пользователе.
    """
    url = API_USER_INFO
    headers = {'Authorization': api_key}
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            user_info = json.load(response).get("user", {})
            return user_info
    except urllib.error.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except urllib.error.URLError as err:
        print(f"Other error occurred: {err}")
        return None

def get_inventory_data(api_key):
    url = API_INVENTORY
    headers = {'Authorization': api_key}
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            inventory_data = json.load(response)
            if isinstance(inventory_data, dict) and 'items' in inventory_data:
                return inventory_data['items']
            elif isinstance(inventory_data, list):  # Если данные уже в списке
                return inventory_data
            else:
                print("Unexpected response format.")
                return []
    except urllib.error.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except urllib.error.URLError as err:
        print(f"Other error occurred: {err}")
        return None

def get_stall_data(api_key, steam_id):
    url = API_STALL.format(steam_id=steam_id)
    headers = {'Authorization': api_key}
    
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            stall_data = json.load(response).get("data", [])
            return stall_data
    except urllib.error.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except urllib.error.URLError as err:
        print(f"Other error occurred: {err}")
        return None

def sell_item(api_key, asset_id, price, marketplace="steam"):
    url = LISTINGS_URL
    data = {
        "asset_id": asset_id,
        "price": price,
        "type": "buy_now"
    }
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as http_err:
        if http_err.code == 400:
            error_data = json.load(http_err)
            if error_data.get("code") == 4:
                raise ValueError("Item overpriced. You need to complete KYC.") from http_err
        raise ValueError(f"HTTP error occurred: {http_err}") from http_err
    except urllib.error.URLError as err:
        raise ValueError(f"An unexpected error occurred: {err}") from err

def delete_item(api_key, listing_id):
    url = f"{LISTINGS_URL}/{listing_id}"
    headers = {'Authorization': api_key}
    
    req = urllib.request.Request(url, headers=headers, method='DELETE')
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except urllib.error.URLError as err:
        print(f"Other error occurred: {err}")
        return None

def change_price(api_key, listing_id, new_price):
    url = f"{LISTINGS_URL}/{listing_id}"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }
    data = json.dumps({"price": new_price}).encode('utf-8')

    req = urllib.request.Request(url, data=data, headers=headers, method='PATCH')

    try:
        with urllib.request.urlopen(req) as response:
            return json.load(response)
    except urllib.error.HTTPError as http_err:
        if http_err.code == 400:
            error_data = json.load(http_err)
            if error_data.get("code") == 4:
                raise ValueError("Item overpriced. You need to complete KYC.") from http_err
        raise ValueError(f"HTTP error occurred: {http_err}") from http_err
    except urllib.error.URLError as err:
        raise ValueError(f"An unexpected error occurred: {err}") from err
        
def get_buy_orders(api_key):
    """
    Синхронная функция для получения всех buy orders с поддержкой пагинации.
    """
    headers = {'Authorization': api_key}
    all_orders = []
    page = 0

    while True:
        url = BUY_ORDERS_URL_TEMPLATE.format(page=page)
        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req) as response:
                data = json.load(response)
                orders = data.get("orders", [])
                all_orders.extend(orders)

                # Если меньше 100 ордеров, прекращаем пагинацию
                if len(orders) < 100:
                    break

                page += 1

        except urllib.error.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
            return None
        except urllib.error.URLError as err:
            print(f"Other error occurred: {err}")
            return None

    return all_orders


# Set up logging
logging.basicConfig(filename='error.log', level=logging.ERROR)


def delete_order_by_id(order_id, api_key):
    """
    Синхронная функция для удаления ордера по его ID.
    """
    url = BUY_ORDERS_DELETE_URL.format(order_id=order_id)
    headers = {'Authorization': api_key}

    req = urllib.request.Request(url, headers=headers, method='DELETE')

    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                return True  # Успешное удаление
            else:
                return False  # Если статус не 200
    except urllib.error.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return False
    except urllib.error.URLError as err:
        print(f"Other error occurred: {err}")
        return False