from __future__ import division, print_function, unicode_literals
import downloader
import ree as re
from utils import Soup, LazyUrl, Downloader, try_n, compatstr, get_print, clean_title, Session, get_max_range, format_filename
from io import BytesIO
import clf2
from translator import tr_
from timee import sleep
from error_printer import print_error
import ytdl
PATTERN_VID = '/(v|video)/(?P<id>[0-9]+)'
SHOW = True


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
        self.url = self.fix_url(res['url']) #4324
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
        self.filename = format_filename(self.title, id, ext)

        ydl = ytdl.YoutubeDL()
        info = ydl.extract_info(url)

        self._url = info['url']

        return self._url


def read_channel(url, session, cw=None):
    print_ = get_print(cw)

    info = {}
    info['items'] = []

    ids = set()
    info['items'] = []
    sd = {
        'count_empty': 0,
        'shown': SHOW,
        }

    max_pid = get_max_range(cw)
    
    def f(html, browser=None):
        soup = Soup(html)
        if is_captcha(soup):
            print('captcha')
            browser.show()
            sd['shown'] = True
        elif sd['shown'] and not SHOW:
            browser.hide()
            sd['shown'] = False
        try:
            st = soup.find('h2', class_='share-title')
            if st is None:
                st = soup.find('h2', class_=lambda c: c and 'ShareTitle' in c)
            info['uid'] = st.text.strip()
            st = soup.find('h1', class_='share-sub-title')
            if st is None:
                st = soup.find('h1', class_=lambda c: c and 'ShareSubTitle' in c)
            info['nickname'] = st.text.strip()
        except Exception as e:
            print_(print_error(e)[0])
        c = 0
        ids_now = set()
        items = soup.findAll('div', class_='video-feed-item') + soup.findAll('div', class_=lambda c: c and 'DivItemContainer' in c)
        for div in items:
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
    res = clf2.solve(url, session, cw, f=f, timeout=1800, show=SHOW, delay=0)

    if not info['items']:
        raise Exception('no items')

    return info
    
