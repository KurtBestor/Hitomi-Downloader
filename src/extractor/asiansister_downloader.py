import downloader
from utils import Soup, urljoin, LazyUrl, Downloader, try_n, clean_title
from timee import sleep
import os
import ree as re


@Downloader.register
class Downloader_asiansister(Downloader):
    type = 'asiansister'
    URLS = ['asiansister.com']

    @try_n(4)
    def init(self):
        self.url = self.url.replace('asiansister_', '')
        html = downloader.read_html(self.url)
        self.soup = Soup(html)

    @property
    def name(self):
        return clean_title(self.soup.find('title').text.replace('- ASIANSISTER.COM', '').strip())

    def read(self):
        imgs = get_imgs(self.url, self.soup, self.name)

        for img in imgs:
            if img.type == 'video':
                self.single = True
            self.urls.append(img.url)

        self.title = self.name


class Image(object):
    def __init__(self, url, referer, p, type='image'):
        self.url = LazyUrl(referer, lambda x: url, self)
        ext = os.path.splitext(url.split('?')[0])[1]
        self.filename = u'{:04}{}'.format(p, ext)
        self.type = type


@try_n(4)
def get_imgs(url, soup=None, name=None):
    if soup is None:
        html = downloader.read_html(url)
        soup = Soup(html)

    view = soup.findAll('div', class_='rootContant')[:2][-1]

    v = view.find('video')
    if v:
        img = v.find('source').attrs['src']
        img =  urljoin(url, img)
        img = Image(img, url, 0, 'video')
        ext = os.path.splitext(img.url().split('?')[0])[1]
        img.filename = u'{}{}'.format(name, ext)
        return [img]

    imgs = []
    for img in view.findAll('img'):
        img = img.attrs['dataurl']
        img = urljoin(url, img)
        img = re.sub('/[a-z]+images/', '/images/', img).replace('_t.', '.')
        img = Image(img, url, len(imgs))
        imgs.append(img)

    return imgs
