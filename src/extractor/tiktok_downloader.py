import downloader
import ree as re
from utils import Soup, LazyUrl, Downloader, try_n, compatstr, get_print, Session, get_max_range, format_filename, json
import clf2
import ytdl
from urllib.parse import unquote
PATTERN_VID = '/(v|video)/(?P<id>[0-9]+)'
SHOW = True


def is_captcha(soup, cw=None):
    r = soup.find('div', class_="verify-wrap") or soup.find('div', class_='captcha_verify_container')
    if r:
        get_print(cw)('captcha')
    return r



class Downloader_tiktok(Downloader):
    type = 'tiktok'
    single = True
    URLS = ['tiktok.com', 'douyin.com']
    display_name = 'TikTok'
    ACCEPT_COOKIES = [r'(.*\.)?(tiktok|douyin)\.com']

    def init(self):
        cw = self.cw
        self.session = Session()
        res = clf2.solve(self.url, self.session, cw)
        soup = Soup(res['html'])
        if is_captcha(soup, cw):
            def f(html):
                return not is_captcha(Soup(html))
            res = clf2.solve(self.url, self.session, cw, show=True, f=f)
        self.url = self.fix_url(res['url']) #4324

    @classmethod
    def fix_url(cls, url):
        url = url.split('?')[0].split('#')[0].strip('/')
        if '://' not in url:
            url = 'https://www.tiktok.com/@{}'.format(url)
        return url

    def read(self):
        format = compatstr(self.ui_setting.youtubeFormat.currentText()).lower().strip()

        def parse_video_url(info, item):
            if 'url' in item:
                return item['url']
            if 'tiktok.com' in self.url.lower(): # TikTok
                return 'https://www.tiktok.com/@{}/video/{}'.format(info.get('uid', ''), item['id']) #5235
            else: # Douyin
                return 'https://www.douyin.com/video/{}'.format(item['id'])

        if re.search(PATTERN_VID, self.url): # single video
            video = Video(self.url, self.session, format, self.cw)
            video.url()
            self.urls.append(video.url)
            self.title = video.title
        elif 'tiktok.com/tag/' in self.url or 'douyin.com/search/' in self.url: # tag search
            tag = re.find(r'/(tag|search)/([^/#\?]+)', self.url)[1]
            tag = unquote(tag)
            title = '#{}'.format(tag)
            info = read_channel(self.url, self.session, self.cw, title=title)
            items = info['items']
            videos = [Video(parse_video_url(info, item), self.session, format, self.cw) for item in items]
            video = self.process_playlist(title, videos)
        elif 'tiktok.com/@' in self.url or 'douyin.com/user/' in self.url: # channel
            info = read_channel(self.url, self.session, self.cw)
            items = info['items']
            videos = [Video(parse_video_url(info, item), self.session, format, self.cw) for item in items]
            title = '{} (tiktok_{})'.format(info['nickname'], info['uid'])
            video = self.process_playlist(title, videos)
        else:
            raise NotImplementedError()


class Video:
    _url = None

    def __init__(self, url, session, format, cw):
        self.url = LazyUrl(url, self.get, self)
        self.session = session
        self.format = format
        self.cw = cw

    @try_n(2)
    def get(self, url):
        if self._url:
            return self._url
        m = re.search(PATTERN_VID, url)
        id = m.group('id')

        ydl = ytdl.YoutubeDL(cw=self.cw)
        info = ydl.extract_info(url)

        ext = '.mp4'
        self.title = info['title']
        self.filename = format_filename(self.title, id, ext)

        self._url = info['url']

        return self._url


def read_channel(url, session, cw=None, title=None):
    info = {}
    info['items'] = []

    if 'tiktok.com' in url.lower(): # TikTok
        soup = downloader.read_soup(url, session=session, user_agent='facebookexternalhit/1.1')
        info['uid'] = re.find(r'/@([\w\.-]+)', soup.find('meta', {'property': 'og:url'})['content'], err='no uid')
        nick = soup.find('meta', {'property': 'og:title'})['content']
        if nick.endswith(' on TikTok'):
            nick = nick[:-len(' on TikTok')]
        info['nickname'] = nick
    else: # Douyin
        def f(html, browser=None):
            soup = Soup(html)
            if is_captcha(soup):
                browser.show()
                return False
            try:
                info['uid'] = re.find(r'''uniqueId%22%3A%22(.+?)%22''', html, err='no uid')
                info['nickname'] = json.loads(re.findall(r'''"name"\s*:\s*(".+?")''', html)[-1]) #5896
                return True
            except:
                return False
        clf2.solve(url, session, cw, f=f)

    options = {
        'extract_flat': True,
        'playlistend': get_max_range(cw),
        }
    ydl = ytdl.YoutubeDL(options, cw=cw)
    info_ = ydl.extract_info(url)

    for e in info_['entries']:
        info['items'].append({'url': e['webpage_url']})

    if not info['items']:
        raise Exception('no items')

    return info

