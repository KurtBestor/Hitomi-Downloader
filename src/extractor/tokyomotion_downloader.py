#coding:utf8
import downloader
from utils import Soup, urljoin, Downloader, cut_pair, LazyUrl, clean_title
from timee import sleep
from translator import tr_
from io import BytesIO
import ree as re
import os



class Downloader_tokyomotion(Downloader):
    type = 'tokyomotion'
    URLS = ['tokyomotion.net']
    single = True
    _type = None
    display_name = 'TOKYO Motion'

    def init(self):
        html = downloader.read_html(self.url)
        self.soup = Soup(html)
        if '/album/' in self.url:
            self._type = 'album'
        else:
            self._type = 'video'

    @property
    def name(self):
        title = get_title(self.soup)
        return clean_title(title)

    def read(self):
        if self._type == 'video':
            video = get_video(self.url, self.soup)
            self.urls.append(video.url)
            self.setIcon(video.thumb)
        elif self._type == 'album':
            imgs = get_imgs(self.url)
            for img in imgs:
                self.urls.append(img.url)
            self.single = False
        else:
            raise NotImplementedError('Unknown type: {}'.format(self._type))

        self.title = self.name


class Video:
    def __init__(self, url, url_thumb, referer, filename):
        self.url = LazyUrl(referer, lambda x: url, self)
        self.url_thumb = url_thumb
        self.thumb = BytesIO()
        downloader.download(url_thumb, referer=referer, buffer=self.thumb)
        self.filename = filename


def get_title(soup):
    video = soup.find('video', id='vjsplayer')
    if video:
        title = soup.find('h3').text.strip()
    else:
        title = soup.find('title').text.split(' Album - ')[0].strip()
    return title


def get_video(url, soup=None):
    if soup is None:
        html = downloader.read_html(url)
        soup = Soup(html)

    video = soup.find('video', id='vjsplayer').find('source').attrs['src']
    url_thumb = soup.find('video', id='vjsplayer').attrs['poster']
    title = get_title(soup)
    filename = u'{}.mp4'.format(clean_title(title))
    video = Video(video, url_thumb, url, filename)
    return video


class Image:
    def __init__(self, url, referer):
        self.url = LazyUrl(referer, lambda x: url, self)
        self.filename = os.path.basename(url.split('?')[0])


def get_imgs(url):
    id = re.find('album/.*?([0-9]+)', url)
    print('id:', id)
    url = 'https://www.tokyomotion.net/album/slideshow/{}'.format(id)

    html = downloader.read_html(url)
    soup = Soup(html)

    imgs = []
    for a in soup.findAll('a', {'data-lightbox': 'slideshow-{}'.format(id)}):
        img = a.find('img').attrs['src']
        img = img.replace('/tmb/', '/')
        img = Image(img, url)
        imgs.append(img)

    return imgs
