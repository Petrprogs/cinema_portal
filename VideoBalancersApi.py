import json
import os
import traceback

import requests

try:
    import config
except ImportError:
    print("config.py not found! Exiting...")
    exit()
from videobalancers import HdRezkaApi, TurboApi, VibixApi

API_BASE_URL_FILE = 'balancer_domain.json'
DEFAULT_API_BASE_URL = 'https://api4.rhserv.vu'

def load_api_base_url():
    if os.path.exists(API_BASE_URL_FILE):
        with open(API_BASE_URL_FILE, 'r') as f:
            data = json.load(f)
            return data.get('api_base_url', DEFAULT_API_BASE_URL)
    return DEFAULT_API_BASE_URL

def save_api_base_url(url):
    with open(API_BASE_URL_FILE, 'w') as f:
        json.dump({'api_base_url': url}, f)

def fetch_and_update_api_base_url():
    js_url = 'https://reyohoho.serv00.net/assets/index-D3BeTuNy.js'
    try:
        resp = requests.get(js_url, timeout=10)
        if resp.status_code == 200:
            text = resp.text
            start = text.find('api_endpoints:JSON.stringify([{url:"')
            if start == -1:
                return None
            start += len('api_endpoints:JSON.stringify([{url:"')
            end = text.find('",', start)
            if end == -1:
                return None
            url = text[start:end]
            if url.startswith('https://'):
                domain = url.split('/')[2]
                new_base_url = f'https://{domain}'
            else:
                new_base_url = url
            save_api_base_url(new_base_url)
            global API_BASE_URL
            API_BASE_URL = new_base_url
            return new_base_url
        else:
            return None
    except Exception as e:
        print(traceback.format_exc())
        return None

API_BASE_URL = load_api_base_url()

class VideoBalancersApi():
    def __init__(self, kp_id=None):
        self.kp_id = kp_id
        if kp_id:
            self.iframes = self.get_iframes(kp_id)
            self.url = None

    def search(self, query) -> list:
        data = {"code": "31", "term": query}
        response = requests.get(
            f"{API_BASE_URL}/search/{query}", params=data)
        return response.json() if response.status_code == 200 else []

    def get_iframes(self, kp_id):
        data = {
            'kinopoisk': str(kp_id)
        }
        
        response = requests.post(
            f"{API_BASE_URL}/cache", data=data, verify=False)
        if response.status_code == 200:
            response_json = response.json()
            print(response_json)
            return response_json

    def get_providers(self, search_data):
        result = []
        if not isinstance(self.iframes, list):
            return result  # Defensive: old format or error

        for iframe_info in self.iframes:
            name = iframe_info.get('name', '').lower()
            if name == "turbo":
                print("Found turbo")
                result.append("turbo")
            elif name == "vibix":
                print("Found vibix")
                result.append("vibix")
            elif name == "hdrezka":
                print("Found hdrezka")
                self.url = iframe_info.get('iframe')
                result.append("hdRezka")

        rezka = HdRezkaApi.HdRezkaApi("", search_data, config.REZKA_EMAIL, config.REZKA_PASSWORD)
        if rezka.found_item:
            print("Found hdrezka")
            self.url = rezka.url
            result.append("hdRezka")
        if config.RUTRACKER_USERNAME and config.RUTRACKER_PASSWORD:
            result.append("rutracker")
        return result

    def get_provider(self, name, search_data=None):
        if not isinstance(self.iframes, list):
            return None  # Defensive: old format or error

        name = name.lower()
        for iframe_info in self.iframes:
            print(iframe_info)
            if iframe_info.get('name', '').lower() == name:
                if name == "turbo":
                    return TurboApi.TurboApi(iframe_info.get("iframe"), self.kp_id)
                elif name == "vibix":
                    return VibixApi.VibixApi(iframe_info.get("iframe"))
        if search_data:
            print("Return rezka")
            return HdRezkaApi.HdRezkaApi('', search_data, config.REZKA_EMAIL, config.REZKA_PASSWORD)
        return None
