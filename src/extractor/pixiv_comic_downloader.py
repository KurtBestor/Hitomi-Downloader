import downloader, requests
from utils import Soup, urljoin, Session, LazyUrl, Downloader, try_n, get_imgs_already, clean_title, get_ext
import ree as re, json, os
from translator import tr_
from timee import sleep
import page_selector, clf2
from hashlib import md5
from datetime import datetime
import errors
SALT = 'mAtW1X8SzGS880fsjEXlM73QpS1i4kUMBhyhdaYySk8nWz533nrEunaSplg63fzT'


class Image(object):

    def __init__(self, url, page, p):
        ext = get_ext(url)
        self.filename = '{}/{:04}{}'.format(page.title, p, ext)

        self.url = LazyUrl(page.url, lambda _: url, self)


class Page(object):

    def __init__(self, url, title):
        self.title = clean_title(title)
        self.url = url


@Downloader.register
class Downloader_pixiv_comic(Downloader):
    type = 'pixiv_comic'
    URLS = ['comic.pixiv.net/works', 'comic.pixiv.net/viewer/']
    _soup = None
    display_name = 'pixivコミック'

    def init(self):
        if '/viewer/' in self.url:
            raise errors.Invalid(tr_('목록 주소를 입력해주세요: {}').format(self.url))

    @property
    def soup(self):
        if self._soup is None:
            self.session = Session()
            self._soup = get_soup(self.url, session=self.session, cw=self.cw)
        return self._soup

    @property
    def name(self):
        soup = self.soup
        title = soup.find('h1').text.strip()
        artist = get_artist(soup)
        if artist:
            self.artist = artist
        else:
            artist = 'N/A'
        self.dirFormat = self.dirFormat.replace('0:id', '').replace('id', '').replace('()', '').replace('[]', '').strip()
        self.print_('dirFormat: {}'.format(self.dirFormat))
        title = self.format_title('N/A', 'id', title, artist, 'N/A', 'N/A', 'Japanese')
        while '  ' in title:
            title = title.replace('  ', ' ')

        return title

    def read(self):
        name = self.name
        self.imgs = get_imgs(self.url, name, self.soup, self.session, cw=self.cw)
        for img in self.imgs:
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = name


def get_soup(url, session=None, cw=None):
    html = read_html(url, session=session, cw=cw)
    soup = Soup(html)
    return soup


def read_html(url, session=None, cw=None):
    r = clf2.solve(url, session=session, cw=cw)
    html = r['html']

    return html


def get_artist(soup):
    artist = soup.find('div', class_='works-author')
    if not artist:
        artist = soup.find('div', class_=lambda c: c and c.startswith('Header_author'))
    if artist:
        return artist.text.strip()
    else:
        artist = re.find(r'"author" *: *(".+?")', soup.html)
        if artist:
            return json.loads(artist)
        else:
            return 'N/A'


def get_pages(soup, url):
    pages = []
    hrefs = set()
    titles = set()
    for a in soup.findAll(lambda tag: tag.name == 'a' and '/viewer/stories/' in tag.get('href', ''))[::-1]:
        href = urljoin(url, a.attrs['href'])
        if href in hrefs:
            continue
        hrefs.add(href)
        divs = a.findAll('div', recursive=False)
        if len(divs) < 2:
            continue
        right = divs[1]
        number = right.findAll('span')[0].text.strip()
        title = right.findAll('span')[1].text.strip()
        title = ' - '.join(x for x in [number, title] if x)
        if title in titles:
            title0 = title
            i = 2
            while title in titles:
                title = title0 + ' ({})'.format(i)
                i += 1
        titles.add(title)
        page = Page(href, title)
        pages.append(page)
    if not pages:
        raise Exception('no pages')

    return pages


@page_selector.register('pixiv_comic')
@try_n(4)
def f(url):
    if '/viewer/' in url:
        raise Exception(tr_('목록 주소를 입력해주세요'))
    html = read_html(url)
    soup = Soup(html)
    pages = get_pages(soup, url)
    return pages


def get_imgs(url, title, soup=None, session=None, cw=None):
    if soup is None:
        soup = get_soup(url, cw=cw)
    if session is None:
        session = Session()
        html = read_html(url, session=session)
    pages = get_pages(soup, url)
    pages = page_selector.filter(pages, cw)
    imgs = []
    for i, page in enumerate(pages):
        imgs_already = get_imgs_already('pixiv_comic', title, page, cw)
        if imgs_already:
            imgs += imgs_already
            continue
        if cw is not None:
            if not cw.alive:
                return
            cw.setTitle((u'{} {} / {}  ({} / {})').format(tr_(u'\uc77d\ub294 \uc911...'), title, page.title, i + 1, len(pages)))
        imgs += get_imgs_page(page, session)

    return imgs


@try_n(4)
def get_imgs_page(page, session):
    id = re.find('/viewer/.+?/([0-9]+)', page.url)
    url_api = 'https://comic.pixiv.net/api/app/episodes/{}/read'.format(id)
    local_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00')
    headers = {
        'X-Client-Time': local_time,
        'X-Client-Hash': md5((local_time + SALT).encode('utf8')).hexdigest(),
        'X-Requested-With': 'pixivcomic',
        'referer': page.url,
        }
    r = session.get(url_api, headers=headers)
    r.raise_for_status()
    data_raw = r.text
    data = json.loads(data_raw)
    pages = data['data']['reading_episode']['pages']

    if not pages:
        raise Exception('No pages')
    
    imgs = []
    for p in pages:
        img = p['url']
        img = img.replace('webp%3Ajpeg', 'jpeg')
        img = Image(img, page, len(imgs))
        imgs.append(img)

    return imgs

