from __future__ import division, print_function, unicode_literals
import downloader
import ree as re
from io import BytesIO
import os
from constants import try_n
from utils import Downloader, LazyUrl, get_ext, format_filename, clean_title
import ytdl



@Downloader.register
class Downloader_youporn(Downloader):
    type = 'youporn'
    single = True
    URLS = ['youporn.com']
    display_name = 'YouPorn'

    @classmethod
    def fix_url(cls, url):
        if 'youporn.com' not in url.lower():
            url = 'https://www.youporn.com/watch/{}'.format(url)
        return url

    def read(self):
        video = Video(self.url, cw=self.cw)

        self.urls.append(video.url)
        self.setIcon(video.thumb)

        self.enableSegment()

        self.title = video.title


class Video(object):
    @try_n(4)
    def __init__(self, url, cw=None):
        ydl = ytdl.YoutubeDL(cw=cw)
        info = ydl.extract_info(url)

        f = info['formats'][-1]
        url_video = f['url']
        self.url = LazyUrl(url, lambda _: url_video, self)
        
        self.url_thumb = info['thumbnails'][0]['url']
        self.thumb = BytesIO()
        downloader.download(self.url_thumb, buffer=self.thumb)
        self.title = info['title']
        ext = get_ext(url_video)
        self.filename = format_filename(self.title, info['id'], ext)
