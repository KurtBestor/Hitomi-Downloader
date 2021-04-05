import downloader
import ree as re
from io import BytesIO as IO
from error_printer import print_error
from utils import Downloader, LazyUrl, get_ext, format_filename, try_n
import ytdl



@Downloader.register
class Downloader_vimeo(Downloader):
    type = 'vimeo'
    URLS = ['vimeo.com']
    single = True
    
    def init(self):
        if 'vimeo.com' not in self.url.lower():
            self.url = u'https://vimeo.com/{}'.format(self.url)

    def read(self):
        video = Video(self.url)
        video.url()#

        self.urls.append(video.url)
        self.setIcon(video.thumb)

        self.enableSegment()

        self.title = video.title


class Video(object):
    _url = None
    
    def __init__(self, url):
        self.url = LazyUrl(url, self.get, self)

    @try_n(4)
    def get(self,  url):
        if self._url:
            return self._url
        
        ydl = ytdl.YoutubeDL()
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
        ext = get_ext(self._url)
        self.filename = format_filename(self.title, info['id'], ext)
        return self._url
