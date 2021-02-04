#coding: utf8
import downloader
import os
from m3u8_tools import M3u8_stream
from utils import Soup, Downloader, LazyUrl, get_print, try_n, clean_title
from io import BytesIO
import constants
from error_printer import print_error
import base64
import json
import webbrowser


@Downloader.register
class Downloader_avgle(Downloader):
    type = 'avgle'
    single = True
    URLS = ['avgle.com']

    def init(self):
        if not self.cw.data_:
            link = 'https://github.com/KurtBestor/Hitomi-Downloader/wiki/Chrome-Extension'
            webbrowser.open(link)
            return self.Invalid('No data; See: {}'.format(link))

    def read(self):
        video = get_video(self.url, cw=self.cw)
        self.urls.append(video.url)

        self.setIcon(video.thumb)
        
        self.title = video.title
        

@try_n(2)
def get_video(url, cw=None):
    print_ = get_print(cw)
    
    if cw and not cw.alive:
        return

    html = downloader.read_html(url)
    soup = Soup(html)

    data = cw.data_
    if not isinstance(data, bytes):
        data = data.encode('utf8')
    s = base64.b64decode(data).decode('utf8')
    urls = json.loads(s)

    print_(u'\n'.join(urls[:4]))

    referer_seg = 'auto' if 'referer=force' in urls[0] else None # 1718

    stream = M3u8_stream(url, urls=urls, n_thread=4, referer_seg=referer_seg)

    url_thumb = soup.find('meta', {'property': 'og:image'}).attrs['content']
    title = soup.find('meta', {'property': 'og:title'}).attrs['content'].strip()
    
    video = Video(stream, url_thumb, url, title)

    return video


class Video(object):
    def __init__(self, url, url_thumb, referer, title):
        self.url = LazyUrl(referer, lambda x: url, self)
        self.url_thumb = url_thumb
        self.thumb = BytesIO()
        downloader.download(url_thumb, referer=referer, buffer=self.thumb)
        self.title = title
        ext = '.mp4'
        self.filename = u'{}{}'.format(clean_title(title, n=-len(ext)), ext)
        

