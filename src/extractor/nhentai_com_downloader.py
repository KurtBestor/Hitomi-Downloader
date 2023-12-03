#coding:utf8
import downloader
import ree as re
from utils import urljoin, LazyUrl, Downloader, try_n, join
import os
import json



class Downloader_nhentai_com(Downloader):
    type = 'nhentai_com'
    URLS = [r'regex:https?://nhentai.com']
    MAX_CORE = 16
    display_name = 'nhentai.com'

    def init(self):
        self.info = get_info(self.url)
        self.url = self.info['url']

    @classmethod
    def key_id(cls, url):
        url = url.lower()
        return re.find(r'/comic/([^/?]+)', url) or url

    def read(self):
        info = self.info

        artist = join(info['artists'])
        self.artist = artist if info['artists'] else None
        group = join(info['groups'])
        lang = info['lang'] or 'N／A'
        series = info['seriess'][0] if info['seriess'] else 'N／A'
        title = self.format_title(info['type'], info['id'], info['title'], artist, group, series, lang)

        for img in info['imgs']:
            self.urls.append(img.url)

        self.title = title


@LazyUrl.register
class LazyUrl_nhentai_com(LazyUrl):
    type = 'nhentai_com'
    def dump(self):
        referer = self._url
        url = self.image.url_img
        return {
            'referer': referer,
            'url': url,
            'p': self.image.p,
            }
    @classmethod
    def load(cls, data):
        referer = data['referer']
        url = data['url']
        img = Image(referer, url, data['p'])
        return img.url


class Image:
    def __init__(self, url_page, url_img, p):
        self.p = p
        self.referer = url_page
        self.filename = os.path.basename(url_img)
        self.url_img = url_img
        self.url = LazyUrl_nhentai_com(url_page, lambda _: self.url_img, self)


@try_n(4)
def get_info(url):
    url = downloader.real_url(url)
    q = re.find(r'/comic/([^/?]+)', url)

    url_api = 'https://nhentai.com/api/comics/{}'.format(q)
    data_raw = downloader.read_html(url_api, url)
    data = json.loads(data_raw)

    url_api = 'https://nhentai.com/api/comics/{}/images'.format(q)
    data_raw = downloader.read_html(url_api, url)
    data_images = json.loads(data_raw)

    info = {}
    info['url'] = url

    info['id'] = int(data['id'])
    info['type'] = data['category']['name']
    info['title'] = data['title']
    info['artists'] = [x['name'] for x in data['artists']]
    info['groups'] = [x['name'] for x in data['groups']]
    info['seriess'] = [x['name'] for x in data['parodies']]
    info['lang'] = data['language']['name']

    imgs = []
    for img in data_images['images']:
        img = urljoin(url, img['source_url'])
        img = Image(url, img, len(imgs))
        imgs.append(img)
    info['imgs'] = imgs

    return info
