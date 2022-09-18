import downloader
import ree as re
from utils import Session, LazyUrl, Soup, Downloader, try_n, get_print, clean_title, print_error, urljoin, get_imgs_already, check_alive
from time import sleep
from translator import tr_
import page_selector
import json
import clf2
from ratelimit import limits, sleep_and_retry


class Page:

    def __init__(self, id_, title):
        self.id_ = id_
        self.title = title
        self.url = 'https://page.kakao.com/viewer?productId={}'.format(id_)


class Image:

    def __init__(self, url, page, p):
        self._url = url
        self.url = LazyUrl('https://page.kakao.com/', self.get, self)
        ext = '.jpg'
        self.filename = '{}/{:04}{}'.format(clean_title(page.title), p, ext)

    @sleep_and_retry
    @limits(5, 1)
    def get(self, _):
        return self._url



class Downloader_kakaopage(Downloader):
    type = 'kakaopage'
    URLS = ['page.kakao.com/home']
    MAX_CORE = 4
    MAX_SPEED = 4.0
    display_name = 'KakaoPage'
    ACCEPT_COOKIES = [r'(.*\.)?kakao\.com']

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        id = re.find('/home/.+?/([0-9]+)', url)
        if id is not None:
            url = id
        if url.isdecimal():
            url = 'https://page.kakao.com/home?seriesId={}'.format(url)
        return url

    def read(self):
        info = get_info(self.url, self.session, cw=self.cw)

        for img in info['imgs']:
            if isinstance(img, Image):
                img = img.url
            self.urls.append(img)

        self.artist = info['artist']

        self.title = info['title']



def get_id(url):
    id_ = re.find('seriesId=([0-9]+)', url, err='No seriesId')
    return id_



def get_pages(url, session, cw=None):
    id_ = get_id(url)

    pages = []
    ids = set()
    for p in range(500): #2966
        check_alive(cw)
        url_api = 'https://api2-page.kakao.com/api/v5/store/singles'
        data = {
            'seriesid': id_,
            'page': str(p),
            'direction': 'asc',
            'page_size': '20',
            'without_hidden': 'true',
            }
        r = session.post(url_api, data=data, headers={'Referer': url})
        print(p, r)
        data = r.json()

        singles = data['singles']
        if not singles:
            print('no singles')
            break

        for single in singles:
            title_page = single['title']
            id_page = single['id']
            if id_page in ids:
                print('dup id')
                continue
            ids.add(id_page)
            page = Page(id_page, title_page)
            pages.append(page)
        sleep(.5)
    return pages


def read_html(url, session):
    res = clf2.solve(url, session=session)
    return res['html']


@try_n(2)
def get_imgs_page(page, session):
    html = read_html(page.url, session=session)
    did = re.find('"did" *: *"(.+?)"', html, err='no did')
    url_api = 'https://api2-page.kakao.com/api/v1/inven/get_download_data/web'
    data = {
        'productId': page.id_,
        'device_mgr_uid': 'Windows - Chrome',
        'device_model': 'Windows - Chrome',
        'deviceId': did,
        }
    print(data)
    r = session.post(url_api, data=data, headers={'Referer': page.url})
    data = r.json()
    if data['result_code']:
        raise Exception(data['message'])
    imgs = []
    for file in data['downloadData']['members']['files']:
        url = file['secureUrl']
        url = 'https://page-edge.kakao.com/sdownload/resource?kid=' + url #5176
        img = Image(url, page, len(imgs))
        imgs.append(img)
    return imgs


def get_info(url, session, cw=None):
    print_ = get_print(cw)
    pages = get_pages(url, session, cw)
    pages = page_selector.filter(pages, cw)
    if not pages:
        raise Exception('no pages')

    info = {}

    html = read_html(url, session=session)
    soup = Soup(html)

    __NEXT_DATA__ = soup.find('script', id='__NEXT_DATA__')
    if __NEXT_DATA__:
        data = json.loads(__NEXT_DATA__.string)
        tid = data['props']['initialState']['common']['constant']['tid']
        print_('tid: {}'.format(tid))
        session.cookies['_kptid'] = tid
        html = read_html(url, session=session)
        soup = Soup(html)

    title = soup.find('h2').text.strip()
    artist = soup.find('meta', {'name': 'author'})['content']
    for x in [' ,', ', ']:
        while x in artist:
            artist = artist.replace(x, ',')
    artist = artist.replace(',', ', ')
    info['artist'] = artist
    info['title_raw'] = title
    info['title'] = clean_title('[{}] {}'.format(artist, title))

    imgs = []

    for i, page in enumerate(pages):
        check_alive(cw)
        if cw is not None:
            cw.setTitle('{} {} / {}  ({} / {})'.format(tr_('읽는 중...'), info['title'], page.title, i + 1, len(pages)))

        #3463
        imgs_already = get_imgs_already('kakaopage', info['title'], page, cw)
        if imgs_already:
            imgs += imgs_already
            continue

        try:
            _imgs = get_imgs_page(page, session)
            e_msg = None
        except Exception as e:
            _imgs = []
            e_msg = print_error(e)[0]
        print_('{} {}'.format(page.title, len(_imgs)))
        if e_msg:
            print_(e_msg)

        imgs += _imgs
        sleep(.2)

    if not imgs:
        raise Exception('no imgs')

    info['imgs'] = imgs

    return info


@page_selector.register('kakaopage')
@try_n(4)
def f(url):
    if 'seriesId=' not in url:
        raise Exception(tr_('목록 주소를 입력해주세요'))
    pages = get_pages(url, Session())
    return pages
