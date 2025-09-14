import requests
from bs4 import BeautifulSoup
import base64
from itertools import product
import threading
import time
import os
import json

class HdRezkaStreamSubtitles():
  def __init__(self, data, codes):
    self.subtitles = {}
    self.keys = []
    if data:
      arr = data.split(",")
      for i in arr:
        temp = i.split("[")[1].split("]")
        lang = temp[0]
        link = temp[1]
        code = codes[lang]
        self.subtitles[code] = {'title': lang, 'link': link}
      self.keys = list(self.subtitles.keys())
  def __str__(self):
    return str(self.keys)
  def __call__(self, id=None):
    if self.subtitles:
      if id:
        if id in self.subtitles.keys():
          return self.subtitles[id]['link']
        for key, value in self.subtitles.items():
          if value['title'] == id:
            return self.subtitles[key]['link']
        if str(id).isnumeric:
          code = list(self.subtitles.keys())[id]
          return self.subtitles[code]['link']
        raise ValueError(f'Subtitles "{id}" is not defined')
      else:
        return None

class HdRezkaStream():
  def __init__(self, season, episode, subtitles={}):
    self.videos = {}
    self.season = season
    self.episode = episode
    self.subtitles = HdRezkaStreamSubtitles(**subtitles)
  def append(self, resolution, link):
    self.videos[resolution] = link
  def __str__(self):
    resolutions = list(self.videos.keys())
    if self.subtitles.subtitles:
      return f"<HdRezkaStream> : {resolutions}, subtitles={self.subtitles}"
    return "<HdRezkaStream> : " + str(resolutions)
  def __repr__(self):
    return f"<HdRezkaStream(season:{self.season}, episode:{self.episode})>"
  def __call__(self, resolution):
    coincidences = list(filter(lambda x: str(resolution) in x , self.videos))
    if len(coincidences) > 0:
      return self.videos[coincidences[0]]
    raise ValueError(f'Resolution "{resolution}" is not defined')


