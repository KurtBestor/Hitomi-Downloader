from __future__ import division, print_function, unicode_literals
import downloader
import ree as re
from io import BytesIO
import os
from fucking_encoding import clean_title
from constants import try_n
from utils import Downloader, LazyUrl, get_ext, compatstr
import youtube_dl


def get_id(url):
    id = re.find('/watch/([0-9]+)', url)
    if id is None:
        raise Exception('no id')
    return id


@Downloader.register
class Downloader_youporn(Downloader):
    type = 'youporn'
    single = True
    URLS = ['youporn.com']
    
    def init(self):
        if self.url.startswith('youporn_'):
            self.url = 'https://www.youporn.com/watch/{}'.format(self.url.replace('youporn_', '', 1))

    @property
    def id(self):
        return get_id(self.url)

    def read(self):
        ui_setting = self.ui_setting
        format = compatstr(ui_setting.youtubeFormat.currentText()).lower().strip()

        video = Video(self.url, format)

        self.urls.append(video.url)
        self.setIcon(video.thumb)

        self.customWidget.enableSegment()

        self.title = video.title


class Video(object):
    @try_n(4)
    def __init__(self, url, format='title'):
        ydl = youtube_dl.YoutubeDL()
        info = ydl.extract_info(url)

        f = info['formats'][-1]
        url_video = f['url']
        self.url = LazyUrl(url, lambda _: url_video, self)
        
        self.url_thumb = info['thumbnails'][0]['url']
        self.thumb = BytesIO()
        downloader.download(self.url_thumb, buffer=self.thumb)
        format = format.replace('title', '###title').replace('id', '###id')
        self.title = format.replace('###title', info['title']).replace('###id', '{}'.format(info['id']))
        ext = get_ext(url_video)
        self.filename = clean_title(self.title, n=-len(ext)) + ext
