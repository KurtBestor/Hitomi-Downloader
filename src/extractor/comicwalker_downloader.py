#coding:utf8
import downloader
from utils import urljoin, try_n, Downloader, get_print, clean_title, get_imgs_already, check_alive, fix_dup, File
import ree as re
from itertools import cycle
from io import BytesIO
from timee import sleep
from translator import tr_
import page_selector
import utils


# https://static.comic-walker.com/viewer/cw-viewer.min.js
def decode(s, hash):
    # generateKey
    key = int(hash[:16], 16)

    filter = [int((key>>i*8)%256) for i in range(8)][::-1] #
    s2 = bytes(x^y for x, y in zip(s, cycle(filter)))
    return s2


class File_comicwalker(File):
    type = 'comicwalker'
    format = 'title/page:04;'

    def get(self):
        f = BytesIO()
        downloader.download(self['src'], referer=self['referer'], buffer=f, customWidget=self.cw)
        s = f.read()
        s2 = decode(s, self['hash'])
        f.seek(0)
        f.write(s2)
        f.seek(0)
        return {'url': f}


class Page:
    def __init__(self, url, title):
        self.url = url
        self.title = clean_title(title)



class Downloader_comicwalker(Downloader):
    type = 'comicwalker'
    URLS = ['comic-walker.com/contents/detail/', 'comic-walker.jp/contents/detail/']
    MAX_CORE = 4
    display_name = 'ComicWalker'

    def read(self):
        soup = downloader.read_soup(self.url)
        title = clean_title(get_title(soup, self.cw))

        self.urls += get_imgs(self.url, soup, self.cw)

        self.title = title


def get_cid(url):
    return re.find('[?&]cid=([a-zA-Z0-9_]+)', url, err='no cid')


def get_imgs_page(page, cw):
    print_ = get_print(cw)
    cid = get_cid(page.url)
    print_(f'cid: {cid}')
    url_api = f'https://comicwalker-api.nicomanga.jp/api/v1/comicwalker/episodes/{cid}/frames' #6368

    meta = downloader.read_json(url_api, referer=page.url)

    data = meta['data']
    imgs = []
    for item in data['result']:
        src = item['meta']['source_url']
        hash = item['meta']['drm_hash']
        if hash is None:
            continue
        d = {
            'title': page.title,
            'page': len(imgs),
            }
        img = File_comicwalker({'src': src, 'hash': hash, 'referer': page.url, 'name': utils.format('comicwalker', d, '.jpg')})
        imgs.append(img)

    return imgs


def get_pages(url, soup=None):
    if soup is None:
        soup = downloader.read_soup(url)

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
    div = soup.find('div', class_='comicIndex-box') #6231
    if div is None:
        raise Exception('no title')
    return div.find('h1').text.strip()


@page_selector.register('comicwalker')
@try_n(4)
def f(url):
    if '/viewer/' in url:
        raise Exception(tr_('목록 주소를 입력해주세요'))
    pages = get_pages(url)
    return pages


def get_imgs(url, soup=None, cw=None):
    if soup is None:
        soup = downloader.read_soup(url)

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
            cw.setTitle(f'{tr_("읽는 중...")} {title} / {page.title}  ({i+1} / {len(pages)})')

        imgs += get_imgs_page(page, cw)

    return imgs
