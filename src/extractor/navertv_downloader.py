import downloader
import ree as re
from io import BytesIO as IO
import os
from constants import try_n
from error_printer import print_error
from utils import Downloader, compatstr, LazyUrl, get_ext, format_filename, clean_title
import ytdl



class Downloader_navertv(Downloader):
    type = 'navertv'
    single = True
    URLS = ['tv.naver.com']
    display_name = 'Naver TV'

    @classmethod
    def fix_url(cls, url):
        if not re.match(r'https?://.+', url, re.I):
            url = f'https://tv.naver.com/v/{url}'
        return url

    def read(self):
        video = Video(self.url, cw=self.cw)
        video.url()#

        self.urls.append(video.url)
        self.setIcon(video.thumb)

        self.enableSegment()

        self.title = video.title



class Video:
    _url = None

    def __init__(self, url, cw=None):
        self.url = LazyUrl(url, self.get, self)
        self.cw = cw

    @try_n(4)
    def get(self, url):
        if self._url:
            return self._url

        ydl = ytdl.YoutubeDL(cw=self.cw)
        info = ydl.extract_info(url)
        fs = [f for f in info['formats'] if f['protocol'] in ['http', 'https']]
        fs = sorted(fs, key=lambda f: int(f.get('width', 0)), reverse=True)
        if not fs:
            raise Exception('No MP4 videos')
        f = fs[0]
        self._url = f['url']

        self.thumb_url = info['thumbnails'][0]['url']
        self.thumb = IO()
        downloader.download(self.thumb_url, buffer=self.thumb)
        self.title = info['title']
        id = info['id']
        ext = get_ext(self._url)
        self.filename = format_filename(self.title, id, ext)
        return self._url
