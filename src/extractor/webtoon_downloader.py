import downloader
from utils import Soup, LazyUrl, clean_title, get_ext, get_imgs_already, urljoin, try_n, Downloader
import os
import page_selector
from translator import tr_
import ree as re



@Downloader.register
class Downloader_webtoon(Downloader):
    type = 'webtoon'
    URLS = ['webtoon.com', 'webtoons.com']
    MAX_CORE = 8
    MAX_SPEED = 4.0
    display_name = 'WEBTOON'

    def init(self):
        self.url = get_main(self.url)
        self.soup = downloader.read_soup(self.url)

    @classmethod
    def fix_url(cls, url):
        return url.replace('webtoon.com', 'webtoons.com')

    def read(self):
        title = clean_title(self.soup.find('h1').text.strip())
        self.title = tr_(u'\uc77d\ub294 \uc911... {}').format(title)
        imgs = get_imgs_all(self.url, title, cw=self.cw)
        for img in imgs:
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = title
        

class Page(object):

    def __init__(self, url, title):
        self.url = url
        self.title = title


class Image(object):

    def __init__(self, url, page, p):
        ext = get_ext(url) or downloader.get_ext(url, referer=page.url)
        self.filename = '{}/{:04}{}'.format(clean_title(page.title), p, ext)

        self.url = LazyUrl(page.url, lambda _: url, self)
        

@try_n(2)
def get_imgs(page):
    html = downloader.read_html(page.url)
    if 'window.__motiontoonViewerState__' in html:
        raise NotImplementedError('motiontoon')
    soup = Soup(html)
    view = soup.find('div', class_='viewer_img')
    imgs = []
    for img in view.findAll('img'):
        src = img.get('data-url') or img['src']
        img = Image(urljoin(page.url, src), page, len(imgs))
        imgs.append(img)
    return imgs


def get_main(url):
    if 'episode_no=' in url:
        soup = downloader.read_soup(url)
        url = urljoin(url, soup.find('div', class_='subj_info').find('a')['href'])
    return url


def set_page(url, p):
    if '&page=' not in url:
        url = url + '&page={}'.format(p)
    else:
        url = re.sub('&page=[0-9]+', '&page={}'.format(p), url)
    if p == 1:
        url = url.replace('&page=1', '')
    return url


def get_pages(url):
    pages = []
    urls = set()
    for p in range(1, 101):
        url_page = set_page(url, p)
        print(url_page)
        for try_ in range(4):
            try:
                soup = downloader.read_soup(url_page)
                view = soup.find('ul', id='_listUl')
                if view is None:
                    raise Exception('no view')
                break
            except Exception as e:
                e_ = e
                print(e)
        else:
            raise e_
        pages_new = []
        for li in view.findAll('li', recursive=False):
            href = urljoin(url, li.find('a')['href'])
            title = li.find('span', class_='subj').text.strip()
            if href in urls:
                continue
            urls.add(href)
            no = int(li['data-episode-no'])
            title = '{:04} - {}'.format(no, title)
            page = Page(href, title)
            pages_new.append(page)
        if not pages_new:
            break
        pages += pages_new
    return pages[::-1]


@page_selector.register('webtoon')
@try_n(4)
def f(url):
    url = get_main(url)
    return get_pages(url)


def get_imgs_all(url, title, cw=None):
    pages = get_pages(url)
    pages = page_selector.filter(pages, cw)
    imgs = []
    for p, page in enumerate(pages):
        imgs_already = get_imgs_already('webtoon', title, page, cw)
        if imgs_already:
            imgs += imgs_already
            continue
        imgs += get_imgs(page)
        msg = tr_(u'\uc77d\ub294 \uc911... {} / {}  ({}/{})').format(title, page.title, p + 1, len(pages))
        if cw is not None:
            cw.setTitle(msg)
            if not cw.alive:
                break
        else:
            print(msg)

    return imgs
