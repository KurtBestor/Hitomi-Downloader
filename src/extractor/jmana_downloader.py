import downloader
from utils import Soup, urljoin, Downloader, fix_title, Session, get_print, LazyUrl, clean_title, get_imgs_already, check_alive
import ree as re
from timee import sleep
from translator import tr_
import os
from constants import try_n, clean_url
import urllib, page_selector
import bs4
import clf2
PATTERN = r'jmana[0-9]*.*/(comic_list_title|book)\?book'
PATTERN_ALL = r'jmana[0-9]*.*/((comic_list_title|book|bookdetail)\?book|book_by_title\?title)' #6157
PATTERN_ID = '[?&]bookdetailid=([0-9]+)'


class Image:

    def __init__(self, url, page, p):
        self.url = LazyUrl(page.url, lambda _: url, self)
        ext = '.jpg'
        name = '{:04}{}'.format(p, ext)
        self.filename = '{}/{}'.format(page.title, name)


class Page:

    def __init__(self, title, url):
        self.title = clean_title(title)
        self.url = url
        self.id = int(re.find(PATTERN_ID, url))



class Downloader_jmana(Downloader):
    type = 'jmana'
    URLS = ['regex:'+PATTERN_ALL]
    MAX_CORE = 8
    _soup = None

    def init(self):
        self.url = clean_url(self.url)
        self.session = Session()
        if re.search(PATTERN_ID, self.url): #1799
            select = self.soup.find('select', class_='bookselect')
            for i, op in enumerate(select.findAll('option')[::-1]):
                if 'selected' in op.attrs:
                    break
            else:
                raise Exception('no selected option')
            for a in self.soup.findAll('a'):
                url = urljoin(self.url, a.get('href') or '')
                if re.search(PATTERN, url):
                    break
            else:
                raise Exception('list not found')
            self.url = self.fix_url(url)
            self._soup = None

            for i, page in enumerate(get_pages(self.url, self.soup, self.session)):
                if page.id == int(op['value']):
                    break
            else:
                raise Exception('can not find page')
            self.cw.range_p = [i]

    @classmethod
    def fix_url(cls, url):
        return url

    @property
    def soup(self):
        if self._soup is None:
            res = clf2.solve(self.url, session=self.session) #4070
            html = res['html']
            soup = Soup(html)
            self._soup = soup
        return self._soup

    @property
    def name(self):
        title = get_title(self.soup)
        artist = get_artist(self.soup)
        title = fix_title(self, title, artist)
        return title

    def read(self):
        title = self.name
        artist = get_artist(self.soup)
        self.artist = artist
        for img in get_imgs(self.url, title, self.session, soup=self.soup, cw=self.cw):
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = self.name



def get_title(soup):
    a = soup.find('a', class_='tit')
    if a:
        return a.text.strip()
    return re.find(r'제목 *: *(.+)', soup.find('a', class_='tit').text, err='no title')


def get_artist(soup):
    return re.find(r'작가 *: *(.+)', soup.text, default='').strip() or 'N/A'


@try_n(4, sleep=60)
def get_imgs_page(page, referer, session, cw=None):
    print_ = get_print(cw)
    sleep(5, cw) #2017
    html = downloader.read_html(page.url, referer, session=session)

    inserted = re.find(r'''var *inserted *= *['"](.*?)['"]''', html)
    print_('inserted: {}'.format(inserted))

    inserted = set(int(i) for i in inserted.split(',')) if inserted else set()

    soup = Soup(html)

    view = soup.find(class_='pdf-wrap')

    imgs = []
    for i, img in enumerate(child for child in view.children if isinstance(child, bs4.element.Tag)):
        src = img.get('data-src') or img.get('src') or ''

        if i in inserted:
            print_('remove: {}'.format(src))
            continue

        if not src:
            continue
        src = urljoin(page.url, src.strip())
        if '/adimg/' in src:
            print('adimg:', src)
            continue
        if '/notice' in src:
            print('notice:', src)
            continue

        img = Image(src, page, len(imgs))
        imgs.append(img)

    return imgs


def get_pages(url, soup, session):
    pages = []
    for inner in soup.findAll('div', class_='inner'):
        a = inner.find('a')
        if not a:
            continue
        href = a.attrs.get('href', '')
        if not re.search(PATTERN_ID, href):
            continue
        if a.find('img'):
            print('skip img', a.attrs.get('href'))
            continue
        href = urljoin(url, href)
        title_page = a.text
        page = Page(title_page, href)
        pages.append(page)

    pages = list(reversed(pages))
    return pages


@page_selector.register('jmana')
def f(url, win):
    if re.search(PATTERN_ID, url):
        raise Exception(tr_('목록 주소를 입력해주세요'))
    session = Session()
    res = clf2.solve(url, session=session, win=win) #4070
    soup = Soup(res['html'])
    pages = get_pages(url, soup, session)
    return pages


def get_imgs(url, title, session, soup=None, cw=None):
    print_ = get_print(cw)
    if soup is None:
        html = downloader.read_html(url, session=session)
        soup = Soup(html)
    pages = get_pages(url, soup, session)
    print_('pages: {}'.format(len(pages)))
    pages = page_selector.filter(pages, cw)
    imgs = []
    for i, page in enumerate(pages):
        check_alive(cw)
        imgs_already = get_imgs_already('jmana', title, page, cw)
        if imgs_already:
            imgs += imgs_already
            continue

        imgs += get_imgs_page(page, url, session, cw)
        if cw is not None:
            cw.setTitle('{} {} / {}  ({} / {})'.format(tr_('읽는 중...'), title, page.title, i + 1, len(pages)))

    if not imgs:
        raise Exception('no imgs')

    return imgs
