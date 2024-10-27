#coding:utf8
from utils import Soup, urljoin, LazyUrl, Downloader, try_n, get_print, clean_title, get_ext, check_alive
from translator import tr_
import ree as re
import clf2#


class Image:
    def __init__(self, url, p, page, cw):
        self.cw = cw
        ext = get_ext(url)
        self.filename = '{:04}{}'.format(p, ext)
        if page.title is not None:
            self.filename = '{}/{}'.format(page.title, self.filename)
        self._url = url
        self.url = LazyUrl(page.url, self.get, self)

    def get(self, _):
        return self._url#'tmp://' + clf2.download(self._url, cw=self.cw)


class Page:
    def __init__(self, title, url, soup=None):
        self.title = clean_title(title)
        self.url = url
        self.soup = soup



class Downloader_mrm(Downloader):
    type = 'mrm'
    URLS = ['myreadingmanga.info']
    _soup = None
    MAX_CORE = 4
    display_name = 'MyReadingManga'
    ACCEPT_COOKIES = [r'(.*\.)?myreadingmanga\.info']

    def init(self):
        self.session = get_session(self.url, self.cw)

    @classmethod
    def fix_url(cls, url):
        return re.find('https?://myreadingmanga.info/[^/]+', url, err='err')

    @property
    def soup(self):
        if self._soup is None:
            for try_ in range(8):
                try:
                    html = read_html(self.url, session=self.session, cw=self.cw)
                    break
                except Exception as e:
                    e_ = e
                    self.print_(e)
            else:
                raise e_
            self._soup = Soup(html)
        return self._soup

    @property
    def name(self):
        title = get_title(self.soup)
        return title

    def read(self):
        self.title = '읽는 중... {}'.format(self.name)

        imgs = get_imgs(self.url, self.soup, self.session, self.cw)

        for img in imgs:
            self.urls.append(img.url)

        self.title = self.name


def get_title(soup):
    title = soup.find('h1', class_='entry-title').text.strip()
    title = fix_title(title)
    title = clean_title(title)
    return title


def get_imgs(url, soup=None, session=None, cw=None):
    if soup is None:
        html = read_html(url, session=session, cw=cw)
        soup = Soup(html)

    title = get_title(soup)

    pagination = soup.find('div', class_='pagination')

    if pagination is None:
        page = Page(None, url, soup)
        imgs = get_imgs_page(page, session=session, cw=cw)
    else:
        pages = get_pages(url, soup, session=session)
        imgs = []
        for i, page in enumerate(pages):
            check_alive(cw)
            s = '{} {} / {}  ({} / {})'.format(tr_('읽는 중...'), title, page.title, i+1, len(pages))
            if cw:
                cw.setTitle(s)
            else:
                print(s)

            imgs += get_imgs_page(page, session=session, cw=cw)

    if not imgs:
        raise Exception('no imgs')

    return imgs


def get_pages(url, soup=None, session=None):
    if soup is None:
        html = read_html(url, session=session, cw=None)
        soup = Soup(html)
    pagination = soup.find('div', class_='pagination')

    pages = []
    hrefs = set()
    for a in pagination.findAll('a'):
        href = a.attrs.get('href', '')
        href = urljoin(url, href)
        if not href.startswith(url):
            print('not match', href)
            continue
        while href.endswith('/'):
            href = href[:-1]
        if href in hrefs:
            print('duplicate', href)
            continue
        hrefs.add(href)
        text = a.text.strip()
        page = Page(text, href)
        pages.append(page)

    if url not in hrefs:
        page = Page('1', url, soup)
        pages.insert(0, page)

    return pages


@try_n(4)
def get_imgs_page(page, session=None, cw=None):
    url = page.url
    soup = page.soup
    if soup is None:
        html = read_html(url, session=session, cw=None)
        soup = Soup(html)
        page.soup = soup

    view = soup.find('div', class_='entry-content')

    imgs = []
    for img in view.findAll('img'):
        img = img.get('data-lazy-src') or img.get('data-src') or img['src'] #7125
        img = urljoin(url, img)
        img = Image(img, len(imgs), page, cw)
        imgs.append(img)
    print(page.title, len(imgs), page.url)

    return imgs


def fix_title(title):
    title = re.sub(r'\(?[^()]*?c\.[^() ]+\)?', '', title)
    while '  ' in title:
        title = title.replace('  ', ' ')
    return title


def read_html(url, session, cw):
##    html = downloader.read_html(url, session=session)
##    soup = Soup(html)
##
##    cf = soup.find('div', class_='cf-browser-verification')
##    if cf is None:
##        return html

    r = clf2.solve(url, cw=cw, session=session)

    return r['html']


@try_n(4)
def get_session(url, cw=None):
    print_ = get_print(cw)
##    html = downloader.read_html(url)
##    soup = Soup(html)
##
##    cf = soup.find('div', class_='cf-browser-verification')
##    if cf is None:
##        print_('no cf protection')
##        return None

    print_('cf protection')
    r = clf2.solve(url, cw=cw)
    session = r['session']

    return session
