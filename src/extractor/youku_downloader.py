from __future__ import division, print_function, unicode_literals
import downloader
import ytdl
from m3u8_tools import M3u8_stream
from utils import LazyUrl, get_ext, Downloader, format_filename, clean_title
from io import BytesIO


@Downloader.register
class Downloader_youku(Downloader):
    type = 'youku'
    single = True
    URLS = ['v.youku.com']

    def read(self):
        video = Video(self.url)
        video.url()# get thumb

        self.urls.append(video.url)
        self.setIcon(video.thumb)

        self.title = video.title

        
class Video(object):
    _url = None
    
    def __init__(self, url):
        self.url = LazyUrl(url, self.get, self)

    def get(self, url):
        if self._url:
            return self._url
        
        ydl = ytdl.YoutubeDL()
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
        self.title = info['title']
        self.filename = format_filename(self.title, info['id'], '.mp4')

        self._url = url_video
        
        return self._url

