#coding:utf8
import downloader
from utils import Soup, LazyUrl, urljoin, try_n, Downloader, get_print, clean_title, get_imgs_already, check_alive, fix_dup
import ree as re
from itertools import cycle
from io import BytesIO
import json
from timee import sleep
from translator import tr_
import page_selector
import os


# https://static.comic-walker.com/viewer/cw-viewer.min.js
def decode(s, hash):
    # generateKey
    key = int(hash[:16], 16)

    filter = [int((key>>i*8)%256) for i in range(8)][::-1] #
    s2 = bytes(x^y for x, y in zip(s, cycle(filter)))
    return s2


class Image:
    def __init__(self, src, hash, p, page):
        def f(_):
            f = BytesIO()
            downloader.download(src, referer=page.url, buffer=f)
            s = f.read()
            s2 = decode(s, hash)
            f.seek(0)
            f.write(s2)
            f.seek(0)
            return f
        self.url = LazyUrl(page.url, f, self)
        self.filename = '{}/{:04}.jpg'.format(page.title, p)


class Page:
    def __init__(self, url, title):
        self.url = url
        self.title = clean_title(title)



class Downloader_comicwalker(Downloader):
    type = 'comicwalker'
    URLS = ['comic-walker.com/contents/detail/', 'comic-walker.jp/contents/detail/']
    MAX_CORE = 4
    display_name = 'ComicWalker'
    _soup = None
    pages = None

    @property
    def soup(self):
        if self._soup is None:
            html = downloader.read_html(self.url)
            self._soup = Soup(html)
        return self._soup

    def read(self):
        cw = self.cw
        title = clean_title(get_title(self.soup, cw))

        self.imgs = get_imgs(self.url, self.soup, cw)

        for img in self.imgs:
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = title


def get_cid(url):
    return re.find('[?&]cid=([a-zA-Z0-9_]+)', url, err='no cid')


def get_imgs_page(page):
    cid = get_cid(page.url)
    url_api = 'https://ssl.seiga.nicovideo.jp/api/v1/comicwalker/episodes/{}/frames'.format(cid)

    html = downloader.read_html(url_api, referer=page.url)

    meta = json.loads(html)
    data = meta['data']
    imgs = []
    for item in data['result']:
        src = item['meta']['source_url']
        hash = item['meta']['drm_hash']
        if hash is None:
            continue
        img = Image(src, hash, len(imgs), page)
        imgs.append(img)

    return imgs


def get_pages(url, soup=None):
    if soup is None:
        html = downloader.read_html(url)
        soup = Soup(html)

    title0 = get_title(soup)

    titles = {}
    pages = []
    for item in soup.findAll('div', class_='acBacknumber-item-leftbox'):
        item = item.parent
        a = item.find('a')
        href = a.attrs['href']
        cid = get_cid(href)
        p = int(cid.split('_')[-2][-4:])
        title = a.attrs['title']
        if title.startswith(title0): #5928
            title = title[len(title0):].strip()
        title = f'{p:04} - {title}' #5929
        title = fix_dup(title, titles) #5929
        href = urljoin(url, href)
        page = Page(href, title)
        pages.append(page)

    return pages


def get_title(soup, cw=None):
    print_ = get_print(cw)
    for h1 in soup.findAll('h1'):
        title = h1.text.strip()
        if title:
            break
    else:
        raise Exception('no title')
    return title


@page_selector.register('comicwalker')
@try_n(4)
def f(url):
    if '/viewer/' in url:
        raise Exception(tr_('목록 주소를 입력해주세요'))
    pages = get_pages(url)
    return pages


def get_imgs(url, soup=None, cw=None):
    if soup is None:
        html = downloader.read_html(url)
        soup = Soup(html)

    title = clean_title(get_title(soup, cw))

    pages = get_pages(url, soup)
    pages = page_selector.filter(pages, cw)

    imgs = []
    for i, page in enumerate(pages):
        check_alive(cw)
        imgs_already = get_imgs_already('comicwalker', title, page, cw)
        if imgs_already:
            imgs += imgs_already
            continue

        if cw is not None:
            cw.setTitle('{} {} / {}  ({} / {})'.format(tr_('읽는 중...'), title, page.title, i+1, len(pages)))

        imgs += get_imgs_page(page)

    return imgs
