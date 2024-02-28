import downloader
from io import BytesIO
from utils import Downloader, LazyUrl, get_ext, format_filename, try_n
import ytdl
from m3u8_tools import M3u8_stream



class Downloader_youporn(Downloader):
    type = 'youporn'
    single = True
    URLS = ['youporn.com']
    display_name = 'YouPorn'
    ACCEPT_COOKIES = [r'(.*\.)?youporn\.com']

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


class Video:
    @try_n(4)
    def __init__(self, url, cw=None):
        ydl = ytdl.YoutubeDL(cw=cw)
        info = ydl.extract_info(url)

        f = info['formats'][-1]
        url_video = f['url']

        ext = get_ext(url_video)
        if ext.lower() == '.m3u8': #6142
            ext = '.mp4'
            url_video = M3u8_stream(url_video, referer=url)

        self.url = LazyUrl(url, lambda _: url_video, self)

        self.url_thumb = info['thumbnails'][0]['url']
        self.thumb = BytesIO()
        downloader.download(self.url_thumb, buffer=self.thumb)
        self.title = info['title']
        self.filename = format_filename(self.title, info['id'], ext)
