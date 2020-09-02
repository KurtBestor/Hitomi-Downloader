# uncompyle6 version 3.5.0
# Python bytecode 2.7 (62211)
# Decompiled from: Python 2.7.16 (v2.7.16:413a49145e, Mar  4 2019, 01:30:55) [MSC v.1500 32 bit (Intel)]
# Embedded file name: xvideo_downloader.pyo
# Compiled at: 2019-10-12 16:51:28
import downloader
from utils import Downloader, Soup, LazyUrl, urljoin, format_filename, clean_title
import os
from timee import sleep, clock
from io import BytesIO as IO
from constants import try_n
import ree as re
from m3u8_tools import playlist2stream


def get_id(url):
    url = url.lower()
    if '/prof-video-click/upload/' in url:
        return url.split('/prof-video-click/upload/')[1].split('/')[1]
    return re.findall('[0-9]+', url.split('xvideos.')[1].split('/')[1].split('?')[0].split('#')[0])[0]


class Video(object):

    def __init__(self, url, url_page, id, title, url_thumb):
        self._url = url
        self.url = LazyUrl(url_page, self.get, self)
        self.id = id
        self.title = title
        self.filename = format_filename(title, id, '.mp4')
        f = IO()
        self.url_thumb = url_thumb
        downloader.download(url_thumb, buffer=f)
        self.thumb = f

    def get(self, _):
        return self._url


def fix_url(url):
    return re.sub('xvideos[0-9]+\\.', 'xvideos.', url)


@Downloader.register
class Downloader_xvideo(Downloader):
    type = 'xvideo'
    URLS = ['regex:xvideos[0-9]*\\.com', 'regex:xvideos[0-9]*\\.in']
    single = True

    def init(self):
        self.url = self.url.replace('xvideo_', '')
        self.url = fix_url(self.url)
        if 'xvideos.' in self.url.lower():
            self.url = self.url.replace('http://', 'https://')
        else:
            self.url = ('https://www.xvideos.com/{}').format(self.url)

    def read(self):
        video = get_video(self.url)
        self.urls.append(video.url)
        self.setIcon(video.thumb)
        self.title = video.title
        

@try_n(4)
def get_video(url_page):
    id = get_id(url_page)
    html = downloader.read_html(url_page)
    soup = Soup(html, unescape=True)
    name = soup.find('title').text.replace('- XVIDEOS.COM', '').strip()
    print('name:', name)
    url = re.find('.setVideoHLS\\([\'"](.+?)[\'"]\\)', html)
    print(url)
    ext = os.path.splitext(url.split('?')[0])[1]
    if ext.lower() == '.m3u8':
        url = playlist2stream(url, n_thread=5)
    url_thumb = soup.find('meta', {'property': 'og:image'}).attrs['content']
    video = Video(url, url_page, id, name, url_thumb)
    return video

