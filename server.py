from flask import Flask, request, send_file, jsonify, redirect, Response, send_from_directory
from flask_cors import CORS
from flask_caching import Cache
import json
import os
import subprocess
from videobalancers import HdRezkaApi
import shutil
import VideoBalancersApi
import base64
from functools import wraps
from VideoBalancersApi import fetch_and_update_api_base_url

# Configuration
config = {
    "DEBUG": True,
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300
}

# Constants
OUTPUT_DIR = 'hls_output'
ICON_BASE_URL = "http://94.177.51.191/res/?res="
BASE_URL = "http://94.177.51.191"

# Initialize Flask app
app = Flask(__name__)
app.config.from_mapping(config)
CORS(app)
cache = Cache(app)
cache.init_app(app)

# Global state
app_state = {
    'ffmpeg_process': None,
    'data': {},
    'rezka': None,
    'balancers_api': None
}

# Helper functions
def load_json(filename):
    """Load JSON data from a file."""
    with open(filename, 'r') as f:
        return json.load(f)

def save_json(filename, data):
    """Save JSON data to a file."""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

def get_icon(item_type):
    """Return the appropriate icon based on the item type."""
    return f"{ICON_BASE_URL}film.png" if item_type == "films" else f"{ICON_BASE_URL}series.png"

