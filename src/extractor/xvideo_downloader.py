import downloader
from utils import Downloader, Soup, LazyUrl, urljoin, format_filename, clean_title, Session, get_ext, get_print, get_max_range
from io import BytesIO
from constants import try_n
import ree as re
from m3u8_tools import playlist2stream
from translator import tr_
CHANNEL_PATTERN = r'/(profiles|[^/]*channels)/([0-9a-zA-Z_]+)'


def get_id(url):
    url = url.lower()
    if '/prof-video-click/' in url:
        return url.split('/prof-video-click/')[1].split('/')[2]
    return re.find(r'xvideos[0-9]*\.[^/]+/video([0-9]+)', url, err='no id')


class Video(object):
    _url = None

    def __init__(self, url_page):
        self.url = LazyUrl(url_page, self.get, self)

    @try_n(4)
    def get(self, url_page):
        if not self._url:
            id = get_id(url_page)
            html = downloader.read_html(url_page)
            soup = Soup(html, unescape=True)
            self.title = soup.find('title').text.replace('- XVIDEOS.COM', '').strip()
            url = re.find(r'''.setVideoHLS\(['"](.+?)['"]\)''', html)
            ext = get_ext(url)
            if ext.lower() == '.m3u8':
                url = playlist2stream(url, n_thread=5)
            url_thumb = soup.find('meta', {'property': 'og:image'}).attrs['content']
            self.thumb = BytesIO()
            downloader.download(url_thumb, buffer=self.thumb)
            self.filename = format_filename(self.title, id, '.mp4')
            self._url= url
        return self._url



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
            
        self.setIcon(video.thumb)
        self.urls.append(video.url)


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
    urls_set = set()
    for p in range(100):
        url_api = urljoin(url_page, '/{}/{}/videos/best/{}'.format(header, username, p))
        print(url_api)
        r = session.post(url_api, data='main_cats=false')
        soup = Soup(r.text)
        thumbs = soup.findAll('div', class_='thumb-block')
        if not thumbs:
            print_('empty')
            break
        for thumb in thumbs:
            info['name'] = thumb.find('span', class_='name').text.strip()
            href = thumb.find('a')['href']
            href = urljoin(url_page, href)
            if href in urls_set:
                print_('duplicate: {}'.format(href))
                continue
            urls_set.add(href)
            urls.append(href)
        
        if len(urls) >= max_pid:
            break
        
        s = '{} {} - {}'.format(tr_('읽는 중...'), info['name'], len(urls))
        if cw:
            if not cw.alive:
                return
            cw.setTitle(s)
        else:
            print(s)
    if not urls:
        raise Exception('no videos')
    info['urls'] = urls[:max_pid]
    return info
        
