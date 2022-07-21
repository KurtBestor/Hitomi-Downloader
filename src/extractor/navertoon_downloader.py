import downloader
from utils import Soup, urljoin, Downloader, LazyUrl, get_imgs_already, clean_title, get_ext, get_print, errors
from constants import try_n
import ree as re, os
from timee import sleep
import page_selector
from translator import tr_
import json


class Page(object):

    def __init__(self, url, title, p):
        self.url = url
        self.title = title
        self.p = p


class Image(object):

    def __init__(self, url, page, p):
        ext = get_ext(url)
        self.filename = (u'{}/{:04}{}').format(clean_title(page.title), p, ext)

        self.url = LazyUrl(page.url, lambda _: url, self)


class Info(object):

    def __init__(self, id, title, artist):
        self.id = id
        self.title = title
        self.artist = artist



class Downloader_navertoon(Downloader):
    type = 'navertoon'
    URLS = ['comic.naver.com']
    MAX_CORE = 8
    MAX_SPEED = 4.0
    display_name = 'Naver Webtoon'

    def init(self):
        self.__info, _ = get_pages(self.url, self.cw)

    @classmethod
    def fix_url(cls, url):
        url = re.sub(r'[?&]page=[0-9]+', '', re.sub(r'[?&]no=[0-9]+', '', url)).replace('m.comic.naver.', 'comic.naver.')
        url = url.replace('detail.nhn', 'list.nhn').replace('/detail?', '/list?')
        return url.rstrip('#')

    @property
    def name(self):
        id = self.__info.id
        title = self.__info.title
        artist = self.__info.artist
        title = self.format_title('N/A', id, title, artist, 'N/A', 'N/A', 'Korean', prefix='navertoon_')
        return clean_title(title)

    def read(self):
        self.title = tr_(u'\uc77d\ub294 \uc911... {}').format(self.name)
        imgs = get_imgs_all(self.url, self.name, cw=self.cw)
        for img in imgs:
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = self.name


def set_no(url, p):
    if '&no=' not in url:
        url = url + ('&no={}').format(p)
        return url
    url = re.sub('&no=[0-9]+', ('&no={}').format(p), url)
    return url


def get_id(url):
    return int(url.lower().split('titleid=')[1].split('&')[0])


def set_page(url, p):
    if '&page=' in url:
        url = re.sub('&page=[0-9]+', ('&page={}').format(p), url)
    else:
        url += ('&page={}').format(p)
    return url


@try_n(4)
def get_pages(url, cw=None):
    print_ = get_print(cw)
    url = Downloader_navertoon.fix_url(url).replace('comic.naver.', 'm.comic.naver.')
    id = get_id(url)
    print('id:', id)
    print(url)
    html = downloader.read_html(url)
    soup = Soup(html)
    if soup.find('button', class_='btn_check'):
        raise errors.LoginRequired()
    try:
        info = soup.find('div', class_='area_info')
        artist = info.find('span', class_='author').text.strip()
    except Exception as e:
        print(e)
        try:
            title = ('\n').join(soup.find('div', class_='title').text.strip().split('\n')[:-1]).strip()
        except:
            title = 'artist not found'

        raise Exception(title)

    print_('artist: {}'.format(artist))
    title = soup.find('meta', {'property': 'og:title'}).attrs['content']
    pages = []
    nos = set()
    for p in range(1, 100):
        if p == 1:
            url_page = url
        else:
            url_page = set_page(url, p)
            html = downloader.read_html(url_page)
        print('read page:', url_page)
        soup = Soup(html)
        view = soup.findAll('ul', class_='section_episode_list')[(-1)]
        for lst in view.findAll('li'):
            url_page = urljoin(url, lst.find('a').attrs['href'])
            if 'detail.nhn' not in url_page.lower() and 'detail?' not in url_page.lower(): #3540
                continue
            print_('url_page: {}'.format(url_page))
            text = lst.find('strong', class_='title').find('span', class_='name').text.strip()
            no = int(re.findall('[?&]no=([0-9]+)', url_page)[0])
            if no in nos:
                print('duplicate no: {}'.format(no))
                continue
            nos.add(no)
            text = '{:04} - {}'.format(no, text)
            page = Page(url_page, text, p)
            pages.append(page)

        btn_next = soup.find('a', class_='btn_next')
        if btn_next is None or btn_next.attrs['href'] == '#':
            print('end of page')
            break

    info = Info(id, title, artist)
    return (
     info, pages)


@page_selector.register('navertoon')
@try_n(4)
def f(url):
    url = Downloader_navertoon.fix_url(url)
    info, pages = get_pages(url)
    return pages


@try_n(6)
def get_imgs(page, cw=None):
    print_ = get_print(cw)
    html = downloader.read_html(page.url)
    soup = Soup(html)

    type_ = re.find('''webtoonType *: *['"](.+?)['"]''', html)
    print_('type: {}'.format(type_))

    imgs = []
    if type_ == 'DEFAULT': # https://m.comic.naver.com/webtoon/detail.nhn?titleId=715772
        view = soup.find('div', class_='toon_view_lst')
        for img in view.findAll('img'):
            img = img.attrs.get('data-src')
            if not img:
                continue
            img = urljoin(page.url, img)
            img = Image(img, page, len(imgs))
            imgs.append(img)
    elif type_ == 'CUTTOON': # https://m.comic.naver.com/webtoon/detail.nhn?titleId=752803
        view = soup.find('div', class_='swiper-wrapper')
        for div in view.findAll('div', class_='swiper-slide'):
            if div.parent != view:
                continue
            if div.find('div', class_='cut_viewer_last'):
                print('cut_viewer_last')
                continue
            if div.find('div', class_='cut_viewer_recomm'):
                print('cut_viewer_recomm')
                continue
            img = div.find('img')
            img = img.attrs['data-src']
            img = urljoin(page.url, img)
            img = Image(img, page, len(imgs))
            imgs.append(img)
    elif type_ == 'EFFECTTOON': #2313; https://m.comic.naver.com/webtoon/detail.nhn?titleId=670144
        img_base = re.find('''imageUrl *: *['"](.+?)['"]''', html) + '/'
        print('img_base:', img_base)
        url_api = re.find('''documentUrl *: *['"](.+?)['"]''', html)
        data_raw = downloader.read_html(url_api, page.url)
        data = json.loads(data_raw)
        for img in data['assets']['stillcut'].values(): # ordered in python3.7+
            img = urljoin(img_base, img)
            img = Image(img, page, len(imgs))
            imgs.append(img)
    else:
        _imgs = re.findall('sImageUrl *: *[\'"](.+?)[\'"]', html)
        if not _imgs:
            raise Exception('no imgs')
        for img in _imgs:
            img = urljoin(page.url, img)
            img = Image(img, page, len(imgs))
            imgs.append(img)

    return imgs


def get_imgs_all(url, title, cw=None):
    print_ = get_print(cw)
    info, pages = get_pages(url, cw)
    pages = page_selector.filter(pages, cw)
    imgs = []
    for p, page in enumerate(pages):
        imgs_already = get_imgs_already('navertoon', title, page, cw)
        if imgs_already:
            imgs += imgs_already
            continue
        imgs_new = get_imgs(page, cw)
        print_('{}: {}'.format(page.title, len(imgs_new)))
        imgs += imgs_new
        if cw is not None:
            cw.setTitle(tr_(u'\uc77d\ub294 \uc911... {} / {}  ({}/{})').format(title, page.title, p + 1, len(pages)))
            if not cw.alive:
                break

    return imgs
