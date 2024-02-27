#coding: utf8
import downloader
from m3u8_tools import M3u8_stream
from utils import Soup, Downloader, LazyUrl, get_print, try_n, check_alive, format_filename, json
from io import BytesIO
import base64
import webbrowser
import errors



class Downloader_avgle(Downloader):
    type = 'avgle'
    single = True
    URLS = ['avgle.com']
    ACCEPT_COOKIES = [r'(.*\.)?avgle\.com']

    def init(self):
        if not self.cw.data_:
            link = 'https://github.com/KurtBestor/Hitomi-Downloader/wiki/Chrome-Extension'
            webbrowser.open(link)
            raise errors.Invalid('No data; See: {}'.format(link))

    def read(self):
        video = get_video(self.url, cw=self.cw)
        self.urls.append(video.url)

        self.setIcon(video.thumb)

        self.title = video.title


@try_n(2)
def get_video(url, cw=None):
    print_ = get_print(cw)

    check_alive(cw)

    data = cw.data_
    version = data['version']
    print_('version: {}'.format(version))
    if version == '0.1':
        raise errors.OutdatedExtension()
    data = data['data']
    if not isinstance(data, bytes):
        data = data.encode('utf8')
    s = base64.b64decode(data).decode('utf8')
    urls = json.loads(s)

    print_('\n'.join(urls[:4]))

    referer_seg = 'auto' if 'referer=force' in urls[0] else None # 1718

    stream = M3u8_stream(url, urls=urls, n_thread=4, referer_seg=referer_seg)

    html = downloader.read_html(url)
    soup = Soup(html)

    url_thumb = soup.find('meta', {'property': 'og:image'}).attrs['content']
    title = soup.find('meta', {'property': 'og:title'}).attrs['content'].strip()

    video = Video(stream, url_thumb, url, title)

    return video


class Video:
    def __init__(self, url, url_thumb, referer, title):
        self.url = LazyUrl(referer, lambda x: url, self)
        self.url_thumb = url_thumb
        self.thumb = BytesIO()
        downloader.download(url_thumb, referer=referer, buffer=self.thumb)
        self.title = title
        self.filename = format_filename(title, '', '.mp4')
