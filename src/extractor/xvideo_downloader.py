import downloader
from utils import Downloader, Soup, LazyUrl, urljoin, format_filename, Session, get_ext, get_print, get_max_range, html_unescape
from io import BytesIO
from constants import try_n
import ree as re
from m3u8_tools import playlist2stream
from translator import tr_
import json
from timee import sleep
from ratelimit import limits, sleep_and_retry
CHANNEL_PATTERN = r'/(profiles|[^/]*channels)/([0-9a-zA-Z_-]+)'


def get_id(url):
    url = url.lower()
    if '/prof-video-click/' in url:
        return url.split('/prof-video-click/')[1].split('/')[2]
    return re.find(r'xvideos[0-9]*\.[^/]+/video([0-9]+)', url, err='no id')


class Video(object):
    _url = None

    def __init__(self, url_page):
        url_page = Downloader_xvideo.fix_url(url_page)
        self.url = LazyUrl(url_page, self.get, self)

    def get(self, url_page):
        if not self._url:
            self._get(url_page)
        return self._url

    @try_n(4)
    @sleep_and_retry
    @limits(1, 2)
    def _get(self, url_page):
        id = get_id(url_page)
        html = downloader.read_html(url_page)
        soup = Soup(html)
        self.title = html_unescape(soup.find('title').text).replace('- XVIDEOS.COM', '').strip()
        url = re.find(r'''.setVideoHLS\(['"](.+?)['"]\)''', html) or re.find(r'''.setVideoUrlLow\(['"](.+?)['"]\)''', html) #https://www.xvideos.com/video65390539/party_night
        if not url:
            raise Exception('no video url')
        ext = get_ext(url)
        if ext.lower() == '.m3u8':
            url = playlist2stream(url, n_thread=5)
        self.url_thumb = soup.find('meta', {'property': 'og:image'}).attrs['content']
        self.filename = format_filename(self.title, id, '.mp4')
        self._url= url

    @property
    def thumb(self):
        self.url()
        f = BytesIO()
        downloader.download(self.url_thumb, buffer=f)
        return f



@Downloader.register
class Downloader_xvideo(Downloader):
    type = 'xvideo'
    URLS = [r'regex:[./]xvideos[0-9]*\.(com|in|es)']
    single = True
    display_name = 'XVideos'

    def init(self):
        if 'xvideos.' in self.url.lower():
            self.url = self.url.replace('http://', 'https://')
        else:
            self.url = 'https://www.xvideos.com/{}'.format(self.url)

    @classmethod
    def fix_url(cls, url):
        url = re.sub(r'[^/]*xvideos[0-9]*\.[^/]+', 'www.xvideos.com', url).replace('http://', 'https://')
        url = url.replace('/THUMBNUM/', '/')
        return url

    @classmethod
    def key_id(cls, url):
        res = re.find(CHANNEL_PATTERN, url)
        if res:
            return '_'.join(res)
        return url

    def read(self):
        res = re.find(CHANNEL_PATTERN, self.url)
        if res:
            header, username = res
            info = read_channel(self.url, self.cw)
            videos = [Video(url) for url in info['urls']]
            video = self.process_playlist('[Channel] {}'.format(info['name']), videos)
        else:
            video = Video(self.url)
            video.url()
            self.title = video.title
            self.urls.append(video.url)
            
        self.setIcon(video.thumb)


def read_channel(url_page, cw=None):
    print_ = get_print(cw)
    res = re.find(CHANNEL_PATTERN, url_page)
    if res is None:
        raise Exception('Not channel')
    header, username = res
    print(header, username)
    max_pid = get_max_range(cw)
    info = {}
    info['header'] = header
    info['username'] = username
    session = Session()
    urls = []
    ids = set()
    for p in range(100):
        url_api = urljoin(url_page, '/{}/{}/videos/best/{}'.format(header, username, p))
        print_(url_api)
        r = session.post(url_api)
        data = json.loads(r.text)
        
        videos = data.get('videos') #4530
        if not videos:
            print_('empty')
            break
        
        for video in videos:
            id_ = video['id']
            if id_ in ids:
                print_('duplicate: {}'.format(id_))
                continue
            ids.add(id_)
            info['name'] = video['pn']
            urls.append(urljoin(url_page, video['u']))
        
        if len(urls) >= max_pid:
            break

        n = data['nb_videos']
        
        s = '{} {} - {}'.format(tr_('읽는 중...'), info['name'], len(urls))
        if cw:
            cw.setTitle(s)
        else:
            print(s)
        if len(ids) >= n:
            break
        sleep(1, cw)
    if not urls:
        raise Exception('no videos')
    info['urls'] = urls[:max_pid]
    return info
