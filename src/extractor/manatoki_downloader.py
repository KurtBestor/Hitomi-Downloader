import downloader
from utils import Soup, try_n, Downloader, urljoin, get_print, Session, clean_url, clean_title, get_outdir, size_folder, LazyUrl, get_ext, ID_DIR
import os
from translator import tr_
import page_selector
import utils
from time import sleep
import clf2
import ree as re
SKIP = True
ID_DIR.register('manatoki', ID_DIR.after_bracket)


class Image(object):
    def __init__(self, url, page, p):
        ext = get_ext(url)
        if ext.lower()[1:] not in ['jpg', 'jpeg', 'bmp', 'png', 'gif', 'webm', 'webp']:
            ext = '.jpg'
        self.filename = '{}/{:04}{}'.format(page.title, p, ext)
        self.url = LazyUrl(page.url, lambda _: url, self)


class Page(object):
    def __init__(self, title, url):
        self.title = clean_title(title)
        self.url = url


@Downloader.register
class Downloader_manatoki(Downloader):
    type = 'manatoki'
    URLS = [r'regex:(mana|new)toki[0-9]*\.(com|net)']
    MAX_CORE = 8
    
    def init(self):
        self.url = self.url.replace('manatoki_', '')
        self.session, self.soup, url = get_soup(self.url)
        self.url = self.fix_url(url)

    @classmethod
    def fix_url(cls, url):
        return url.split('?')[0]

    @classmethod
    def key_id(cls, url):
        return '/'.join(url.split('/')[3:5])

    @property
    def name(self):
        return get_title(self.soup)

    def read(self):
        list = self.soup.find('ul', class_='list-body')
        if list is None:
            return self.Invalid(tr_('목록 주소를 입력해주세요: {}').format(self.url))
        self.title = tr_('읽는 중... {}').format(self.name)
        self.artist = get_artist(self.soup)

        imgs = get_imgs(self.url, self.soup, self.session, self.customWidget)
        
        for img in imgs:
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = self.name


def get_title(soup):
    artist = get_artist(soup)
    title = soup.find('meta', {'name':'subject'})['content'].strip()
    title = '[{}] {}'.format(artist, title)
    return clean_title(title)


def get_artist(soup):
    view = soup.find('div', class_='view-title')
    text = view.text.replace('\n', '#')
    artist = re.find('작가[ #]*:[ #]*(.+?)#', text, default='N/A').strip()
    return artist


def get_soup(url):
    session = Session()
    res = clf2.solve(url, session=session)
    soup = Soup(res['html'])
    
    return session, soup, res['url']


def get_pages(url, soup):
    list = soup.find('ul', class_='list-body')
    pages = []
    for item in list.findAll('div', 'wr-subject'):
        for span in item.a.findAll('span'):
            span.decompose()
        title = item.a.text.strip()
        href = item.a.attrs['href']
        href = urljoin(url, href)
        page = Page(title, href)
        pages.append(page)
    return pages[::-1]


@page_selector.register('manatoki')
def f(url):
    session, soup, url = get_soup(url)
    list = soup.find('ul', class_='list-body')
    if list is None:
        raise Exception(tr_('목록 주소를 입력해주세요'))
    pages = get_pages(url, soup)
    return pages


def get_imgs(url, soup=None, session=None, cw=None):
    print_ = get_print(cw)
    
    if soup is None or session is None:
        session, soup = get_soup(url)

    pages = get_pages(url, soup)
    pages = page_selector.filter(pages, cw)

    title = get_title(soup)
    imgs = []
    for i, page in enumerate(pages):
        dir = os.path.join(get_outdir('manatoki'), title, page.title)
        print('test dir:', dir)
        if SKIP and size_folder(dir) > 0:
            print_('Skip: {}'.format(page.title))
            for p, img in enumerate(sorted(os.listdir(dir))):
                img = os.path.join(dir, img)
                imgs.append(img)
            continue
        
        imgs_ = get_imgs_page(page, url, session, cw)
        imgs += imgs_

        s = '{} {} / {}  ({} / {})'.format(tr_('읽는 중...'), title, page.title, i+1, len(pages))
        print_('{} {}'.format(page.title, len(imgs_)))
        if cw is not None:
            if not cw.alive:
                return
            cw.setTitle(s)
        else:
            print('read page... {}    ({})'.format(page.url, len(imgs)))

    return imgs


@try_n(4)
def get_imgs_page(page, referer, session, cw):
    #sleep(2)
    #html = downloader.read_html(page.url, referer, session=session)
    #soup = Soup(html)

    # 2183
    res = clf2.solve(page.url, session=session)
    soup = Soup(res['html'])
    
    views = soup.findAll('div', class_='view-content')
    
    imgs = []
    for view in views:
        if view is None:
            continue
        for img in view.findAll('img'):
            img = img.attrs.get('data-original') or img.attrs.get('content')
            if not img:
                continue
            img = urljoin(page.url, img)
            if '/img/cang' in img:
                continue
            if '/img/blank.gif' in img:
                continue
            img = Image(img, page, len(imgs))
            imgs.append(img)

    if not imgs:
        raise Exception('no imgs')

    return imgs
