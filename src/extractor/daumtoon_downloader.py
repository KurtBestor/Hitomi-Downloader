import downloader
from utils import Soup, Session, LazyUrl, Downloader, try_n, get_imgs_already, clean_title, get_print, check_alive
import json, os
from timee import time, sleep
import ree as re
from translator import tr_
import page_selector


class NotPaidError(Exception): pass


class Page(object):

    def __init__(self, id, url, title, serviceType):
        self.id = id
        self.url = url
        self.title = title
        self.serviceType = serviceType


class Image(object):

    def __init__(self, url, page, p):
        self._url = url
        self.url = LazyUrl(page.url, self.get, self)
        ext = os.path.splitext(url.split('?')[0])[1]
        if ext.lower()[1:] not in ('jpg', 'jpeg', 'bmp', 'png', 'gif', 'webm', 'webp'):
            ext = '.jpg'
        self.filename = '{}/{:04}{}'.format(clean_title(page.title), p, ext)

    def get(self, _):
        return self._url


def get_id(url):
    if '/league/' in url:
        header = 'league_'
    else:
        header = ''
    body = re.find('/viewer/([0-9a-zA-Z_-]+)', url) or re.find('/view/([0-9a-zA-Z_-]+)', url)
    return header, body


def header_to_type(header):
    if header == 'league_':
        return 'leaguetoon'
    return 'webtoon'


def get_info(url, session):
    referer = url
    header, id = get_id(referer)
    type_ = header_to_type(header)

    info = {}
    ids = set()
    pages = []
    for p in range(1, 1+10):
        if p == 1:
            url = 'http://webtoon.daum.net/data/pc/{}/view/{}?timeStamp={}'.format(type_, id, int(time()))
        else:
            if type_ == 'webtoon':
                break
            url = 'http://webtoon.daum.net/data/pc/{}/view/{}?page_no={}&timeStamp={}'.format(type_, id, p, int(time()))
        print(url)
        info_raw = downloader.read_html(url, referer=referer, session=session)
        _info = json.loads(info_raw)
        webtoon = _info['data'].get('webtoon') or _info['data'].get('leaguetoon')
        if webtoon is None:
            raise Exception('No webtoon')

        if p == 1:
            info['title'] = webtoon['title']
            artists = []
            for artist in webtoon['cartoon']['artists']:
                artist = artist['penName']
                if artist in artists:
                    continue
                artists.append(artist)

            if len(artists) > 1:
                artists = [
                 artists[1], artists[0]] + artists[2:]
            info['artists'] = artists

        eps = webtoon.get('webtoonEpisodes') or webtoon.get('leaguetoonEpisodes')
        if not eps:
            if p > 1:
                eps = []
            else:
                raise Exception('No eps')
        c = 0
        for ep in eps:
            id_ = ep.get('articleId') or ep.get('id')
            title = ep['title']
            serviceType = 'free' if type_ =='leaguetoon' else ep['serviceType']
            if type_ == 'leaguetoon':
                url = 'http://webtoon.daum.net/league/viewer/{}'.format(id_)
            else:
                url = 'http://webtoon.daum.net/webtoon/viewer/{}'.format(id_)
            if id_ in ids:
                continue
            c += 1
            ids.add(id_)
            page = Page(id_, url, title, serviceType)
            pages.append(page)
        if c == 0:
            print('c == 0; break')
            break

    info['pages'] = sorted(pages, key=lambda x: x.id)
    return info


@Downloader.register
class Downloader_daumtoon(Downloader):
    type = 'daumtoon'
    URLS = ['webtoon.daum.net']
    MAX_CORE = 16
    MAX_SPEED = 4.0
    display_name = 'Daum Webtoon'

    def init(self):
        if '/viewer/' in self.url:
            return self.Invalid(tr_('목록 주소를 입력해주세요: {}').format(self.url))
        if '/view/' not in self.url and not self.url.lower().startswith('http'):
            self.url = 'http://webtoon.daum.net/webtoon/view/{}'.format(self.url)
        self.session = None
        self._info = get_info(self.url, self.session)

    @property
    def name(self):
        title = self._info['title']
        artists = self._info['artists']
        artist = artists[0] if artists else 'N/A'
        title = self.format_title('N/A', ''.join(get_id(self.url)), title, artist, 'N/A', 'N/A', 'Korean', prefix='daumtoon_')
        return clean_title(title)

    def read(self):
        self.title = tr_(u'\uc77d\ub294 \uc911... {}').format(self.name)
        imgs = get_imgs_all(self._info, self.name, self.session, cw=self.cw)
        for img in imgs:
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = self.name
        self.session = None


def get_imgs(page, session, cw):
    print_ = get_print(cw)
    
    if not downloader.cookiejar.get('PROF', domain='.daum.net') and page.serviceType != 'free': #3314
        raise NotPaidError()
        
    html = downloader.read_html(page.url, session=session)
    header, id = get_id(page.url)
    t = int(time())
    soup = Soup(html)
    type_ = header_to_type(header)

    url_data = 'http://webtoon.daum.net/data/pc/{}/viewer/{}?timeStamp={}'.format(type_, id, t)
    data_raw = downloader.read_html(url_data, session=session, referer=page.url)
    data = json.loads(data_raw)
    if header == 'league_':
        m_type = None
    else:
        m_type = data['data']['webtoonEpisode']['multiType']
    print_('m_type: {}'.format(m_type))
    
    if m_type == 'chatting':
        page.url = page.url.replace('daum.net/', 'daum.net/m/')
        url_data = 'http://webtoon.daum.net/data/mobile/{}/viewer?id={}&{}'.format(type_, id, t)
        data_raw = downloader.read_html(url_data, session=session, referer=page.url)
        data = json.loads(data_raw)
        imgs = []
        for chat in data['data']['webtoonEpisodeChattings']:
            img = chat.get('image')
            if not img:
                continue
            img = Image(img['url'], page, len(imgs))
            imgs.append(img)
    else:
        url_data = 'http://webtoon.daum.net/data/pc/{}/viewer_images/{}?timeStamp={}'.format(type_, id, t)
        data_raw = downloader.read_html(url_data, session=session, referer=page.url)
        data = json.loads(data_raw)
        if not data.get('data'):
            raise NotPaidError()
        imgs = []
        for img in data['data']:
            img = Image(img['url'], page, len(imgs))
            imgs.append(img)

    return imgs


def get_imgs_all(info, title, session, cw=None):
    print_ = get_print(cw)
    pages = info['pages']
    pages = page_selector.filter(pages, cw)
    imgs = []
    for p, page in enumerate(pages):
        imgs_already = get_imgs_already('daumtoon', title, page, cw)
        if imgs_already:
            imgs += imgs_already
            continue
        try:
            imgs += get_imgs(page, session, cw)
        except NotPaidError:
            print_('Not paid: {}'.format(page.title)) #3314
            continue
        if cw is not None:
            cw.setTitle(tr_(u'\uc77d\ub294 \uc911... {} / {}  ({}/{})').format(title, page.title, p + 1, len(pages)))
        check_alive(cw)

    return imgs


@page_selector.register('daumtoon')
@try_n(4)
def f(url):
    info = get_info(url, None)
    return info['pages']

