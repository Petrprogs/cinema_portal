# Forkplayer FXML Website

A Flask-based backend for streaming movies and series via TurboCDN, Vibix, and HdRezka, with support for SoundCloud music, dynamic API endpoint updating, and on-the-fly video processing.

---

## Features

- **Universal Video Balancer API**: Unified interface for TurboCDN, Vibix, and HdRezka, supporting search, streaming, and playlist generation.
- **Automatic Balancer Domain Update**: The backend can fetch and update the base API domain automatically from a remote JS file. Trigger this by calling `/update_balancer_domain` (GET, with authentication).
- **On-the-fly DRC Conversion**: Uses ffmpeg to provide alternative DRC-processed streams for improved audio.
- **Bookmarks and Watch History**: Add/remove favorites, track watched episodes, and persist user data in `db.json`.
- **In-memory Search Mapping**: When a user searches, the backend stores a mapping of Kinopoisk ID (`kp_id`) to the search title for session use (e.g., HdRezka lookups).
- **Clean Client API**: All client URLs use only IDs; the backend handles all title lookups and passes the correct title to HdRezka as needed.
- **Caching and Performance**: Uses Flask-Caching for efficient repeated queries and responses.
- **CORS Support**: Cross-origin requests are enabled for integration with various clients.
- **Resource Serving**: Static icons and resources are served from the `/res/` endpoint.

---

## API Endpoints

### Main and Navigation

- `/`  
  Returns the main FXML page (JSON) for Forkplayer navigation.

- `/bookmarks/`  
  Returns the user's list of favorite items.

- `/add_to_fav/`  
  Adds an item to the user's favorites.

- `/rem_from_fav/`  
  Removes an item from the user's favorites.

### Search and Content

- `/turbo/search`  
  Search for movies/series. Results include playlist URLs for further actions.

- `/turbo/process_item`  
  Handles all further navigation for a search result (season/episode/translation selection, etc.).

- `/process_item/`  
  Handles HdRezka item processing (season/episode/translation selection, etc.).

### Streaming

- `/stream.m3u8`  
  Serves the HLS playlist for a video stream (with optional DRC conversion).

- `/segment<count>.ts`  
  Serves individual HLS video segments.

- `/turbo/redir`  
  Redirects to the actual stream URL for TurboCDN/Vibix.

### SoundCloud

- `/soundcloud/search`  
  Search for tracks on SoundCloud.

- `/soundcloud/liked`  
  List liked tracks for the user.

### Resources

- `/res/`  
  Serves static resources (icons, etc.).

### Admin/Utility

- `/update_balancer_domain`  
  Triggers a fetch and update of the current balancer API domain (requires authentication).

---

## Project Structure

- `server.py`  
  Main Flask backend, all endpoints, session state, and orchestration.

- `VideoBalancersApi.py`  
  Universal interface for all video balancer parsers (TurboCDN, Vibix, HdRezka). Handles dynamic API base URL, provider selection, and search logic.

- `videobalancers/`  
  - `TurboApi.py` — TurboCDN parser and stream handler.
  - `VibixApi.py` — Vibix parser and stream handler.
  - `HdRezkaApi.py` — HdRezka parser, search, and stream handler.

- `soundcloud_api.py`  
  SoundCloud API integration.

- `main_page.json`, `search_result_page.json`  
  FXML templates for main navigation and search results.

- `db.json`  
  User data: bookmarks, watch history, etc.

- `hls_output/`  
  Temporary directory for HLS video segments (auto-cleaned).

- `res/`  
  Static resources (icons, etc.).

- `balancer_domain.json`  
  Stores the current balancer API domain (auto-updated).

---

## Setup & Requirements

- **Python 3.8+**
- **Dependencies**:  
  - Flask, Flask-CORS, Flask-Caching
  - requests, beautifulsoup4, lxml, demjson3
  - ffmpeg (must be installed and in PATH)
- **Install**:  
  ```
  pip install -r requirements.txt
  ```
- **Run**:  
  ```
  python server.py
  ```
- **Configuration**:  
  - Edit constants in `server.py` for base URLs, ports, etc.
  - Place your icons in `res/`.

---

## Usage Notes

- All endpoints require authentication via `box_user` and `box_mac` query parameters.
- The backend manages all title lookups and session state; the client only needs to use IDs.
- The in-memory mapping for search results is rebuilt on each server restart.
- The balancer domain can be updated at any time via the `/update_balancer_domain` endpoint.

---

## Development

- See `.gitignore` for ignored files (cache, cookies, generated data, etc.).
- All sensitive or user-specific data is kept out of version control.
- Modular design: add new balancer APIs by extending `videobalancers/` and updating `VideoBalancersApi.py`.

---

## Contributing

Feel free to contribute or open issues for bugs and feature requests!