def auth_required(f):
    """Decorator to check authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.args.get("box_mac"):
            return "Unauthorized", 401
        return f(*args, **kwargs)
    return decorated_function

def clean_url_from_unwanted_params(url):
    """Remove unwanted query parameters from URL."""
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
    
    # Parameters to remove
    unwanted_params = ['box_client', 'box_mac', 'initial', 'platform', 'country', 'tvp', 'hw']
    
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    
    # Remove unwanted parameters
    for param in unwanted_params:
        query_params.pop(param, None)
    
    # Rebuild query string
    new_query = urlencode(query_params, doseq=True)
    
    # Reconstruct URL
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))

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

def initialize_ffmpeg(stream_url, origin="", referer="", proxy=""):
    """Initialize the FFmpeg process before the first request."""
    if app_state['data'].get("drc_stream") != stream_url:
        if app_state['ffmpeg_process']:
            app_state['ffmpeg_process'].kill()
        
        app_state['data']["drc_stream"] = stream_url
        start_ffmpeg(stream_url, origin, referer, proxy)
        app_state['ffmpeg_process'] = None

def start_ffmpeg(mp4_url, origin="", referer="", proxy=""):
    """Start the FFmpeg process to convert the MP4 stream into HLS segments."""
    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    ffmpeg_command = [
        'ffmpeg',
        '-copyts',
        '-user_agent', 'Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0',
        '-i', mp4_url,
        '-hls_base_url', BASE_URL + '/',
        '-filter_complex', 'compand=attacks=0:points=-80/-900|-45/-15|-27/-9|0/-7|20/-7:gain=5',
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-f', 'hls',
        '-hls_time', '3',
        '-hls_list_size', '0',
        '-hls_playlist_type', 'event',
        '-hls_flags', 'append_list',
        '-hls_segment_filename', os.path.join(OUTPUT_DIR, 'segment%03d.ts'),
        os.path.join(OUTPUT_DIR, 'stream.m3u8'),
    ]
    
    if origin:
        ffmpeg_command[2:2] = ["-headers", f"Origin: {origin}"]
    if referer:
        ffmpeg_command[2:2] = ["-headers", f"Referer: {referer}"]
    if proxy:
        ffmpeg_command[2:2] = ["-http_proxy", "bot0TN93:wLiPe9hNN8@45.151.98.28:50100"]
    
    return subprocess.Popen(ffmpeg_command)

# Routes
@app.route("/")
@auth_required
def main_page():
    global BASE_URL, ICON_BASE_URL
    BASE_URL = request.host_url
    ICON_BASE_URL = request.host_url+"res/?res="
    index_page = load_json("main_page.json")
    for channel in index_page["channels"]:
        channel["playlist_url"] = channel["playlist_url"].replace("http://94.177.51.191/", request.host_url)
    return jsonify(index_page)

@app.route("/bookmarks/", strict_slashes=False)
@auth_required
def watched():
    db_dict = load_json("db.json")
    response_template = load_json("search_result_page.json")
    db_dict["bookmarks"].reverse()

    for item in db_dict["bookmarks"]:
        base64_url = base64.b64encode(item['url'].encode()).decode()
        response_template["channels"].append(create_channel_item(
            title=item["title"],
            icon=f"{ICON_BASE_URL}film.png",
            description=item["description"],
            playlist_url=item["url"],
            menu=[{
                "title": "Из избранного", 
                "playlist_url": f"{BASE_URL}/rem_from_fav?url={base64_url}"
            }]
        ))
    return jsonify(response_template)

@app.route("/add_to_fav/", strict_slashes=False)
def add_to_fav():
    feed_response = load_json("search_result_page.json")
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
    feed_response = load_json("search_result_page.json")
    db_dict = load_json("db.json")
    
    url = base64.b64decode(request.args.get("url")).decode()
    db_dict["bookmarks"] = [d for d in db_dict["bookmarks"] if d['url'] != url]
    
    save_json("db.json", db_dict)
    feed_response.update({
        "notify": "Успешно удалено из избранного", 
        "cmd": "stop();reload();"
    })
    return jsonify(feed_response)

@app.route('/stream.m3u8')
def serve_playlist():
    """Serve the HLS playlist (m3u8 file)."""
    initialize_ffmpeg(
        request.args.get("stream"),
        request.args.get("origin"),
        request.args.get("referer"),
        request.args.get("proxy")
    )
    
    while not os.path.exists(f"{OUTPUT_DIR}/stream.m3u8"):
        pass
    
    return send_from_directory(OUTPUT_DIR, 'stream.m3u8', mimetype='application/vnd.apple.mpegurl')

@app.route('/segment<count>.ts')
def serve_segment(count):
    """Serve the HLS segment files (.ts)."""
    return send_from_directory(OUTPUT_DIR, f'segment{count}.ts', mimetype='video/MP2T')

@app.route("/process_item/", strict_slashes=False)
@cache.cached(query_string=True)
def process_item():
    response_template = load_json("search_result_page.json")
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
        app_state["rezka"] = HdRezkaApi.HdRezkaApi(url, email="timoshinp72@gmail.com", password="3198084972")
    
    streams = app_state["rezka"].getStream(
        request.args.get("s"),
        request.args.get("e"),
        translation=request.args.get("translation")
    )
    
    for i, (res, stream_url) in enumerate(streams.videos.items(), start=1):
        clean_url = stream_url.split(":hls")[0].replace("https", "http")
        
        response_template["channels"].append(create_channel_item(
            title=f"{app_state['rezka'].name} {res}",
            icon=f"{ICON_BASE_URL}film.png",
            parser=f"{BASE_URL}/mark_watched?url={url}&e={request.args.get('e')}&s={request.args.get('s')}",
            stream_url=clean_url
        ))
        
        if res == "1080p":
            response_template["channels"].append(create_channel_item(
                title=f"{app_state['rezka'].name} {res} DRC",
                parser=f"{BASE_URL}/mark_watched?url={url}",
                icon=f"{ICON_BASE_URL}film.png",
                stream_url=f"{BASE_URL}/stream.m3u8?stream={clean_url}"
            ))
    
    return jsonify(response_template)

def handle_season(response_template, url):
    """Handle the season request."""
    if not app_state.get("rezka"):
        app_state["rezka"] = HdRezkaApi.HdRezkaApi(url, email="timoshinp72@gmail.com", password="3198084972")
        if not app_state.get("transl"):
            seasons = app_state["rezka"].getSeasons()
            app_state["transl"] = next(
                translation for translation in seasons.values() 
                if translation["translator_id"] == str(request.args.get("translation")))
    
    episodes = app_state["transl"]["episodes"][request.args.get("s")]
    
    for episode_number in range(1, len(episodes) + 1):
        response_template["channels"].append(create_channel_item(
            title=f"Эпизод {episode_number}",
            icon=f"{ICON_BASE_URL}film.png",
            playlist_url=f"{BASE_URL}process_item?url={url}&translation={request.args.get('translation')}"
                        f"&s={request.args.get('s')}&e={episode_number}"
        ))
    
    return jsonify(response_template)

def handle_translation(response_template, url):
    """Handle the translation request."""
    if not app_state.get("rezka"):
        app_state["rezka"] = HdRezkaApi.HdRezkaApi(url, email="timoshinp72@gmail.com", password="3198084972")
    
    if app_state["rezka"].type == "video.movie":
        streams = app_state["rezka"].getStream('1', '1', translation=request.args.get("translation"))
        subs = [[sub[1]["title"], sub[1]["link"]] for sub in streams.subtitles.subtitles.items()]
        
        for i, (res, stream_url) in enumerate(streams.videos.items(), start=1):
            clean_url = stream_url.split(":hls")[0].replace("https", "http")
            
            response_template["channels"].append(create_channel_item(
                title=f"{app_state['rezka'].name} {res}",
                icon=f"{ICON_BASE_URL}film.png",
                stream_url=clean_url,
                subtitles=subs
            ))
            
            if res == "1080p":
                response_template["channels"].append(create_channel_item(
                    title=f"{app_state['rezka'].name} {res} DRC",
                    icon=f"{ICON_BASE_URL}film.png",
                    stream_url=f"{BASE_URL}/stream.m3u8?stream={clean_url}"
                ))
        
        return jsonify(response_template)

    seasons = app_state["rezka"].getSeasons()
    app_state["transl"] = next(
        translation for translation in seasons.values() 
        if translation["translator_id"] == str(request.args.get("translation")))
    
    for season in app_state["transl"]["seasons"].keys():
        response_template["channels"].append(create_channel_item(
            title=f"Сезон {season}",
            icon=f"{ICON_BASE_URL}series.png",
            playlist_url=f"{BASE_URL}process_item?url={url}&translation={request.args.get('translation')}&s={season}"
        ))
    
    return jsonify(response_template)

def handle_url(response_template, url):
    """Handle the URL request, getting translations."""
    app_state["rezka"] = HdRezkaApi.HdRezkaApi(url, email="timoshinp72@gmail.com", password="3198084972")
    translations = app_state["rezka"].getTranslations()
    
    for tr_name, tr_id in translations.items():
        response_template["channels"].append(create_channel_item(
            title=tr_name if tr_name else "По умолчанию",
            icon=f"{ICON_BASE_URL}series.png",
            playlist_url=f"{BASE_URL}process_item?url={url}&translation={tr_id}"
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

@app.route("/res/", strict_slashes=False)
def resources():
    return send_file("res/" + request.args.get("res"), as_attachment=True)

# Turbo CDN parser routes
@app.route("/turbo/search", strict_slashes=False)
def turbo_search():
    search_data = load_json("search_result_page.json")
    balancers_api = VideoBalancersApi.VideoBalancersApi()
    search_result = balancers_api.search(request.args.get("search"))    

    # Ensure mapping exists
    if 'kp_id_to_title' not in app_state:
        app_state['kp_id_to_title'] = {}

    for item in search_result:
        # Store mapping for later use
        app_state['kp_id_to_title'][str(item['id'])] = item['title']
        search_data["channels"].append(create_channel_item(
            title=item["title"],
            icon=f"{ICON_BASE_URL}film.png",
            description=f'<img style="float: left; padding-right: 15px" src="{item["poster"]}">',
            playlist_url=f"{request.host_url}turbo/process_item?id={item['id']}",  # No title in URL
            menu=[{
                "title": "В избранное", 
                "playlist_url": f"{request.host_url}add_to_fav?url={request.host_url}turbo/process_item?id={item['id']}"
            }]
        ))
    
    return jsonify(search_data)

@app.route("/turbo/process_item", strict_slashes=False)
def turbo_process_item():
    response_template = load_json("search_result_page.json")
    
    if request.args.get("trs"):
        return handle_turbo_series_translation(
            response_template, 
            request.args.get("id"),
            request.args.get("s"),
            request.args.get("e"),
            request.args.get("trs")
        )
    elif request.args.get("e"):
        return handle_turbo_episode(
            response_template,
            request.args.get("id"),
            request.args.get("s"),
            request.args.get("e")
        )
    elif request.args.get("s"):
        return handle_turbo_season(
            response_template,
            request.args.get("id"),
            request.args.get("s")
        )
    elif request.args.get("tr"):
        return handle_turbo_translation(
            response_template,
            request.args.get("id"),
            request.args.get("tr")
        )
    elif request.args.get("source"):
        return handle_turbo_cdn(
            response_template,
            request.args.get("source")
        )
    elif request.args.get("id"):
        return handle_turbo_id(
            response_template,
            request.args.get("id")
        )

def handle_turbo_cdn(response_template, cdn_name):
    """Handle CDN source selection."""
    kp_id = request.args.get("id")
    # Use title from mapping if needed
    title = app_state.get('kp_id_to_title', {}).get(str(kp_id))
    query_params = {
        "query": title,
        "kp_id": kp_id
    }
    
    app_state["balancers_api"] = VideoBalancersApi.VideoBalancersApi(
        kp_id
    ).get_provider(cdn_name, query_params)
    if cdn_name == "hdRezka":
        return redirect(f"{request.host_url}process_item?url={app_state['balancers_api'].url}", 302)
    
    if hasattr(app_state["balancers_api"], 'getSeasons'):
        seasons = app_state["balancers_api"].getSeasons()
        if seasons:
            for season in seasons:
                response_template["channels"].append(create_channel_item(
                    title=season,
                    icon=f"{ICON_BASE_URL}film.png",
                    playlist_url=f"{clean_url_from_unwanted_params(request.url)}&s={season.split(' ')[0] if season.split(' ')[0].isdigit() else season.split(' ')[1]}"
                ))
            return jsonify(response_template)
    
    translations = app_state["balancers_api"].getTranslations()
    watched_db = load_json("db.json")
    
    for i, translation in enumerate(translations):
        clean_url = clean_url_from_unwanted_params(request.url)
        is_watched = any(
            not ("season" in watched and "episode" in watched)
            for watched in watched_db["watched"]
            if watched["url"] == clean_url.split("&")[0]
        )
        
        response_template["channels"].append(create_channel_item(
            title=f"<s>{translation}</s>" if is_watched else translation,
            icon=f"{ICON_BASE_URL}film.png",
            parser=f"{request.host_url}mark_watched?url={clean_url}",
            playlist_url=f"{clean_url}&tr={i}"
        ))
    
    return jsonify(response_template)

def handle_turbo_id(response_template, kp_id):
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
            icon=f"{ICON_BASE_URL}film.png",
            playlist_url=f"{clean_url_from_unwanted_params(request.url)}&source={provider}"
        ))
    
    return jsonify(response_template)

def handle_turbo_translation(response_template, kp_id, tr_index):
    """Handle translation selection for movies."""
    if not app_state.get("balancers_api"):
        app_state["balancers_api"] = VideoBalancersApi.VideoBalancersApi(kp_id).get_provider(
            request.args.get("source"))
    streams = app_state["balancers_api"].getStreams(int(tr_index))
    search_title = app_state.get('kp_id_to_title', {}).get(str(kp_id), "Unknown")
    for quality, stream_url in streams:
        response_template["channels"].append(create_channel_item(
            title=f"{search_title} {quality}",
            icon=f"{ICON_BASE_URL}film.png",
            stream_url=f"{request.host_url}turbo/redir?url={stream_url}"
        ))
        if quality in ("1080p", "720p", "1080", "720"):
            response_template["channels"].append(create_channel_item(
                title=f"{search_title} {quality} DRC",
                icon=f"{ICON_BASE_URL}film.png",
                stream_url=f"{BASE_URL}/stream.m3u8?stream={stream_url}"
            ))
    return jsonify(response_template)

def handle_turbo_season(response_template, kp_id, season):
    """Handle season selection for series."""
    if not app_state.get("balancers_api"):
        app_state["balancers_api"] = VideoBalancersApi.VideoBalancersApi(kp_id).get_provider(
            request.args.get("source"))
    
    episodes = app_state["balancers_api"].getEpisodes(int(season))
    watched_db = load_json("db.json")
    
    clean_url = clean_url_from_unwanted_params(request.url)
    for episode in episodes:
        ep_num = episode.split(" ")[0] if episode.split(" ")[0].isdigit() else episode.split(" ")[1]
        is_watched = any(
            item for item in watched_db["watched"]
            if (item["url"] == clean_url.split("&")[0] and
                item.get("season") == request.args["s"] and
                item.get("episode") == ep_num)
        )
        
        response_template["channels"].append(create_channel_item(
            title=f"<s>{episode}</s>" if is_watched else episode,
            icon=f"{ICON_BASE_URL}film.png",
            parser=f"{request.host_url}mark_watched?url={clean_url.split('&')[0]}"
                  f"&season={request.args.get('s')}&episode={ep_num}",
            playlist_url=f"{clean_url}&e={ep_num}"
        ))
    
    return jsonify(response_template)

def handle_turbo_episode(response_template, kp_id, season, episode):
    """Handle episode selection for series."""
    if not app_state.get("balancers_api"):
        app_state["balancers_api"] = VideoBalancersApi.VideoBalancersApi(kp_id).get_provider(
            request.args.get("source"))
    
    translations = app_state["balancers_api"].getTranslations(int(season), int(episode))
    clean_url = clean_url_from_unwanted_params(request.url)
    for translation in translations:
        response_template["channels"].append(create_channel_item(
            title=translation,
            icon=f"{ICON_BASE_URL}film.png",
            playlist_url=f"{clean_url}&trs={translations.index(translation)}"
        ))
    
    return jsonify(response_template)

def handle_turbo_series_translation(response_template, kp_id, season, episode, tr_index):
    """Handle series translation streams."""
    if not app_state.get("balancers_api"):
        app_state["balancers_api"] = VideoBalancersApi.VideoBalancersApi(kp_id).get_provider(
            request.args.get("source"))
    streams = app_state["balancers_api"].getStreams(int(tr_index), int(season), int(episode))
    for quality, stream_url in streams:
        response_template["channels"].append(create_channel_item(
            title=f"{quality}",
            icon=f"{ICON_BASE_URL}film.png",
            stream_url=f"{request.host_url}turbo/redir?url={stream_url.replace('https','http')}"
        ))
        
        if quality in ("1080p", "720p", "1080", "720"):
            response_template["channels"].append(create_channel_item(
                title=f"{quality} DRC",
                icon=f"{ICON_BASE_URL}film.png",
                stream_url=f"{BASE_URL}/stream.m3u8?stream={stream_url}"
            ))
    
    return jsonify(response_template)

@app.route("/turbo/redir", strict_slashes=False)
def stream_redirect():
    """Redirect to the actual stream URL."""
    return redirect(app_state["balancers_api"].getStream(request.args.get("url")), code=302)

@app.route('/update_balancer_domain', methods=['GET'])
@auth_required
def update_balancer_domain():
    new_domain = fetch_and_update_api_base_url()
    if new_domain:
        return jsonify({'success': True, 'new_domain': new_domain})
    else:
        return jsonify({'success': False, 'error': 'Failed to fetch or parse new domain'}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
