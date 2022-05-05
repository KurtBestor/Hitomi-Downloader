#coding:utf8
from __future__ import division, print_function, unicode_literals
import downloader
from utils import Soup, get_ext, LazyUrl, Downloader, try_n, clean_title, get_print
import ree as re
from translator import tr_
from timee import sleep
import errors


def setPage(url, p):
    url = url.split('?')[0]
    if p > 1:
        url += '?page={}'.format(p)
    return url


def getPage(url):
    p = re.find('page=([0-9]+)', url)
    return int(p or 1)


class Image(object):
    def __init__(self, url, referer, p):
        self.url = LazyUrl(referer, lambda x: url, self)
        ext = get_ext(url)
        self.filename = '{:04}{}'.format(p, ext)


@Downloader.register
class Downloader_v2ph(Downloader):
    type = 'v2ph'
    URLS = ['v2ph.com/album/']
    MAX_CORE = 4
    MAX_PARALLEL = 1
    display_name = 'V2PH'
    
    @classmethod
    def fix_url(cls, url):
        return url.split('?')[0]

    def read(self):
        info = get_info(self.url)
        
        for img in get_imgs(self.url, info['title'], self.cw):
            self.urls.append(img.url)

        self.title = clean_title(info['title'])



@try_n(2)
def get_info(url):
    html = downloader.read_html(url)
    soup = Soup(html)
    info = {}
    info['title'] = soup.find('h1').text.strip()
    return info


def get_imgs(url, title, cw=None):
    print_ = get_print(cw)
    imgs = []

    for p in range(1, 1001):
        url = setPage(url, p)
        print_(url)
        for try_ in range(4):
            try:
                html = downloader.read_html(url, user_agent=downloader.hdr['User-Agent'])
                #sleep(1)
                break
            except Exception as e:
                print(e)
        else:
            raise
        soup = Soup(html)

        view = soup.find('div', class_='photos-list')
        if view is None:
            if p == 1:
                raise errors.LoginRequired()
            else:
                break # Guest user
        for img in view.findAll('img'):
            img = img.attrs['data-src']
            img = Image(img, url, len(imgs))
            imgs.append(img)
        
        pgn = soup.find('ul', class_='pagination')
        ps = [getPage(a.attrs['href']) for a in pgn.findAll('a')] if pgn else []
        if not ps or p >= max(ps):
            print('max p')
            break

        msg =  '{} {}  ({} / {})'.format(tr_('읽는 중...'), title, p, max(ps))
        if cw:
            cw.setTitle(msg)
        else:
            print(msg)

    return imgs
    

