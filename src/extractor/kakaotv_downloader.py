import downloader
import ytdl
from utils import Downloader, try_n, LazyUrl, get_ext, format_filename
from io import BytesIO as IO
from m3u8_tools import M3u8_stream


@Downloader.register
class Downloader_vlive(Downloader):
    type = 'kakaotv'
    URLS = ['tv.kakao']
    single = True
    display_name = 'KakaoTV'

    @classmethod
    def fix_url(cls, url):
        return url.split('?')[0].strip('/')

    def read(self):
        video = Video(self.url, cw=self.cw)
        video.url()#

        self.urls.append(video.url)
        self.setIcon(video.thumb)

        self.enableSegment()

        self.title = video.title



class Video(object):
    _url = None
    
    def __init__(self, url, cw=None):
        self.url = LazyUrl(url, self.get, self)
        self.cw = cw

    @try_n(2)
    def get(self,  url):
        if self._url:
            return self._url
        
        ydl = ytdl.YoutubeDL(cw=self.cw)
        info = ydl.extract_info(url)
        fs = [f for f in info['formats'] if f['ext'] == 'mp4']
        f = sorted(fs, key=lambda f: f['height'])[-1]
        self._url = f['url']
        
        self.thumb_url = info['thumbnails'][0]['url']
        self.thumb = IO()
        downloader.download(self.thumb_url, buffer=self.thumb)
        self.title = info['title']
        ext = get_ext(self._url)
        self.filename = format_filename(self.title, info['id'], ext)
        return self._url
