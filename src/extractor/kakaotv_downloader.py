import downloader
import ytdl
from utils import Downloader, try_n, LazyUrl, get_ext, format_filename
from io import BytesIO as IO



class Downloader_kakaotv(Downloader):
    type = 'kakaotv'
    URLS = ['tv.kakao']
    single = True
    display_name = 'KakaoTV'
    ACCEPT_COOKIES = [r'(.*\.)?kakao\.com']

    @classmethod
    def fix_url(cls, url):
        url = url.replace('.kakao.com/m/', '.kakao.com/')
        return url.split('?')[0].strip('/')

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
