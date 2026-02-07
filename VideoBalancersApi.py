import requests

try:
    import config
except ImportError:
    print("config.py not found! Exiting...")
    exit()
from videobalancers import HdRezkaApi

class VideoBalancersApi():
    def __init__(self, kp_id=None):
        self.kp_id = kp_id
        if kp_id:
            self.url = None

    def search(self, query) -> list:
        data = {"keyword": query}
        headers = {"X-API-KEY": config.KINOPOISK_API_KEY}
        response = requests.get(
            f"https://kinopoiskapiunofficial.tech/api/v2.1/films/search-by-keyword", params=data, headers=headers)
        return response.json() if response.status_code == 200 else []

    def get_providers(self, search_data):
        result = []

        rezka = HdRezkaApi.HdRezkaApi("", search_data, config.REZKA_EMAIL, config.REZKA_PASSWORD)
        if rezka.found_item:
            print("Found hdrezka")
            self.url = rezka.url
            result.append("hdRezka")
        if config.RUTRACKER_USERNAME and config.RUTRACKER_PASSWORD:
            result.append("rutracker")
        return result

    def get_provider(self, name, search_data=None):
        if search_data:
            print("Return rezka")
            return HdRezkaApi.HdRezkaApi('', search_data, config.REZKA_EMAIL, config.REZKA_PASSWORD)
        return None
