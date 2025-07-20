import requests


class SoundCloudApi():
    def __init__(self, client_id, user_id):
        self.client_id = client_id
        self.user_id = user_id
        self.HEADERS = {
            'Host': 'api-v2.soundcloud.com',
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0',       
            'Authorization': 'OAuth 2-298622-1481024943-A1yyuGAL6lhAP',
        }

    def __request(self, url, params):
        params.update(
            {
                "user_id": self.user_id,
                "client_id": self.client_id
            }
        )
        print(params)
        request = requests.get(url, params, headers=self.HEADERS)
        print(request.status_code)
        return request.json()

    def search(self, query):
        params = {"q": query, "limit": '51'}
        return self.__request("https://api-v2.soundcloud.com/search/tracks", params)

    
