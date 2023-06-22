import downloader, requests
from utils import Soup, urljoin, Session, LazyUrl, Downloader, try_n, get_imgs_already, clean_title, get_ext, get_print, check_alive, fix_dup
import ree as re, json, os
from translator import tr_
from timee import sleep
import page_selector, clf2
from hashlib import md5
from datetime import datetime
import errors
import utils
SALT = 'mAtW1X8SzGS880fsjEXlM73QpS1i4kUMBhyhdaYySk8nWz533nrEunaSplg63fzT'


class Image:

    def __init__(self, url, page, p):
        ext = get_ext(url)
        self.filename = '{}/{:04}{}'.format(page.title, p, ext)

        self.url = LazyUrl(page.url, lambda _: url, self)


class Page:

    def __init__(self, url, title):
        self.title = clean_title(title)
        self.url = url



class Downloader_pixiv_comic(Downloader):
    type = 'pixiv_comic'
    URLS = ['comic.pixiv.net/works', 'comic.pixiv.net/viewer/']
    _soup = None
    display_name = 'pixivコミック'
    ACCEPT_COOKIES = [r'(.*\.)?pixiv\.net']

    def init(self):
        if '/viewer/' in self.url:
            raise errors.Invalid(tr_('목록 주소를 입력해주세요: {}').format(self.url))

    @try_n(4) #5329
    def read(self):
        self.session = Session()
        def f(html):
            return '/viewer/stories/' in html #5498
        html = clf2.solve(self.url, session=self.session, cw=self.cw, f=f, timeout=30, show='fake')['html']
        soup = Soup(html)
        self.purge_cookies()

        title = soup.find('h1').text.strip()
        artist = get_artist(soup)
        if artist:
            self.artist = artist
        else:
            artist = 'N/A'
        self.dirFormat = self.dirFormat.replace('0:id', '').replace('id', '').replace('()', '').replace('[]', '').strip()
        self.print_(f'dirFormat: {self.dirFormat}')
        title = self.format_title('N/A', 'id', title, artist, 'N/A', 'N/A', 'Japanese')
        while '  ' in title:
            title = title.replace('  ', ' ')

        self.imgs = get_imgs(self.url, title, soup, self.session, cw=self.cw)
        for img in self.imgs:
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = title


def get_artist(soup):
    artist = soup.find('div', class_='works-author')
    if not artist:
        artist = soup.find('div', class_=lambda c: c and c.startswith('Header_author'))
    if artist:
        return artist.text.strip()
    html = soup.html.replace('\\"', utils.esc('"')) #4936
    artist = re.find(r'"author" *: *(".*?")', html) # 4389
    if artist:
        artist = json.loads(artist).replace(utils.esc('"'), '"')
    if not artist: #5278
        artist = soup.find(class_=lambda c: c and set(c.split(' ')) == set(['mt-4', 'typography-14', 'text-text2'])) #5662
        if artist:
            artist = artist.text.strip()
    return artist or None


def get_pages(soup, url, cw=None):
    print_ = get_print(cw)
    pages = []
    hrefs = set()
    titles = {}
    for a in soup.findAll(lambda tag: tag.name == 'a' and '/viewer/stories/' in tag.get('href', ''))[::-1]:
        href = urljoin(url, a.attrs['href'])
        print_(href)
        if href in hrefs:
            continue
        divs = a.div.findAll('div', recursive=False) #5158
        if not divs: #5158
            continue
        if len(divs) < 2:
            divs = divs[0].findAll('div', recursive=False) #4861
        if len(divs) < 2:
            continue
        right = divs[1]
        number = list(right.children)[0].text.strip() #5158
        title = list(right.children)[1].text.strip() #5158
        title = ' - '.join(x for x in [number, title] if x)
        cid = re.find(r'/viewer/stories/([0-9]+)', href, err='no cid')
        title = f'{cid} - {title}' #5929
        title = fix_dup(title, titles) #5929
        page = Page(href, title)
        pages.append(page)
        hrefs.add(href)
    if not pages:
        raise Exception('no pages')

    return pages


@page_selector.register('pixiv_comic')
@try_n(4)
def f(url):
    if '/viewer/' in url:
        raise Exception(tr_('목록 주소를 입력해주세요'))
    html = clf2.solve(url, show='fake')['html']
    soup = Soup(html)
    pages = get_pages(soup, url)
    return pages


def get_imgs(url, title, soup, session, cw=None):
    pages = get_pages(soup, url, cw)
    pages = page_selector.filter(pages, cw)
    imgs = []
    for i, page in enumerate(pages):
        check_alive(cw)
        imgs_already = get_imgs_already('pixiv_comic', title, page, cw)
        if imgs_already:
            imgs += imgs_already
            continue
        if cw is not None:
            cw.setTitle('{} {} / {}  ({} / {})'.format(tr_('읽는 중...'), title, page.title, i + 1, len(pages)))
        imgs += get_imgs_page(page, session)

    return imgs


@try_n(4)
def get_imgs_page(page, session):
    id = re.find('/viewer/.+?/([0-9]+)', page.url)
    url_api = f'https://comic.pixiv.net/api/app/episodes/{id}/read'
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