class HdRezkaApi():
  __version__ = 5.2
  def __init__(self, url, email, password):
    self.baseurl = "rezka.si"
    self.HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'}
    self.COOKIES = {}
    self.url = url.split(".html")[0] + ".html"
    self.authorize(email, password)
    self.page = self.getPage()
    self.soup = self.getSoup()
    self.id = self.extractId()
    self.name = self.getName()
    self.type = self.getType()
    #other
    self.translators = None
    self.seriesInfo = None
   
  def authorize(self, email, password):
    data = {
      'login_name': email,
      'login_password': password,
      'login_not_save': '0',
    }
    if os.path.exists("rezka_cookies"):
      self.COOKIES = json.load(open("rezka_cookies", "r"))
      return
    auth_req = requests.post(f"https://{self.baseurl}/ajax/login/", data=data, headers=self.HEADERS)
    if auth_req.json()["success"] == True:
      self.COOKIES = auth_req.cookies.get_dict()
      del self.COOKIES["PHPSESSID"]
      print(self.COOKIES)
      self.COOKIES.update({"hdmbbs": "1"})
      with open("rezka_cookies", "w") as fl:
        fl.write(json.dumps(self.COOKIES, indent=4))
    else:
      print(auth_req.text)

  def getPage(self):
    return requests.get(self.url, headers=self.HEADERS, cookies=self.COOKIES, timeout=10000)

  def getSoup(self):
    return BeautifulSoup(self.page.content, 'html.parser')

  def extractId(self):
    return self.soup.find(id="post_id").attrs['value']

  def getName(self):
    return self.soup.find(class_="b-post__title").get_text().strip()
  
  def getPosterURL(self):
    print(self.soup.find_all("img")[0]["src"])
    return self.soup.find_all("img")[0]["src"]

  def getType(self):
    return self.soup.find('meta', property="og:type").attrs['content']

  @staticmethod
  def clearTrash(data):
    trashList = ["@","#","!","^","$"]
    trashCodesSet = []
    for i in range(2,4):
      startchar = ''
      for chars in product(trashList, repeat=i):
        data_bytes = startchar.join(chars).encode("utf-8")
        trashcombo = base64.b64encode(data_bytes)
        trashCodesSet.append(trashcombo)

    arr = data.replace("#h", "").split("//_//")
    trashString = ''.join(arr)

    for i in trashCodesSet:
      temp = i.decode("utf-8")
      trashString = trashString.replace(temp, '')

    finalString = base64.b64decode(trashString+"==")
    return finalString.decode("latin-1")

  def getTranslations(self):
    arr = {}
    translators = self.soup.find(id="translators-list")
    if translators:
      children = translators.findChildren(recursive=False)
      for child in children:
        if child.text:
          arr[child.text] = child.attrs['data-translator_id']

    if not arr:
      #auto-detect
      def getTranslationName(s):
        table = s.find(class_="b-post__info")
        for i in table.findAll("tr"):
          tmp = i.get_text()
          if tmp.find("переводе") > 0:
            return tmp.split("В переводе:")[-1].strip()
      def getTranslationID(s):
        initCDNEvents = {'video.tv_series': 'initCDNSeriesEvents',
                 'video.movie'    : 'initCDNMoviesEvents'}
        tmp = s.text.split(f"sof.tv.{initCDNEvents[self.type]}")[-1].split("{")[0]
        return tmp.split(",")[1].strip()

      arr[getTranslationName(self.soup)] = getTranslationID(self.page)

    self.translators = arr
    return arr

  def getOtherParts(self):
    parts = self.soup.find(class_="b-post__partcontent")
    other = []
    if parts:
      for i in parts.findAll(class_="b-post__partcontent_item"):
        if 'current' in i.attrs['class']:
          other.append({
            i.find(class_="title").text: self.url
          })
        else:
          other.append({
            i.find(class_="title").text: i.attrs['data-url']
          })
    return other

  @staticmethod
  def getEpisodes(s, e):
    seasons = BeautifulSoup(s, 'html.parser')
    episodes = BeautifulSoup(e, 'html.parser')

    seasons_ = {}
    for season in seasons.findAll(class_="b-simple_season__item"):
      seasons_[ season.attrs['data-tab_id'] ] = season.text

    episodes_ = {}
    for episode in episodes.findAll(class_="b-simple_episode__item"):
      if episode.attrs['data-season_id'] in episodes_:
        episodes_[episode.attrs['data-season_id']] [ episode.attrs['data-episode_id'] ] = episode.text
      else:
        episodes_[episode.attrs['data-season_id']] = {episode.attrs['data-episode_id']: episode.text}

    return seasons_, episodes_

  def getSeasons(self):
    if not self.translators:
      self.translators = self.getTranslations()

    arr = {}
    for i in self.translators:
      js = {
        "id": self.id,
        "translator_id": self.translators[i],
        "action": "get_episodes"
      }
      r = requests.post("https://" + self.baseurl + "/ajax/get_cdn_series/", data=js, cookies=self.COOKIES, headers=self.HEADERS, timeout=100)
      response = r.json()
      if response['success']:
        seasons, episodes = self.getEpisodes(response['seasons'], response['episodes'])
        arr[i] = {
          "translator_id": self.translators[i],
          "seasons": seasons, "episodes": episodes
        }
      time.sleep(0.5)

    self.seriesInfo = arr
    return arr

  def getStream(self, season=None, episode=None, translation=None, index=0):
    def makeRequest(data):
      r = requests.post("https://" + self.baseurl + "/ajax/get_cdn_series/", data=data, cookies=self.COOKIES, headers=self.HEADERS)
      r = r.json()
      if r['success']:
        arr = self.clearTrash(r['url']).split(",")
        stream = HdRezkaStream( season,
                    episode,
                    subtitles={'data':  r['subtitle'], 'codes': r['subtitle_lns']}
                    )
        for i in arr:
          res = i.split("[")[1].split("]")[0]
          video = i.split("[")[1].split("]")[1].split(" or ")[1]
          stream.append(res, video)
        return stream

    def getStreamSeries(self, season, episode, translation_id):
      if not (season and episode):
        raise TypeError("getStream() missing required arguments (season and episode)")
      
      season = str(season)
      episode = str(episode)

      if not self.seriesInfo:
        self.getSeasons()
      seasons = self.seriesInfo

      tr_str = list(self.translators.keys())[list(self.translators.values()).index(translation_id)]

      if not season in list(seasons[tr_str]['episodes']):
        raise ValueError(f'Season "{season}" is not defined')

      if not episode in list(seasons[tr_str]['episodes'][season]):
        raise ValueError(f'Episode "{episode}" is not defined')

      return makeRequest({
        "id": self.id,
        "translator_id": translation_id,
        "season": season,
        "episode": episode,
        "action": "get_stream"
      })
      

    def getStreamMovie(self, translation_id):
      return makeRequest({
        "id": self.id,
        "translator_id": translation_id,
        "action": "get_movie"
      })      


    if not self.translators:
      self.translators = self.getTranslations()

    if translation:
      if translation.isnumeric():
        if translation in self.translators.values():
          tr_id = translation
        else:
          raise ValueError(f'Translation with code "{translation}" is not defined')

      elif translation in self.translators:
        tr_id = self.translators[translation]
      else:
        raise ValueError(f'Translation "{translation}" is not defined')

    else:
      tr_id = list(self.translators.values())[index]


    if self.type == "video.tv_series":
      return getStreamSeries(self, season, episode, tr_id)
    elif self.type == "video.movie":
      return getStreamMovie(self, tr_id)
    else:
      raise TypeError("Undefined content type")


  def getSeasonStreams(self, season, translation=None, index=0, ignore=False, progress=None):
    season = str(season)

    if not progress:
      progress = lambda cur, all: print(f"{cur}/{all}", end="\r")

    if not self.translators:
      self.translators = self.getTranslations()
    trs = self.translators

    if translation:
      if translation.isnumeric():
        if translation in trs.values():
          tr_id = translation
        else:
          raise ValueError(f'Translation with code "{translation}" is not defined')

      elif translation in trs:
        tr_id = trs[translation]
      else:
        raise ValueError(f'Translation "{translation}" is not defined')

    else:
      tr_id = list(trs.values())[index]

    tr_str = list(trs.keys())[list(trs.values()).index(tr_id)]

    if not self.seriesInfo:
      self.getSeasons()
    seasons = self.seriesInfo

    if not season in list(seasons[tr_str]['episodes']):
      raise ValueError(f'Season "{season}" is not defined')

    series = seasons[tr_str]['episodes'][season]
    series_length = len(series)

    streams = {}
    threads = []
    progress(0, series_length)

    for episode_id in series:
      def make_call(ep_id, retry=True):
        try:
          stream = self.getStream(season, ep_id, tr_str)
          streams[ep_id] = stream
          progress(len(streams), series_length)
        except Exception as e:
          if retry:
            time.sleep(1)
            if ignore:
              return make_call(ep_id)
            else:
              return make_call(ep_id, retry=False)
          if not ignore:
            ex_name = e.__class__.__name__
            ex_desc = e
            print(f"{ex_name} > ep:{ep_id}: {ex_desc}")
            streams[ep_id] = None
            progress(len(streams), series_length)
      
      t = threading.Thread(target=make_call, args=(episode_id,), daemon=True)
      t.start()
      threads.append(t)

    for t in threads:
      t.join()

    sorted_streams = {k: streams[k] for k in sorted(streams, key=lambda x: int(x))}
    return sorted_streams

