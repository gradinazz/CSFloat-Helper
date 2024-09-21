import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

CACHE_DIR = "cache"

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def load_config():
    try:
        with open("config.json", 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print("Config file not found!")
        return None

def cache_image(url):
    if not url:
        return None

    file_name = url.split("/")[-1]
    file_path = os.path.join(CACHE_DIR, file_name)
    if not os.path.exists(file_path):
        try:
            with urllib.request.urlopen(url) as response:
                with open(file_path, 'wb') as file:
                    file.write(response.read())
        except urllib.error.URLError as e:
            print(f"Failed to download image from {url}: {e}")
            return None
    return file_path

def calculate_days_on_sale(created_at):
    try:
        created_at_datetime = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        delta = now - created_at_datetime
        days = delta.days
        hours = delta.seconds // 3600
        return f"{days}d {hours}h"
    except ValueError as e:
        print(f"Error parsing date: {e}")
        return ""
