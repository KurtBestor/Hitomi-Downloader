from utils import Downloader, LazyUrl, try_n, format_filename, get_ext
import ytdl
from io import BytesIO as IO
import downloader
import ree as re
PATTEN_IMAGIZER = r'coub-com-.+\.imagizer\.com'


def get_id(url):
    return re.find(r'/view/([0-9a-z]+)', url, err='no id')



class Downloader_coub(Downloader):
    type = 'coub'
    URLS = ['coub.com', r'regex:'+PATTEN_IMAGIZER]
    single = True
    ACCEPT_COOKIES = [r'(.*\.)?coub\.com']

    @classmethod
    def fix_url(cls, url):
        return re.sub(PATTEN_IMAGIZER, 'coub.com', url)

    @classmethod
    def key_id(cls, url):
        return get_id(url)

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
        self.url = LazyUrl(url, self.get, self, pp=self.pp)
        self.cw = cw

    @try_n(2)
    def get(self,  url):
        if self._url:
            return self._url

        ydl = ytdl.YoutubeDL(cw=self.cw)
        info = ydl.extract_info(url)
        fs = [f for f in info['formats'] if f['ext'] == 'mp4']
        f = sorted(fs, key=lambda f: int(f.get('filesize', 0)))[-1]
        self._url = f['url']
##        fs = [f for f in info['formats'] if f['ext'] == 'mp3']
##        self.f_audio = sorted(fs, key=lambda f: int(f.get('filesize', 0)))[-1]

        self.thumb_url = info['thumbnails'][0]['url']
        self.thumb = IO()
        downloader.download(self.thumb_url, buffer=self.thumb)
        self.title = info['title']
        ext = get_ext(self._url)
        self.filename = format_filename(self.title, info['id'], ext)
        return self._url

    def pp(self, filename):
##        import ffmpeg
##        f = IO()
##        downloader.download(self.f_audio['url'], buffer=f)
##        ffmpeg.merge(filename, f)
        return filename
