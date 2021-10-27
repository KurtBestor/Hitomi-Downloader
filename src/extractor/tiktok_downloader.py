from __future__ import division, print_function, unicode_literals
import downloader
import ree as re
from utils import urljoin, Soup, LazyUrl, Downloader, try_n, compatstr, get_print, clean_title, Session, get_max_range
import os
import json
import ast
from io import BytesIO
import random
import clf2
from translator import tr_
from timee import sleep
from error_printer import print_error
import devtools
HDR = {'User-Agent': downloader.hdr['User-Agent']}
PATTERN_VID = '/(v|video)/(?P<id>[0-9]+)'


def is_captcha(soup):
    return soup.find('div', class_="verify-wrap") is not None

    
@Downloader.register
class Downloader_tiktok(Downloader):
    type = 'tiktok'
    single = True
    URLS = ['tiktok.com']
    display_name = 'TikTok'
    
    def init(self):
        cw = self.cw
        self.session = Session()
        res = clf2.solve(self.url, self.session, cw)
        soup = Soup(res['html'])
        if is_captcha(soup):
            def f(html):
                return not is_captcha(Soup(html))
            clf2.solve(self.url, self.session, cw, show=True, f=f)

    @classmethod
    def fix_url(cls, url):
        url = url.split('?')[0].split('#')[0].strip('/')
        if 'tiktok.com' not in url.lower():
            url = 'https://www.tiktok.com/@{}'.format(url)
        return url
    
    def read(self):
        format = compatstr(self.ui_setting.youtubeFormat.currentText()).lower().strip()
        
        if re.search(PATTERN_VID, self.url) is None:
            info = read_channel(self.url, self.session, self.cw)
            items = info['items']
            videos = [Video('https://www.tiktok.com/@{}/video/{}'.format(info['uid'], item['id']), self.session, format) for item in items]
            title = '{} (tiktok_{})'.format(info['nickname'], info['uid'])
            video = self.process_playlist(title, videos)
        else:
            video = Video(self.url, self.session, format)
            video.url()
            self.urls.append(video.url)
            self.title = clean_title(video.title)

        self.setIcon(video.thumb)

        

class Video(object):
    _url = None
    
    def __init__(self, url, session, format='title (id)'):
        self.url = LazyUrl(url, self.get, self)
        self.session = session
        self.format = format

    @try_n(2)
    def get(self, url):
        if self._url:
            return self._url
        m = re.search(PATTERN_VID, url)
        id = m.group('id')
        ext = '.mp4'
        self.title = id#
        self.filename = '{}{}'.format(clean_title(self.title, n=-len(ext)), ext)

        html = downloader.read_html(url, session=self.session)
        soup = Soup(html)
        data = soup.find(id='__NEXT_DATA__')
        props = data.contents[0]
        data_encode = json.dumps(props)
        ast_le = ast.literal_eval(data_encode)
        data = json.loads(ast_le)

        #info = data['props']['pageProps']['videoData']['itemInfos']
        info = data['props']['pageProps']['itemInfo']['itemStruct']
        self._url = info['video']['downloadAddr']

        self.url_thumb = info['video']['cover']
        self.thumb = BytesIO()
        downloader.download(self.url_thumb, referer=url, buffer=self.thumb)

        return self._url


def read_channel(url, session, cw=None):
    print_ = get_print(cw)

    info = {}
    info['items'] = []

    ids = set()
    info['items'] = []
    sd = {
        'count_empty': 0,
        'shown': False,
        }

    max_pid = get_max_range(cw)
    
    def f(html, browser=None):
        soup = Soup(html)
        if is_captcha(soup):
            print('captcha')
            browser.show()
            sd['shown'] = True
        elif sd['shown']:
            browser.hide()
            sd['shown'] = False
        try:
            info['uid'] = soup.find('h2', class_='share-title').text.strip()
            info['nickname'] = soup.find('h1', class_='share-sub-title').text.strip()
        except Exception as e:
            print_(print_error(e)[0])
        c = 0
        ids_now = set()
        for div in soup.findAll('div', class_='video-feed-item'):
            a = div.find('a')
            if a is None:
                continue
            href = a['href']
            if not href:
                continue
            m = re.search(PATTERN_VID, href)
            if m is None:
                continue
            id_video = int(m.group('id'))
            ids_now.add(id_video)
            if id_video in ids:
                continue
            ids.add(id_video)
            info['items'].append({'id': id_video})
            c += 1

        print_('items: {}'.format(len(info['items'])))
        if len(info['items']) >= max_pid:
            info['items'] = info['items'][:max_pid]
            return True
        
        browser.runJavaScript('window.scrollTo(0, document.body.scrollHeight);')
        sleep(15, cw)
        
        if c or (ids_now and min(ids_now) > min(ids)):
            sd['count_empty'] = 0
        else:
            print_('empty')
            sd['count_empty'] += 1
        msg = '{}  {} (tiktok_{}) - {}'.format(tr_('읽는 중...'), info.get('nickname'), info.get('uid'), len(info['items']))
        if cw:
            if not cw.alive:
                raise Exception('cw dead')
            cw.setTitle(msg)
        else:
            print(msg)
        return sd['count_empty'] > 4
    res = clf2.solve(url, session, cw, f=f, timeout=1800, show=True, delay=0)

    if not info['items']:
        raise Exception('no items')

    return info
    


@try_n(2)
def read_channel_legacy(url, session, cw=None):
    print_ = get_print(cw)
    html = downloader.read_html(url, session=session, headers=HDR)
    uid = re.find('//user/profile/([0-9]+)', html, err='no uid')
    secUid = re.find('"secUid" *: *"([^"]+?)"', html, err='no secUid')
    verifyFp = ''.join(random.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for i in range(16))
    maxCursor = 0

    info = {}
    info['items'] = []
    ids = set()

    for i in range(100):
        url_api = 'https://t.tiktok.com/api/item_list/?count=30&id={uid}&type=1&secUid={secUid}&maxCursor={maxCursor}&minCursor=0&sourceType=8&appId=1180&region=US&language=en&verifyFp={verifyFp}'.format(uid=uid, secUid=secUid, verifyFp=verifyFp, maxCursor=maxCursor)
        
        js = 'window.byted_acrawler.sign({url:"{}"});'.replace('{}', url_api)
        print(js)
        for try_ in range(4):
            try:
                sign = devtools.eval_js(url, js, session)['output']
                break
            except Exception as e:
                print(e)
                e_ = e
        else:
            raise e_
        url_api += '&_signature=' + sign
        print_(url_api)

        data_raw = downloader.read_html(url_api, url, session=session, headers=HDR)
        data = json.loads(data_raw)
        
        items = []
        for item in data.get('items', []):
            id_video = item['id']
            if id_video in ids:
                print('duplicate:', id_video)
                continue
            ids.add(id_video)
            items.append(item)

        if not items:
            print('no items')
            break

        info['items'] += items
        
        if i == 0:
            info['uid'] = items[0]['author']['uniqueId']
            info['nickname'] = items[0]['author']['nickname']

        msg = '{}  {} (tiktok_{}) - {}'.format(tr_('읽는 중...'), info['nickname'], info['uid'], len(info['items']))
        if cw:
            if not cw.alive:
                break
            
            cw.setTitle(msg)
        else:
            print(msg)

        if not data['hasMore']:
            break
        maxCursor = data['maxCursor']

    if not info['items']:
        raise Exception('no items')

    return info