class HdRezkaSearch():
  def __init__(self, query, email, password):
    self.query = query
    self.HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36'}
    self.COOKIES = {}
    self.authorize(email, password)
    self.baseurl = "rezka.si"

  def authorize(self, email, password):
    data = {
      'login_name': email,
      'login_password': password,
      'login_not_save': '0',
    }
    if os.path.exists("rezka_cookies"):
      self.COOKIES = json.load(open("rezka_cookies", "r"))
      return
    auth_req = requests.post(f"https://{self.baseurl}ajax/login/", data=data, headers=self.HEADERS)
    if auth_req.json()["success"] == True:
      self.COOKIES = auth_req.cookies.get_dict()
      del self.COOKIES["PHPSESSID"]
      self.COOKIES.update({"hdmbbs": "1"})
      print(self.COOKIES)
      with open("rezka_cookies", "w") as fl:
        fl.write(json.dumps(self.COOKIES, indent=4))
    else:
      print(auth_req.text)

  def full_search(self):
    response = requests.get(f'https://{self.baseurl}/search/', params={'do': 'search', 'subaction': 'search', 'q': self.query}, headers=self.HEADERS, cookies=self.COOKIES, timeout=100)
    parsed_html = BeautifulSoup(response.text, 'lxml')
    results = []
    for link in parsed_html.find_all('div', attrs={"class": "b-content__inline_item"}):
        url = link.find("div").find("a")["href"]
        if url.startswith("/"):
          url = f"https://{self.baseurl}" + url
        id_movie = url.split("-")[0].split("/")[-1]
        print(id_movie)
        quick_content = requests.post(f'https://{self.baseurl}/engine/ajax/quick_content.php', data={'id': id_movie, 'is_touch': '1'}, headers=self.HEADERS, cookies=self.COOKIES, timeout=100)
        quick_content_bs = BeautifulSoup(quick_content.text, 'lxml')
        description = quick_content_bs.find_all("div", attrs={"class": "b-content__bubble_text"})[0].text.replace("\n","").strip()
        censor = quick_content_bs.find_all("div", attrs={"class": "b-content__bubble_text"})[1].find("b")
        censor = censor.text if censor else "N/A"
        genres = ", ".join([genre.text for genre in quick_content_bs.find_all("div", attrs={'class': "b-content__bubble_text"})[-1].find_all("a")])
        #artists = ", ".join([genre.text for genre in quick_content_bs.find_all("div", attrs={'class': "b-content__bubble_str"})[-1].find_all("span", attrs={"itemprop": "name"})[:3]]) + "..."
        bubbles = quick_content_bs.find_all("div", attrs={'class': "b-content__bubble_str"})
        if not bubbles:  # Check if the list is empty
            artists = "n/a"
        else:
            artists = ", ".join([genre.text for genre in bubbles[-1].find_all("span", attrs={"itemprop": "name"})[:3]]) + "..."
        imdb = quick_content_bs.find('span', attrs={'class': 'imdb'})
        kp = quick_content_bs.find('span', attrs={'class': 'kp'})
        ratings = f"{imdb if imdb else 'IMDb: N/A'} {kp if kp else 'Кинопоиск: N/A'}"
        poster = link.find("div").find("a").find("img")["src"]
        title = link.find_all("div", attrs={"class": "b-content__inline_item-link"})[-1].find("a").text
        other_info = link.find_all("div", attrs={"class": "b-content__inline_item-link"})[-1].find("div").text
        year = other_info.split(",")[0]
        country = other_info.split(",")[1]
        item_type = link.find("div").find("a").find("span")["class"][-1]
        results.append({"id": id_movie, "title": title, "description": description, 
            "censor": censor, "genres": genres, "artists": artists, "ratings": ratings, "year": year, "country": country, "poster": poster, "url": url, "item_type": item_type})
    print(results)
    return results

  def get_recommendations(self, type, page):
    response = requests.get(f'https://{self.baseurl}/{type}/page/{page}/', headers=self.HEADERS, cookies=self.COOKIES, timeout=100)
    print(response.text)
    parsed_html = BeautifulSoup(response.text, 'lxml')
    results = []
    for link in parsed_html.find_all('div', attrs={"class": "b-content__inline_item"}):
        url = link.find("div").find("a")["href"]
        if url.startswith("/"):
          url = f"https://{self.baseurl}" + url
        id_movie = url.split("-")[0].split("/")[-1]
        print(id_movie)
        quick_content = requests.post(f'https://{self.baseurl}/engine/ajax/quick_content.php', data={'id': id_movie, 'is_touch': '1'}, headers=self.HEADERS, cookies=self.COOKIES, timeout=100)
        quick_content_bs = BeautifulSoup(quick_content.text, 'lxml')
        description = quick_content_bs.find_all("div", attrs={"class": "b-content__bubble_text"})[0].text.replace("\n","").strip()
        censor = quick_content_bs.find_all("div", attrs={"class": "b-content__bubble_text"})[1].find("b")
        censor = censor.text if censor else "N/A"
        genres = ", ".join([genre.text for genre in quick_content_bs.find_all("div", attrs={'class': "b-content__bubble_text"})[-1].find_all("a")])
        #artists = ", ".join([genre.text for genre in quick_content_bs.find_all("div", attrs={'class': "b-content__bubble_str"})[-1].find_all("span", attrs={"itemprop": "name"})[:3]]) + "..."
        bubbles = quick_content_bs.find_all("div", attrs={'class': "b-content__bubble_str"})
        if not bubbles:  # Check if the list is empty
            artists = "n/a"
        else:
            artists = ", ".join([genre.text for genre in bubbles[-1].find_all("span", attrs={"itemprop": "name"})[:3]]) + "..."
        imdb = quick_content_bs.find('span', attrs={'class': 'imdb'})
        kp = quick_content_bs.find('span', attrs={'class': 'kp'})
        ratings = f"{imdb if imdb else 'IMDb: N/A'} {kp if kp else 'Кинопоиск: N/A'}"
        poster = link.find("div").find("a").find("img")["src"]
        title = link.find_all("div", attrs={"class": "b-content__inline_item-link"})[-1].find("a").text
        other_info = link.find_all("div", attrs={"class": "b-content__inline_item-link"})[-1].find("div").text
        year = other_info.split(",")[0]
        country = other_info.split(",")[1]
        item_type = link.find("div").find("a").find("span")["class"][-1]
        results.append({"id": id_movie, "title": title, "description": description, 
            "censor": censor, "genres": genres, "artists": artists, "ratings": ratings, "year": year, "country": country, "poster": poster, "url": url, "item_type": item_type})
    return results
    
