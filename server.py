import atexit
import base64
import mimetypes
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
from urllib.parse import quote_plus, unquote_plus

import yt_dlp
from flask import (
    Flask,
    Response,
    jsonify,
    redirect,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from flask_caching import Cache
from flask_cors import CORS

import VideoBalancersApi
from utils import *
from videobalancers import FilmachRutube, HdRezkaApi, RutrackerApi
try:
    import config
except ImportError:
    print("config.py not found! Exiting...")
    exit()

# Initialize Flask app
app = Flask(__name__)
app.config.from_mapping(config.cache_config)
CORS(app)
cache = Cache(app)
cache.init_app(app)

# Global state
app_state = {
    'ffmpeg_process': None,
    'data': {},
    'rezka': None,
    'balancers_api': None,
    'kp_id_to_title': {},
    'kp_id_to_title_rus': {}
}

def save_app_state():
    """Save app_state to disk"""
    try:
        # Don't save ffmpeg_process as it can't be serialized
        state_to_save = {
            'data': app_state.get('data', {}),
            'rezka_url': app_state.get('rezka').url if app_state.get('rezka') else None,
            'balancers_api_data': getattr(app_state.get('balancers_api'), '__dict__', {}) if app_state.get('balancers_api') else {},
            'kp_id_to_title': app_state.get('kp_id_to_title', {}),
            'kp_id_to_title_rus': app_state.get('kp_id_to_title_rus', {})
        }
        
        with open('app_state.json', 'w', encoding='utf-8') as f:
            json.dump(state_to_save, f, indent=2, ensure_ascii=False)
        print("App state saved successfully")
    except Exception as e:
        print(f"Error saving app state: {e}")

def load_app_state():
    """Load app_state from disk"""
    try:
        if os.path.exists('app_state.json'):
            with open('app_state.json', 'r', encoding='utf-8') as f:
                saved_state = json.load(f)
            
            # Restore basic data
            app_state['data'] = saved_state.get('data', {})
            app_state['kp_id_to_title'] = saved_state.get('kp_id_to_title', {})
            app_state['kp_id_to_title_rus'] = saved_state.get('kp_id_to_title_rus', {})
            
            # Recreate rezka instance if URL exists
            if saved_state.get('rezka_url'):
                app_state['rezka'] = HdRezkaApi.HdRezkaApi(
                    saved_state['rezka_url'], 
                    email=config.REZKA_EMAIL, 
                    password=config.REZKA_PASSWORD
                )
            
            print("App state loaded successfully")
            return True
    except Exception as e:
        print(f"Error loading app state: {e}")
    return False

# Helper functions
def get_icon(item_type):
    """Return the appropriate icon based on the item type."""
    
    return url_for("resources", res="film.png", _external=True) if item_type == "films" else url_for("resources", res="film.png", _external=True)

def create_channel_item(title, icon, description=None, playlist_url=None, menu=None, parser=None, stream_url=None, subtitles=None):
    """Create a standardized channel item dictionary."""
    item = {
        "title": title,
        "logo_30x30": icon,
        "description": description
    }
    if menu:
        item["menu"] = menu
    if parser:
        item["parser"] = parser
    if playlist_url:
        item["playlist_url"] = playlist_url
    if stream_url:
        item["stream_url"] = stream_url
    if subtitles:
        item["subtitles"] = subtitles
    return item

# Routes
@app.route("/")
@auth_required
def main_page():
    index_page = load_json("templates/main_page.json")
    for channel in index_page["channels"]:
        channel["playlist_url"] = channel["playlist_url"].replace("http://94.177.51.191/", request.host_url)
        channel["logo_30x30"] = channel["logo_30x30"].replace("http://94.177.51.191/", request.host_url)
    return jsonify(index_page)

@app.route("/bookmarks/", strict_slashes=False)
@auth_required
def watched():
    db_dict = load_json("db.json")
    response_template = load_json("templates/search_result_page.json")
    db_dict["bookmarks"].reverse()

    for item in db_dict["bookmarks"]:
        if item.get("is_local"):
            # Для локальных видео используем прямой URL
            item_url = item['url']
        else:
            base64_url = base64.b64encode(item['url'].encode()).decode()
            item_url = item['url']
        
        response_template["channels"].append(create_channel_item(
            title=item["title"],
            icon=url_for("resources", res="film.png", _external=True),
            description=item["description"],
            playlist_url=item_url,
            menu=[{
                "title": "Из избранного", 
                "playlist_url": f"{request.host_url}rem_from_fav?url={base64.b64encode(item_url.encode()).decode()}"
            }] if not item.get("is_local") else [{
                "title": "Из избранного",
                "playlist_url": f"{request.host_url}rem_from_fav?url={base64.b64encode(item_url.encode()).decode()}"
            }]
        ))
    return jsonify(response_template)

@app.route("/add_to_fav/", strict_slashes=False)
def add_to_fav():
    feed_response = load_json("templates/search_result_page.json")
    db_dict = load_json("db.json")
    
    url = request.args.get("url")
    item_info = next(item for item in app_state['data'].get("search", {}).get("channels", []) 
                   if item["playlist_url"] == url)
    
    if not any(item for item in db_dict["bookmarks"] if item.get("url") == url):
        db_dict["bookmarks"].append({
            "url": url,
            "description": item_info["description"],
            "title": item_info["title"]
        })
    
    save_json("db.json", db_dict)
    feed_response.update({
        "notify": "Успешно добавлено в избранное", 
        "cmd": "stop();"
    })
    return jsonify(feed_response)

@app.route("/rem_from_fav/", strict_slashes=False)
def rem_from_fav():
    feed_response = load_json("templates/search_result_page.json")
    db_dict = load_json("db.json")
    
    url = base64.b64decode(request.args.get("url")).decode()
    db_dict["bookmarks"] = [d for d in db_dict["bookmarks"] if d['url'] != url]
    
    save_json("db.json", db_dict)
    feed_response.update({
        "notify": "Успешно удалено из избранного", 
        "cmd": "stop();reload();"
    })
    return jsonify(feed_response)

@app.route("/rezka/process_item/", strict_slashes=False)
@cache.cached(query_string=True)
def rezka_process_item():
    response_template = load_json("templates/search_result_page.json")
    url = request.args.get("url")
    if request.args.get("e"):
        return handle_episode(response_template, url)
    if request.args.get("s"):
        return handle_season(response_template, url)
    if request.args.get("translation"):
        return handle_translation(response_template, url)
    
    return handle_url(response_template, url)

def handle_episode(response_template, url):
    """Handle the episode request."""
    if not app_state.get("rezka"):
        app_state["rezka"] = HdRezkaApi.HdRezkaApi(url, email=config.REZKA_EMAIL, password=config.REZKA_PASSWORD)
    
    streams = app_state["rezka"].getStream(
        request.args.get("s"),
        request.args.get("e"),
        translation=request.args.get("translation")
    )
    
    for i, (res, stream_url) in enumerate(streams.videos.items(), start=1):
        clean_url = stream_url.split(":hls")[0].replace("https", "http")
        
        response_template["channels"].append(create_channel_item(
            title=f"{app_state['rezka'].name} {res}",
            icon=url_for("resources", res="film.png", _external=True),
            parser=f"{request.host_url}mark_watched?url={url}&e={request.args.get('e')}&s={request.args.get('s')}",
            stream_url=clean_url
        ))
    
    return jsonify(response_template)

def handle_season(response_template, url):
    """Handle the season request."""
    if not app_state.get("rezka"):
        app_state["rezka"] = HdRezkaApi.HdRezkaApi(url, email=config.REZKA_EMAIL, password=config.REZKA_PASSWORD)
        if not app_state.get("transl"):
            seasons = app_state["rezka"].getSeasons()
            app_state["transl"] = next(
                translation for translation in seasons.values() 
                if translation["translator_id"] == str(request.args.get("translation")))
    
    episodes = app_state["transl"]["episodes"][request.args.get("s")]
    
    for episode_number in range(1, len(episodes) + 1):
        response_template["channels"].append(create_channel_item(
            title=f"Эпизод {episode_number}",
            icon=url_for("resources", res="film.png", _external=True),
            playlist_url=f"{request.host_url}rezka/process_item?url={url}&translation={request.args.get('translation')}"
                        f"&s={request.args.get('s')}&e={episode_number}"
        ))
    
    return jsonify(response_template)

def handle_translation(response_template, url):
    """Handle the translation request."""
    if not app_state.get("rezka"):
        app_state["rezka"] = HdRezkaApi.HdRezkaApi(url, email=config.REZKA_EMAIL, password=config.REZKA_PASSWORD)
    
    if app_state["rezka"].type == "video.movie":
        streams = app_state["rezka"].getStream('1', '1', translation=request.args.get("translation"))
        subs = [[sub[1]["title"], sub[1]["link"]] for sub in streams.subtitles.subtitles.items()]
        
        for i, (res, stream_url) in enumerate(streams.videos.items(), start=1):
            clean_url = stream_url.split(":hls")[0].replace("https", "http")
            
            response_template["channels"].append(create_channel_item(
                title=f"{app_state['rezka'].name} {res}",
                icon=url_for("resources", res="film.png", _external=True),
                stream_url=clean_url,
                subtitles=subs
            ))
        
        return jsonify(response_template)

    seasons = app_state["rezka"].getSeasons()
    app_state["transl"] = next(
        translation for translation in seasons.values() 
        if translation["translator_id"] == str(request.args.get("translation")))
    
    for season in app_state["transl"]["seasons"].keys():
        response_template["channels"].append(create_channel_item(
            title=f"Сезон {season}",
            icon=url_for("resources", res="series.png", _external=True),
            playlist_url=f"{request.host_url}rezka/process_item?url={url}&translation={request.args.get('translation')}&s={season}"
        ))
    
    return jsonify(response_template)

def handle_url(response_template, url):
    """Handle the URL request, getting translations."""
    app_state["rezka"] = HdRezkaApi.HdRezkaApi(url, email=config.REZKA_EMAIL, password=config.REZKA_PASSWORD)
    translations = app_state["rezka"].getTranslations()
    
    for tr_name, tr_id in translations.items():
        response_template["channels"].append(create_channel_item(
            title=tr_name if tr_name else "По умолчанию",
            icon=url_for("resources", res="series.png", _external=True),
            playlist_url=f"{request.host_url}rezka/process_item?url={url}&translation={tr_id}"
        ))
    
    return jsonify(response_template)

@app.route("/mark_watched/", strict_slashes=False)
def mark_watched():
    db_dict = load_json("db.json")
    url = request.args.get("url")
    
    if request.args.get("s") and not any(
        item for item in db_dict["watched"] 
        if (item["url"] == url and 
            item.get("season") == request.args.get("season") and 
            item.get("episode") == request.args.get("episode"))
    ):
        db_dict["watched"].append({
            "url": url,
            "episode": request.args.get("episode"),
            "season": request.args.get("season")
        })
    elif not request.args.get("episode") and not any(
        item for item in db_dict["watched"] if item["url"] == url
    ):
        db_dict["watched"].append({"url": url})
    
    save_json("db.json", db_dict)
    return jsonify({"message": "Success"})

@app.route("/res/<res>", strict_slashes=False)
def resources(res):
    return send_file("res/" + res, as_attachment=True)

# Kinopoisk search route
@app.route("/search", strict_slashes=False)
def turbo_search():
    search_data = load_json("templates/search_result_page.json")
    balancers_api = VideoBalancersApi.VideoBalancersApi()
    search_result = balancers_api.search(request.args.get("search"))    

    # Ensure mappings exist
    if 'kp_id_to_title' not in app_state:
        app_state['kp_id_to_title'] = {}
    if 'kp_id_to_title_rus' not in app_state:
        app_state['kp_id_to_title_rus'] = {}

    for item in search_result["films"]:
        # Store both English and Russian mappings for later use
        app_state['kp_id_to_title'][str(item['filmId'])] = item['nameEn'] + " " + item['year'] if item.get("nameEn") else item.get('nameRu', '')
        app_state['kp_id_to_title_rus'][str(item['filmId'])] = item['nameRu'] + " " + item['year'] if item.get('nameRu') else item.get('nameEn', '')
        print(item)
        description_text = item["description"] if item.get("description") else ""
        if description_text:
            # Find the position of the second period
            first_period = description_text.find(".")
            second_period = description_text.find(".", first_period + 1)
            if second_period != -1:
                description_slice = description_text[:second_period]
            else:
                description_slice = description_text
        else:
            description_slice = ""

        description = (
            f'<img style="float: left; padding-right: 15px" src="{item["posterUrlPreview"]}">'
            f'{item["year"]}<br>'
            f'{", ".join(country["country"] for country in item["countries"])}<br>'
            f'Жанры: {", ".join(genre["genre"] for genre in item["genres"])}<br>'
            f'Оценка Кинопоиск: {item["rating"]}<br>'
            f'{description_slice}'
        )
        search_data["channels"].append(create_channel_item(
            title=item['nameRu'] if item.get("nameRu") else item['nameEn'],
            icon=url_for("resources", res="film.png", _external=True),
            description=description,
            playlist_url=f"{request.host_url}process_item?id={item['filmId']}",  # No title in URL
            menu=[{
                "title": "В избранное", 
                "playlist_url": f"{request.host_url}add_to_fav?url={request.host_url}process_item?id={item['filmId']}"
            }]
        ))
    
    return jsonify(search_data)

@app.route("/process_item", strict_slashes=False)
def process_item():
    response_template = load_json("templates/search_result_page.json")
    if not request.args.get("source"):
        kp_id = request.args.get("id")
        # Use title from mapping if needed
        title = app_state.get('kp_id_to_title', {}).get(str(kp_id))
        query_params = {
            "query": title,
            "kp_id": kp_id
        }
        
        providers = VideoBalancersApi.VideoBalancersApi(kp_id).get_providers(query_params)
        
        for provider in providers:
            response_template["channels"].append(create_channel_item(
                title=provider.capitalize(), 
                icon=url_for("resources", res="film.png", _external=True),
                playlist_url=f"{clean_url_from_unwanted_params(request.url)}&source={provider}"
            ))
        return response_template
    else:
        source = request.args.get("source")
        return handle_cdn(response_template, source)


def handle_cdn(response_template, cdn_name):
    """Handle CDN source selection."""
    kp_id = request.args.get("id")
    title = app_state.get('kp_id_to_title', {}).get(str(kp_id))
    query_params = {
        "query": title,
        "kp_id": kp_id
    }
    app_state["balancers_api"] = VideoBalancersApi.VideoBalancersApi(
        kp_id
    ).get_provider(cdn_name, query_params)
    if cdn_name == "hdRezka":
        return redirect(f"{request.host_url}rezka/process_item?url={app_state['balancers_api'].url}", 302)
    elif cdn_name == "rutracker":
        return redirect(f"{request.host_url}/tracker/process_item?kp_id={kp_id}", 302)
    elif cdn_name == "filmach":
        return redirect(f"{request.host_url}/filmach/process_item?kp_id={kp_id}", 302)

@app.route("/local_videos/", strict_slashes=False)
@auth_required
def local_videos():
    """Display list of local video files"""
    response_template = load_json("templates/search_result_page.json")
    video_files = scan_local_videos(config.LOCAL_VIDEO_DIRS)
    
    if not video_files:
        response_template["channels"].append(create_channel_item(
            title="Локальных видео не найдено",
            icon=url_for("resources", res="film.png", _external=True),
            description=f"Проверенные директории: {', '.join(config.LOCAL_VIDEO_DIRS)}"
        ))
        return jsonify(response_template)
    
    for video in video_files:
        # Кодируем путь для безопасной передачи в URL
        encoded_path = base64.b64encode(video['path'].encode()).decode()
        
        response_template["channels"].append(create_channel_item(
            title=video['title'],
            icon=url_for("resources", res="film.png", _external=True),
            description=f"Путь: {video['relative_path']}",
            stream_url=f"{request.host_url}serve_local_video?path={encoded_path}",
            menu=[{
                "title": "Добавить в избранное",
                "playlist_url": f"{request.host_url}add_local_to_fav?path={encoded_path}&title={base64.b64encode(video['title'].encode()).decode()}"
            }]
        ))
    
    return jsonify(response_template)

@app.route("/serve_local_video", strict_slashes=False)
def serve_local_video():
    """Serve local video file"""
    try:
        file_path = base64.b64decode(request.args.get("path")).decode()
        
        # Проверяем, что файл находится в разрешенной директории
        is_allowed = False
        for allowed_dir in config.LOCAL_VIDEO_DIRS:
            if file_path.startswith(allowed_dir):
                is_allowed = True
                break
        
        if not is_allowed or not os.path.exists(file_path):
            return "File not found or access denied", 404
        
        # Определяем MIME-тип
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'video/mp4'  # Дефолтный тип
        
        file_size = os.path.getsize(file_path)
        range_header = request.headers.get('Range', None)
        
        if range_header:
            # Обработка запроса на частичную загрузку
            from werkzeug.http import parse_range_header
            
            range_obj = parse_range_header(range_header, file_size)
            if range_obj is None:
                return "Invalid range header", 416
            
            ranges = range_obj.ranges
            if len(ranges) != 1:
                return "Multiple ranges not supported", 416
            
            start, end = ranges[0]
            # Если end не указан, устанавливаем его как конец файла
            if end is None:
                end = file_size - 1
            
            if start >= file_size or end >= file_size:
                return "Range not satisfiable", 416
            
            length = end - start + 1
            
            def generate():
                with open(file_path, 'rb') as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk_size = min(8192, remaining)
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                        remaining -= len(chunk)
            
            response = Response(generate(), status=206, mimetype=mime_type)
            response.headers['Content-Range'] = f'bytes {start}-{end}/{file_size}'
            response.headers['Content-Length'] = length
            response.headers['Accept-Ranges'] = 'bytes'
            return response
        
        # Полная загрузка файла с поддержкой range requests
        response = send_file(
            file_path,
            mimetype=mime_type,
            as_attachment=False,
            conditional=True
        )
        response.headers['Accept-Ranges'] = 'bytes'
        return response
        
    except Exception as e:
        print(f"Error serving local video: {e}")
        import traceback
        traceback.print_exc()
        return "Internal server error", 500

@app.route("/tracker/process_item", strict_slashes=False)
def process_tracker_item():
    if request.args.get("id"):
        return handle_topic(request.args.get("id"))
    elif request.args.get("kp_id"):
        return handle_tracker_search(request.args.get("kp_id"))

def handle_tracker_search(kp_id: int):
    def prioritize_hd_content(title):
        """Определение приоритета HD контента"""
        hd_priority = {
            "1080p": 3,  # Высший приоритет
            "720p": 2,
            "hdrip": 2,
            "bdrip": 2,
            "web-dl": 2,
            "hdtv": 1
        }
        
        for quality, priority in hd_priority.items():
            if quality in title.lower():
                return priority
        
        return 0
    search_data = load_json("templates/search_result_page.json")
    title = app_state.get('kp_id_to_title', {}).get(str(kp_id)).replace(")", "").replace("(", "")[:-1] + "*"

    if config.RUTRACKER_PROXY:
        tracker = RutrackerApi.Rutracker(config.RUTRACKER_USERNAME, config.RUTRACKER_PASSWORD, "https://rutracker.org/", proxies={'http': config.RUTRACKER_PROXY, 'https': config.RUTRACKER_PROXY})
    else:
        tracker = RutrackerApi.Rutracker(config.RUTRACKER_USERNAME, config.RUTRACKER_PASSWORD, "https://rutracker.org/")
    search_items = tracker.search(title)
    filtered_items = []
    for item in search_items:
        item_title = item[1].lower()
        item_category = item[0].lower()
        
        if not any(keyword in item_category for keyword in ["кино", "фильм", "сериал"]):
            continue
        
        if any(keyword in item_title for keyword in ["4k", "uhd", "2160p"]):
            continue
        
        quality_score = prioritize_hd_content(item_title)
        
        filtered_items.append({
            'item': item,
            'quality_score': quality_score
        })

    # Сортировка по качеству (лучшие HD версии первыми)
    filtered_items.sort(key=lambda x: x['quality_score'], reverse=True)

    # Добавление в результат
    for filtered in filtered_items:
        item = filtered['item']
        description = f"Категория: {item[0]}\nРазмер: {tracker._convert_size_inverted(item[3])}\nСиды: {item[4]}\nЛичи: {item[5]}"
        search_data["channels"].append(create_channel_item(
                title=item[1],
                icon=url_for("resources", res="film.png", _external=True),
                description=description,
                playlist_url=f"{request.host_url}tracker/process_item?id={item[2]}"
            ))
    return jsonify(search_data)

def handle_topic(topic_id: int):
    search_data = load_json("templates/search_result_page.json")
    if config.RUTRACKER_PROXY:
        tracker = RutrackerApi.Rutracker(config.RUTRACKER_USERNAME, config.RUTRACKER_PASSWORD, "https://rutracker.org/", proxies={'http': config.RUTRACKER_PROXY, 'https': config.RUTRACKER_PROXY})
    else:
        tracker = RutrackerApi.Rutracker(config.RUTRACKER_USERNAME, config.RUTRACKER_PASSWORD, "https://rutracker.org/")
    magnet = tracker.get_magnet_link(topic_id)
    description = tracker.get_info(topic_id)
    print(description)
    video_codecs = re.findall(r"(?:Формат\s+)?[Вв]идео\s*:\s*(.+)", description)
    audio_tracks = re.findall(r"^(Аудио\s*#?\s*(?:\d+\s*:)?\s*.+)$", description, flags=re.MULTILINE)
    print(audio_tracks)
    if len(video_codecs) > 0:
        video_codecs = video_codecs[-1].replace("\n", "").strip()
        match = re.match(r'^(\S+)(\s+)?', video_codecs)
        if match:
            first_word = match.group(1)
            if re.search(r'[\u0400-\u04FF\u0500-\u052F]', first_word):
                # Remove the first word and any following whitespace
                video_codecs = video_codecs[len(match.group(0)):]
        
    if len(audio_tracks) > 0:
        audio_tracks = "<br>".join([item.replace("\n", "").strip() for item in audio_tracks])
    streams = subprocess.run(f'API_PASSWORD="myapipassword" htorrent info -m="{magnet}"', shell=True, capture_output=True).stdout.decode()
    result = []
    lines = streams.strip().split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        
        # Look for file entries
        if line.strip().startswith('- path:'):
            # Extract path and get filename
            path_match = re.search(r'path:\s*(.+)', line)
            if path_match:
                path = path_match.group(1).strip()
                # Extract filename (last part after /)
                filename = path.split('/')[-1]
                
                # Get length from next line
                if i + 1 < len(lines):
                    length_line = lines[i + 1].rstrip()
                    length_match = re.search(r'length:\s*(\d+)', length_line)
                    if length_match:
                        size_bytes = int(length_match.group(1))
                        
                        # Convert to human readable format
                        if size_bytes >= 1024**3:
                            size_human = f"{size_bytes / 1024**3:.2f} GB"
                        elif size_bytes >= 1024**2:
                            size_human = f"{size_bytes / 1024**2:.2f} MB"
                        elif size_bytes >= 1024:
                            size_human = f"{size_bytes / 1024:.2f} KB"
                        else:
                            size_human = f"{size_bytes} B"
                        
                        # Get URL from line after length
                        if i + 2 < len(lines):
                            url_line = lines[i + 2].rstrip()
                            url_match = re.search(r'streamURL:\s*(.+)', url_line)
                            if url_match:
                                url = url_match.group(1).strip()
                                
                                # Add to result
                                result.append({
                                    'name': filename,
                                    'size_bytes': size_bytes,
                                    'size_human': size_human,
                                    'url': url,
                                    'original_path': path  # Optional: include if needed
                                })
                                
                                # Skip the next two lines we've already processed
                                i += 2
        i += 1
    for item in result:
        if item["name"].endswith(".srt"):
                    continue
        description = f"{item['name']}<br>Видео: {video_codecs}<br>{audio_tracks}<br>Размер: {item['size_human']}\n"
        search_data["channels"].append(create_channel_item(
                title=item["name"],
                icon=url_for("resources", res="film.png", _external=True),
                description=description,
                stream_url=item["url"].replace("localhost", request.host.split(":")[0] if ":" in request.host else request.host)
            ))
    return jsonify(search_data)

@app.route("/filmach/process_item", strict_slashes=False)
def process_filmach_item():
    if request.args.get("video_url"):
        return handle_filmach_video_url(
            request.args.get("video_url"),
            request.args.get("format_id")
        )
    elif request.args.get("kp_id"):
        return handle_filmach_search(request.args.get("kp_id"))

def handle_filmach_video_url(video_url, format_id=None):
    response_template = load_json("templates/search_result_page.json")
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'cachedir': False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        formats = info.get('formats', []) or []
        if format_id is None:
            m3u8_formats = [
                fmt for fmt in formats
                if fmt.get('url') and fmt.get('format_id') and 'm3u8' in str(fmt.get('format_id')).lower()
            ]
            grouped_formats = {}
            for fmt in m3u8_formats:
                key = (
                    int(fmt.get('height') or 0),
                    int(fmt.get('width') or 0),
                    int(fmt.get('fps') or 0),
                    fmt.get('format_note') or ''
                )
                current = grouped_formats.get(key)
                if not current or float(fmt.get('tbr') or 0) > float(current.get('tbr') or 0):
                    grouped_formats[key] = fmt

            playable_formats = sorted(
                grouped_formats.values(),
                key=lambda fmt: (
                    int(fmt.get('height') or 0),
                    int(fmt.get('width') or 0),
                    float(fmt.get('tbr') or 0)
                ),
                reverse=True
            )

            for fmt in playable_formats:
                height = fmt.get('height')
                width = fmt.get('width')
                fps = fmt.get('fps')
                quality_label = f"{height}p" if height else "Unknown"
                if fps:
                    quality_label += f" {fps}fps"
                if fmt.get('format_note'):
                    quality_label += f" {fmt['format_note']}"

                description = f"{quality_label}<br>Format: {fmt.get('format_id')}<br>Размер: {fmt.get('filesize', fmt.get('filesize_approx', 0))}"
                response_template['channels'].append(create_channel_item(
                    title=quality_label,
                    icon=url_for("resources", res="film.png", _external=True),
                    description=description,
                    playlist_url=(
                        f"{request.host_url}filmach/process_item?video_url={quote_plus(video_url)}"
                        f"&format_id={quote_plus(str(fmt['format_id']))}"
                    )
                ))
            if not playable_formats:
                response_template.update({
                    'notify': 'Не удалось найти доступные m3u8-форматы для этого видео.',
                    'cmd': 'back();'
                })
            return jsonify(response_template)

        chosen_format = next(
            (fmt for fmt in formats if str(fmt.get('format_id')) == str(format_id)),
            None
        )
        if not chosen_format:
            response_template.update({
                'notify': 'Выбранный формат не найден.',
                'cmd': 'back();'
            })
            return jsonify(response_template)

        stream_url = chosen_format.get('url')
        if not stream_url:
            response_template.update({
                'notify': 'Не удалось получить URL потока для выбранного качества.',
                'cmd': 'back();'
            })
            return jsonify(response_template)

        title = chosen_format.get('format') or f"{chosen_format.get('height', '?')}p"
        response_template['channels'].append(create_channel_item(
            title=f"{title} ({chosen_format.get('format_id')})",
            icon=url_for("resources", res="film.png", _external=True),
            stream_url=stream_url
        ))
        return jsonify(response_template)
    except Exception as e:
        response_template.update({
            'notify': f'Ошибка получения видео: {e}',
            'cmd': 'back();'
        })
        return jsonify(response_template)

def handle_filmach_search(kp_id):
    search_data = load_json("templates/search_result_page.json")
    title = app_state.get('kp_id_to_title_rus', {}).get(str(kp_id)).replace(")", "").replace("(", "")
    client = FilmachRutube.FilmachRutube()
    search_result = client.search(title)
    for item in search_result:
        description = f'<img style="float: left; padding-right: 15px" src="{item["thumbnail_url"]}">{item["title"]}'
        search_data["channels"].append(create_channel_item(
                title=item["title"],
                icon=url_for("resources", res="film.png", _external=True),
                description=description,
                playlist_url=f"{request.host_url}filmach/process_item?video_url={item["video_url"]}"
            ))
    return jsonify(search_data)

def initialize_app():
    """Initialize application on startup"""
    print("Initializing application...")
    load_app_state()
    
    os.makedirs(config.FFMPEG_OUTPUT_DIR, exist_ok=True)
    
    print("Application initialized")

def shutdown_handler(signum=None, frame=None):
    """Handle server shutdown gracefully"""
    print("Shutting down, saving app state...")
    save_app_state()
    if app_state['ffmpeg_process']:
        app_state['ffmpeg_process'].kill()
    sys.exit()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)

initialize_app()
atexit.register(shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)
