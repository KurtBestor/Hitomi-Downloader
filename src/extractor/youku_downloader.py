from __future__ import division, print_function, unicode_literals
import downloader
import youtube_dl
from m3u8_tools import M3u8_stream
from utils import LazyUrl, get_ext, Downloader, compatstr
from fucking_encoding import clean_title
from io import BytesIO


@Downloader.register
class Downloader_youku(Downloader):
    type = 'youku'
    single = True
    URLS = ['v.youku.com']
    
    def init(self):
        self.url = self.url.replace('youku_', '', 1)

    @property
    def id(self):
        return self.url

    def read(self):
        ui_setting = self.ui_setting
        format = compatstr(ui_setting.youtubeFormat.currentText()).lower().strip()

        video = Video(self.url, format)
        video.url()# get thumb

        self.urls.append(video.url)
        self.setIcon(video.thumb)

        self.title = video.title

        
class Video(object):
    _url = None
    
    def __init__(self, url, format='title (id)'):
        self.url = LazyUrl(url, self.get, self)
        self.format = format

    def get(self, url):
        if self._url:
            return self._url
        
        ydl = youtube_dl.YoutubeDL()
        info = ydl.extract_info(url)

        # get best video
        fs = info['formats']
        fs = sorted(fs, key=lambda x: int(x['width']), reverse=True)
        f = fs[0]
        url_video = f['url']

        # thumb
        self.thumb_url = info['thumbnails'][0]['url']
        self.thumb = BytesIO()
        downloader.download(self.thumb_url, buffer=self.thumb)

        # m3u8
        print(f['protocol'])
        if 'm3u8' in f['protocol']:
            url_video = M3u8_stream(url_video, referer=url)

        # title & filename
        format = self.format.replace('title', '###title').replace('id', '###id')
        self.title = format.replace('###title', info['title']).replace('###id', u'{}'.format(info['id']))
        ext = '.mp4'
        self.filename = clean_title(self.title, n=-len(ext)) + ext

        self._url = url_video
        
        return self._url

