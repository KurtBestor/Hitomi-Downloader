import downloader
import ree as re
from utils import urljoin, Downloader, format_filename, Soup, LazyUrl, get_print, Session
from m3u8_tools import M3u8_stream
from io import BytesIO
PATTERN_ID = r'/content/([^/]+)'



class Downloader_fc2(Downloader):
    type = 'fc2'
    single = True
    URLS = ['video.fc2.com']
    ACCEPT_COOKIES = [r'(.*\.)?fc2\.com']

    @classmethod
    def fix_url(cls, url):
        if not re.match(r'https?://.+', url, re.I):
            url = f'https://video.fc2.com/content/{url}'
        return url

    @classmethod
    def key_id(cls, url):
        return re.find(PATTERN_ID, url) or url

    def read(self):
        self.session = Session()
        self.session.cookies.set('_ac', '1', domain='.video.fc2.com')
        info = get_info(self.url, self.session, self.cw)

        video = info['videos'][0]

        self.urls.append(video.url)

        f = BytesIO()
        downloader.download(video.url_thumb, referer=self.url, buffer=f)
        self.setIcon(f)

        self.title = info['title']


class Video:

    def __init__(self, url, url_thumb, referer, title, id_, session):
        self._url = url
        self.url = LazyUrl(referer, self.get, self)
        self.filename = format_filename(title, id_, '.mp4')
        self.url_thumb = url_thumb
        self.session = session

    def get(self, referer):
        ext = downloader.get_ext(self._url, session=self.session, referer=referer)
        if ext == '.m3u8':
            video = M3u8_stream(self._url, referer=referer, session=self.session, n_thread=4)
        else:
            video = self._url
        return video


def get_info(url, session, cw=None):
    print_ = get_print(cw)
    info = {'videos': []}
    html = downloader.read_html(url, session=session)
    soup = Soup(html)
    info['title'] = soup.find('h2', class_='videoCnt_title').text.strip()

    id_ = re.find(PATTERN_ID, url, err='no id')
    print_('id: {}'.format(id_))
    token = re.find(r'''window.FC2VideoObject.push\(\[['"]ae['"], *['"](.+?)['"]''', html, err='no token')
    print_('token: {}'.format(token))

    url_api = 'https://video.fc2.com/api/v3/videoplaylist/{}?sh=1&fs=0'.format(id_)
    hdr = {
        'X-FC2-Video-Access-Token': token,
        }
    data = downloader.read_json(url_api, url, session=session, headers=hdr)

    pl = data['playlist']
    url_video = urljoin(url, pl.get('hq') or pl.get('nq') or pl['sample']) #3784
    url_thumb = soup.find('meta', {'property':'og:image'})['content']
    video = Video(url_video, url_thumb, url, info['title'], id_, session)
    info['videos'].append(video)

    return info
