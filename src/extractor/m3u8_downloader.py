from utils import Downloader, LazyUrl, clean_title
from m3u8_tools import playlist2stream, M3u8_stream
import os


@Downloader.register
class Downloader_m3u8(Downloader):
    type = 'm3u8'
    URLS = ['.m3u8']
    single = True
    display_name = 'M3U8'
    
    def init(self):
        if '://' not in self.url:
            self.url = 'http://' + self.url

    def read(self):
        video = Video(self.url)

        self.urls.append(video.url)

        self.title = video.title


class Video(object):
    def __init__(self, url):
        try:
            m = playlist2stream(url)
        except:
            m = M3u8_stream(url)
        self.url = LazyUrl(url, lambda _: m, self)
        self.title = os.path.splitext(os.path.basename(url))[0]
        self.filename = clean_title(self.title, n=-4) + '.mp4'
