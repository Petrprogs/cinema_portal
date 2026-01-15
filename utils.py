import json
from functools import wraps
import os
from pathlib import Path
from flask import request

# === JSON helpers ===
def load_json(filename):
    """Load JSON data from a file."""
    with open(filename, 'r') as f:
        return json.load(f)

def save_json(filename, data):
    """Save JSON data to a file."""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

# === Flask helpers ===
def auth_required(f):
    """Decorator to check authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.args.get("box_mac") and not "127.0.0.1" in request.remote_addr:
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


def scan_local_videos(dirs):
    """Scan configured directories for video files"""
    video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.m3u8'}
    video_files = []
    
    for directory in dirs:
        if os.path.exists(directory):
            for root, _, files in os.walk(directory):
                for file in files:
                    if Path(file).suffix.lower() in video_extensions:
                        rel_path = os.path.relpath(os.path.join(root, file), directory)
                        video_files.append({
                            'title': file,
                            'path': os.path.join(root, file),
                            'relative_path': rel_path,
                            'directory': directory
                        })
    
    return video_files