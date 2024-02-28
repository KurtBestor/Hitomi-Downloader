import downloader
from utils import Soup, Downloader, LazyUrl, format_filename
import ree as re
from m3u8_tools import playlist2stream
from io import BytesIO as IO



class Video:

    def __init__(self, url, url_page, title, url_thumb):
        self._url = url
        self.url = LazyUrl(url_page, self.get, self)
        self.id = get_id(url_page)
        self.title = title
        self.filename = format_filename(title, self.id, '.mp4')
        f = IO()
        self.url_thumb = url_thumb
        downloader.download(url_thumb, buffer=f)
        self.thumb = f

    def get(self, _):
        return self._url


def get_id(url):
    return url.split('xnxx.com/')[1].split('/')[0]



class Downloader_xnxx(Downloader):
    type = 'xnxx'
    URLS = [r'regex:xnxx[0-9]*\.(com|es)']
    single = True
    display_name = 'XNXX'
    ACCEPT_COOKIES = [r'(.*\.)?xnxx[0-9]*\.(com|es)']

    @classmethod
    def fix_url(cls, url):
        return re.sub(r'xnxx[0-9]*\.(com|es)', 'xnxx.com', url)

    def read(self):
        video = get_video(self.url)
        self.urls.append(video.url)
        self.setIcon(video.thumb)
        self.title = video.title


def get_video(url):
    html = downloader.read_html(url)
    soup = Soup(html)

    for script in soup.findAll('script'):
        script = script.text or script.string or ''
        hls = re.find(r'''html5player\.setVideoHLS\(['"](.+?)['"]''', script)
        if hls:
            break
    else:
        raise Exception('No VideoHLS')

    video = playlist2stream(hls)

    title = get_title(soup)

    url_thumb = soup.find('meta', {'property': 'og:image'}).attrs['content'].strip()

    video = Video(video, url, title, url_thumb)
    return video


def get_title(soup):
    return soup.find('meta', {'property': 'og:title'}).attrs['content'].strip()
