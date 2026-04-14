import curl_cffi

class FilmachRutube:
    def __init__(self) -> None:
        self.base_url = "https://rutube.ru/api"
        self.author_ids = 32181632
        pass
    
    def __make_request__(self, endpoint, params={}):
        with curl_cffi.Session(impersonate="chrome131") as session:
            params["client"] = "wdp"
            params["author_ids"] = self.author_ids
            params["page"] = 1
            response = session.get(f"{self.base_url}{endpoint}", params=params)
            response.raise_for_status()
            return response.json()

    def search(self, query):
        result = self.__make_request__("/search/video", {"query": query})
        query_items = []
        for item in result["results"]:
            query_items.append({
                "id": item["id"],
                "title": item["title"],
                "thumbnail_url": item["thumbnail_url"],
                "video_url": item["video_url"]
            })
        return query_items
