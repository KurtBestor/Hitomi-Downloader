#coding:utf8
from __future__ import print_function
import downloader
from utils import Soup, cut_pair, LazyUrl, Downloader, get_print, get_max_range, try_n, clean_title
import json
import ree as re
import os
from translator import tr_


@Downloader.register
class Downloader_bcy(Downloader):
    type = 'bcy'
    URLS = ['bcy.net/item/detail/', 'bcy.net/u/']
    MAX_CORE = 8
    display_name = '半次元'
    
    def init(self):
        self.html = downloader.read_html(self.url)
        self.info = get_info(self.url, self.html)

    @property
    def name(self):
        info = self.info
        if '/detail/' in self.url:
            title = u'{} (bcy_{}) - {}'.format(clean_title(info['artist']), info['uid'], info['id'])
        else:
            title = u'{} (bcy_{})'.format(clean_title(info['artist']), info['uid'])
        return title

    def read(self):
        imgs = get_imgs(self.url, self.html, cw=self.customWidget)

        for img in imgs:
            self.urls.append(img.url)

        self.title = self.name
        self.artist = self.info['artist']


@try_n(2)
def get_imgs(url, html=None, cw=None):
    if '/detail/' not in url:
        return get_imgs_channel(url, html, cw)
    
    if html is None:
        html = downloader.read_html(url)

    s = cut_pair(html.split('window.__ssr_data = JSON.parse("')[1])
    s = json.loads(u'"{}"'.format(s))

    data = json.loads(s)

    multi = data['detail']['post_data']['multi']

    imgs = []

    for m in multi:
        path = m['original_path']
        img = json.loads(u'"{}"'.format(path))
        img = Image_single(img, url, len(imgs))
        imgs.append(img)

    return imgs


class Image_single(object):
    def __init__(self, url ,referer, p):
        self._url = url
        self.p = p
        self.url = LazyUrl(referer, self.get, self)

    def get(self, referer):
        ext = get_ext(self._url, referer)
        self.filename = '{:04}{}'.format(self.p, ext)
        return self._url


class Image(object):
    def __init__(self, url, referer, id, p):
        self.id = id
        self.p = p
        self._url = url
        self.url = LazyUrl(referer, self.get, self)

    def get(self, referer):
        ext = get_ext(self._url, referer)
        self.filename = u'{}_p{}{}'.format(self.id, self.p, ext)
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
    
    s = cut_pair(html.split('window.__ssr_data = JSON.parse("')[1])
    j = json.loads(json.loads(u'"{}"'.format(s)))
    
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
    max_pid = get_max_range(cw, 2000)
        
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
        for item in items:
            id = item['item_detail']['item_id']
            if id in ids:
                print('duplicate')
                continue
            ids.add(id)
            url_single = u'https://bcy.net/item/detail/{}'.format(id)
            imgs_single = get_imgs(url_single, cw=cw)
            print_(str(id))
            for p, img in enumerate(imgs_single):
                img = Image(img._url, url_single, id, p)
                imgs.append(img)
            s = u'{} {} - {}'.format(tr_(u'읽는 중...'), info['artist'], min(len(imgs), max_pid))
            if cw:
                if not cw.alive:
                    return
                cw.setTitle(s)
            else:
                print(s)

            if len(imgs) >= max_pid:
                break
        if len(imgs) >= max_pid:
            print('over max_pid:', max_pid)
            break
    return imgs[:max_pid]
    
