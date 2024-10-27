import downloader
from io import BytesIO as IO
from utils import Downloader, LazyUrl, get_ext, format_filename, try_n, get_print
import ytdl



class Downloader_vimeo(Downloader):
    type = 'vimeo'
    URLS = ['vimeo.com']
    single = True
    ACCEPT_COOKIES = [r'(.*\.)?vimeo\.com']

    def init(self):
        if 'vimeo.com' not in self.url.lower():
            self.url = 'https://vimeo.com/{}'.format(self.url)

    def read(self):
        video = Video(self.url, cw=self.cw)
        video.url()#

        self.urls.append(video.url)
        self.setIcon(video.thumb)

        self.enableSegment()

        self.title = video.title
        self.artist = video.artist


def format_(f):
    if f is None:
        return 'None'
    return 'format:{} - resolution:{} - vbr:{} - abr:{} - url:{}'.format(f['format'], f['resolution'], f['vbr'], f['abr'], f['url'])


class Video:
    _url = None

    def __init__(self, url, cw=None):
        self.url = LazyUrl(url, self.get, self)
        self.cw = cw

    @try_n(4)
    def get(self,  url):
        if self._url:
            return self._url
        print_ = get_print(self.cw)

        ydl = ytdl.YoutubeDL(cw=self.cw)
        info = ydl.extract_info(url)
        for f in info['formats']:
            print_(format_(f))
        fs = [f for f in info['formats'] if f['protocol'] in ['http', 'https']]
        fs = sorted(fs, key=lambda f: int(f.get('width', 0)), reverse=True)
        if not fs:
            raise Exception('No MP4 videos')
        f = fs[0]

        self.thumb_url = info['thumbnails'][0]['url']
        self.thumb = IO()
        downloader.download(self.thumb_url, buffer=self.thumb)
        self.title = info['title']
        url_video = f['url']
        ext = get_ext(url) or '.mp4'
        self.artist = info['uploader']
        self.filename = format_filename(self.title, info['id'], ext, artist=self.artist) #7127
        self._url = url_video
        return self._url
