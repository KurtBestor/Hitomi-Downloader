#coding:utf8
import downloader
from utils import Soup, cut_pair, LazyUrl, Downloader, get_print, get_max_range, try_n, clean_title, check_alive, json
import os
from translator import tr_



class Downloader_bcy(Downloader):
    type = 'bcy'
    URLS = ['bcy.net/item/detail/', 'bcy.net/u/']
    MAX_CORE = 8
    display_name = '半次元'
    ACCEPT_COOKIES = [r'(.*\.)?bcy\.net']

    def init(self):
        self.html = downloader.read_html(self.url)
        self.info = get_info(self.url, self.html)

    @property
    def name(self):
        info = self.info
        if '/detail/' in self.url:
            title = '{} (bcy_{}) - {}'.format(clean_title(info['artist']), info['uid'], info['id'])
        else:
            title = '{} (bcy_{})'.format(clean_title(info['artist']), info['uid'])
        return title

    def read(self):
        imgs = get_imgs(self.url, self.html, cw=self.cw)

        for img in imgs:
            self.urls.append(img.url)

        self.title = self.name
        self.artist = self.info['artist']


def get_ssr_data(html):
    s = html.split('window.__ssr_data = JSON.parse("')[1].replace('\\"', '"')
    s = cut_pair(s).replace('"', '\\"')
    data = json.loads(json.loads('"{}"'.format(s)))
    return data


@try_n(2)
def get_imgs(url, html=None, cw=None):
    if '/detail/' not in url:
        return get_imgs_channel(url, html, cw)

    if html is None:
        html = downloader.read_html(url)

    data = get_ssr_data(html)

    multi = data['detail']['post_data']['multi']

    imgs = []

    for m in multi:
        path = m['original_path']
        img = json.loads('"{}"'.format(path))
        img = Image_single(img, url, len(imgs))
        imgs.append(img)

    return imgs


class Image_single:
    def __init__(self, url ,referer, p):
        self._url = url
        self.p = p
        self.url = LazyUrl(referer, self.get, self)

    def get(self, referer):
        ext = get_ext(self._url, referer)
        self.filename = '{:04}{}'.format(self.p, ext)
        return self._url


class Image:
    def __init__(self, url, referer, id, p):
        self.id = id
        self.p = p
        self._url = url
        self.url = LazyUrl(referer, self.get, self)

    def get(self, referer):
        ext = get_ext(self._url, referer)
        self.filename = '{}_p{}{}'.format(self.id, self.p, ext)
        return self._url


def get_ext(url, referer=None):
    ext = os.path.splitext(url.split('?')[0].replace('~noop.image', ''))[1]
    if ext in ['.image', '']:
        ext = downloader.get_ext(url, referer=referer)
    return ext


def get_info(url, html):
    soup = Soup(html)
    info = {}

    uname = soup.find('div', class_='user-name') or soup.find('p', class_='uname') or soup.find('div', class_='user-info-name')

    info['artist'] = uname.text.strip()

    j = get_ssr_data(html)

    if '/detail/' in url:
        info['uid'] = j['detail']['detail_user']['uid']
        info['id'] = j['detail']['post_data']['item_id']
    else:
        info['uid'] = j['homeInfo']['uid']

    return info


def get_imgs_channel(url, html=None, cw=None):
    print_ = get_print(cw)
    if html is None:
        html = downloader.read_html(url)
    info = get_info(url, html)

    # Range
    max_pid = get_max_range(cw)

    ids = set()
    imgs = []
    for p in range(1000):
        url_api = 'https://bcy.net/apiv3/user/selfPosts?uid={}'.format(info['uid'])
        if imgs:
            url_api += '&since={}'.format(imgs[-1].id)
        data_raw = downloader.read_html(url_api, url)
        data = json.loads(data_raw)['data']
        items = data['items']
        if not items:
            print('no items')
            break
        c = 0
        for item in items:
            check_alive(cw)
            id = item['item_detail']['item_id']
            if id in ids:
                print('duplicate')
                continue
            c += 1
            ids.add(id)
            url_single = 'https://bcy.net/item/detail/{}'.format(id)
            imgs_single = get_imgs(url_single, cw=cw)
            print_(str(id))
            for p, img in enumerate(imgs_single):
                img = Image(img._url, url_single, id, p)
                imgs.append(img)
            s = '{} {} - {}'.format(tr_('읽는 중...'), info['artist'], min(len(imgs), max_pid))
            if cw:
                cw.setTitle(s)
            else:
                print(s)

            if len(imgs) >= max_pid:
                break
        if not c:
            print('not c')
            break
        if len(imgs) >= max_pid:
            print('over max_pid:', max_pid)
            break
    return imgs[:max_pid]
