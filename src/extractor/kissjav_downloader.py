import downloader
from utils import Soup, urljoin, Downloader, LazyUrl, Session, try_n, format_filename, clean_title
from timee import sleep
import ree as re
from io import BytesIO
import clf2


@Downloader.register
class Downloader_kissjav(Downloader):
    type = 'kissjav'
    URLS = ['kissjav.com']
    single = True
    display_name = 'KissJAV'

    def read(self):
        self.session = None#get_session(self.url, cw=self.cw)
        
        video = get_video(self.url, self.session)
        self.urls.append(video.url)
        self.setIcon(video.thumb)
        self.enableSegment(1024*1024//2)
        
        self.title = video.title


@try_n(2)
def get_video(url, session):
    soup = downloader.read_soup(url, session=session)

    view = soup.find('div', id='player-container-fluid')
    src_best = None
    res_best = -1
    for source in view.findAll('source'):
        src = urljoin(url, source.attrs['src'])
        res = re.find('([0-9]+)p', source.attrs['title'])
        res = int(res) if res else 0
        if res > res_best:
            src_best = src
            res_best = res

    if src_best is None:
        raise Exception('No source')

    title = soup.find('h1').text.strip()
    id = soup.find('div', id='video').attrs['data-id']

    url_thumb = soup.find('meta', {'property': 'og:image'}).attrs['content']

    #src_best = downloader.real_url(src_best)

    video = Video(src_best, url_thumb, url, title, id, session)
    return video


class Video(object):
    def __init__(self, url, url_thumb, referer, title, id, session):
        self.title = title
        self.filename = format_filename(title, id, '.mp4')
        self.url = LazyUrl(referer, lambda x: url, self)

        self.thumb = BytesIO()
        self.url_thumb = url_thumb
        downloader.download(url_thumb, buffer=self.thumb, session=session)


@try_n(2)
def get_session(url, cw=None):
    session = Session()
    clf2.solve(url, session=session, cw=cw)
    return session
        
