import requests
from bs4 import BeautifulSoup
import json
import re
import base64
from urllib.parse import unquote
try:
    import demjson3
except:
    import demjson as demjson3

class VibixApi():
    def __init__(self, iframe_url=None):
        self.get_json_options(iframe_url)

    def get_json_options(self, iframe_url):
        headers = self._get_default_headers()
        response = requests.get(iframe_url, headers=headers)
        if response.status_code == 200:
            self._process_json_response(response.text)

    def _get_default_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Connection': 'keep-alive',
            'Referer': 'https://reyohoho.serv00.net/',
            "Host": "4f463c79.obrut.show",
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'iframe',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Priority': 'u=4',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        }

    def _process_json_response(self, response_text):
        bs = BeautifulSoup(response_text, features="lxml")
        script_tag = bs.find_all("script")[3]
        script_content = script_tag.text.split('Playerjs(')[1].split(");")[0]
        self.data_dict = demjson3.decode(script_content)

    def getTranslations(self, season=1, episode=1):
        if self.data_dict.get("poster"):
            return [ep["title"] for ep in self.data_dict["file"]]
        else:
            return [ep["title"] for ep in self.data_dict["file"][season-1]["folder"][episode-1]["folder"]]

    def getSeasons(self):
        if not self.data_dict.get("poster"):
            return [item["title"] for item in self.data_dict["file"]]
        return None

    def getEpisodes(self, season):
        if not self.data_dict.get("poster"):
            return [item["title"] for item in self.data_dict["file"][season-1]["folder"]]
        return None

    def getStreams(self, tr_index=0, season=1, episode=1):
        if self.data_dict.get("poster"):
            streams = self.data_dict["file"][tr_index]["file"].split(",")
        else:
            streams = self.data_dict["file"][season-1]["folder"][episode -
                                                                 1]["folder"][tr_index]["file"].split(",")

        result_streams = []
        for stream in streams:
            res = stream.split("[")[1].split("]")[0].replace("MP4", "").strip()
            if res == "Авто":
                break
            video = stream.split("[")[1].split("]")[1]
            result_streams.append([res, video])
        return reversed(result_streams)

    def getStream(self, file_url):
        return file_url.replace('https', 'http')

    def _get_default_stream_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0',
            'Accept': '*/*',
            'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3',
            'Origin': 'https://4f463c79.obrut.show',
            'Connection': 'keep-alive',
            'Referer': 'https://4f463c79.obrut.show/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'Priority': 'u=0',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache',
        }
