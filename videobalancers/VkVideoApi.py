import curl_cffi
from urllib.parse import quote
import time


class VkVideoApi:
    def __init__(self, client_id="52461373", client_secret="o557NLIkAErNhakXrQ7A") -> None:
        self.base_url = "https://api.vkvideo.ru/method"
        self.auth_url = "https://login.vk.com/"
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expiry = 0
        self._refresh_token()
    
    def _refresh_token(self):
        """Get or refresh anonymous access token"""
        with curl_cffi.Session() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0",
                "Accept": "*/*",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Referer": "https://vkvideo.ru/",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://vkvideo.ru",
                "Sec-Fetch-Storage-Access": "none",
                "Sec-GPC": "1",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "cross-site",
                "Priority": "u=4"
            }
            
            post_data = {
                "client_secret": self.client_secret,
                "client_id": self.client_id,
                "scopes": "audio_anonymous,video_anonymous,photos_anonymous,profile_anonymous",
                "isApiOauthAnonymEnabled": "false",
                "version": "1",
                "app_id": "6287487"
            }
            
            response = session.post(
                f"{self.auth_url}?act=get_anonym_token",
                headers=headers,
                data=post_data
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("type") == "okay" and "data" in result:
                self.access_token = result["data"]["access_token"]
                self.token_expiry = result["data"]["expired_at"]
                return True
            else:
                raise Exception(f"Failed to get token: {result}")
    
    def _ensure_valid_token(self):
        """Check if token is expired and refresh if needed"""
        if time.time() >= self.token_expiry - 300:  # Refresh 5 minutes before expiry
            self._refresh_token()
    
    def __make_request__(self, endpoint, data={}):
        self._ensure_valid_token()
        
        with curl_cffi.Session() as session:
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0",
                "Accept": "*/*",
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Referer": "https://vkvideo.ru/",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://vkvideo.ru",
                "Sec-GPC": "1",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site",
                "Priority": "u=0",
                "TE": "trailers"
            }
            
            # Prepare POST data
            post_data = {
                "screen_ref": "search_video_service",
                "input_method": "keyboard_search_button",
                "access_token": self.access_token
            }
            post_data.update(data)
            
            response = session.post(
                f"{self.base_url}{endpoint}",
                params={"v": "5.276", "client_id": self.client_id},
                headers=headers,
                data=post_data
            )
            response.raise_for_status()
            return response.json()

    def search(self, query: str):
        """
        Search for videos on VK Video
        
        Args:
            query: Search query string
            
        Returns:
            List of video items with id, title, thumbnail_url, video_url and direct_url
        """
        result = self.__make_request__("/catalog.getVideoSearchWeb2", {"q": query})
        
        query_items = []
        if "response" in result and "catalog_videos" in result["response"]:
            for item in result["response"]["catalog_videos"]:
                video_data = item.get("video", {})
                
                # Get the best quality thumbnail
                thumbnail_url = ""
                images = video_data.get("image", [])
                if images:
                    # Prefer larger images
                    thumbnail_url = images[-1].get("url", "")
                
                # Get direct video URL (use mp4_720 if available, fallback to highest quality)
                video_url = ""
                files = video_data.get("files", {})
                for quality in ["mp4_720", "mp4_480", "mp4_360", "mp4_240", "mp4_144"]:
                    if quality in files and files[quality]:
                        video_url = files[quality]
                        break
                
                query_items.append({
                    "id": f"{video_data.get('owner_id', '')}_{video_data.get('id', '')}",
                    "title": video_data.get("title", ""),
                    "thumbnail_url": thumbnail_url,
                    "video_url": video_url,
                    "direct_url": video_data.get("direct_url", ""),
                    "duration": video_data.get("duration", 0),
                    "views": video_data.get("views", 0),
                    "likes": video_data.get("likes", {}).get("count", 0)
                })
        
        return query_items
    
    def get_token_info(self):
        """Get current token information"""
        return {
            "access_token": self.access_token[:50] + "..." if self.access_token else None,
            "expires_at": self.token_expiry,
            "expires_in": max(0, self.token_expiry - int(time.time())) if self.token_expiry else 0
        }