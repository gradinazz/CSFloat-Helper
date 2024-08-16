import requests
import json

# Constants for API endpoints
API_USER_INFO = "https://csfloat.com/api/v1/me"
API_INVENTORY = "https://csfloat.com/api/v1/me/inventory"
API_STALL = "https://csfloat.com/api/v1/users/{steam_id}/stall?limit=999"
LISTINGS_URL = "https://csfloat.com/api/v1/listings"

def get_user_info(api_key):
    headers = {'Authorization': api_key}
    try:
        response = requests.get(API_USER_INFO, headers=headers)
        response.raise_for_status()

        user_info = response.json().get("user", {})
        return user_info
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        print(f"Other error occurred: {err}")
        return None

def get_inventory_data(api_key):
    headers = {"Authorization": api_key}
    try:
        response_inventory = requests.get(API_INVENTORY, headers=headers)
        response_inventory.raise_for_status()
        inventory_data = response_inventory.json()
        if isinstance(inventory_data, dict) and 'items' in inventory_data:
            return inventory_data['items']
        elif isinstance(inventory_data, list):  # Если данные уже в списке
            return inventory_data
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
    headers = {"Authorization": api_key}
    try:
        response_stall = requests.get(API_STALL.format(steam_id=steam_id), headers=headers)
        response_stall.raise_for_status()
        return response_stall.json().get("data", [])
    except requests.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        return None
    except Exception as err:
        print(f"Other error occurred: {err}")
        return None

def sell_item(api_key, asset_id, price, marketplace="steam"):
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
    headers = {"Authorization": api_key}
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