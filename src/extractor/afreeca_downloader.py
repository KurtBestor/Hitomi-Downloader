import downloader
from utils import Soup, Downloader, get_outdir, Session, LazyUrl, try_n, format_filename, get_print
import ree as re
from timee import sleep, time
import os
from io import BytesIO
import shutil
from m3u8_tools import playlist2stream, M3u8_stream
import errors


class Video:

    def __init__(self, stream, referer, id, title, url_thumb):
        self.url = LazyUrl(referer, lambda x: stream, self)
        self.id = id
        self.title = title
        self.filename = format_filename(title, id, '.mp4')
        self.url_thumb = url_thumb
        self.thumb = BytesIO()
        downloader.download(url_thumb, buffer=self.thumb)



class Downloader_afreeca(Downloader):
    type = 'afreeca'
    URLS = ['afreecatv.com']
    single = True
    display_name = 'AfreecaTV'

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        return url.rstrip(' /')

    def read(self):
        video = get_video(self.url, self.session, self.cw)
        self.urls.append(video.url)

        self.setIcon(video.thumb)

        self.title = video.title


@try_n(4)
def _get_stream(url_m3u8):
    print('_get_stream', url_m3u8)
    try:
        stream = playlist2stream(url_m3u8)
    except Exception as e:
        print(e)
        stream = M3u8_stream(url_m3u8)
    return stream


@try_n(8)
def get_video(url, session, cw):
    print_ = get_print(cw)
    html = downloader.read_html(url, session=session)
    if "document.location.href='https://login." in html:
        raise errors.LoginRequired()
    if len(html) < 2000:
        alert = re.find(r'''alert\(['"](.+?)['"]\)''', html)
        if alert:
            raise errors.LoginRequired(alert)
    soup = Soup(html)
    url_thumb = soup.find('meta', {'property': 'og:image'}).attrs['content']
    print_('url_thumb: {}'.format(url_thumb))
    params = re.find('VodParameter *= *[\'"]([^\'"]+)[\'"]', html, err='No VodParameter')
    params += '&adultView=ADULT_VIEW&_={}'.format(int(time()*1000))
    for subdomain in ['afbbs', 'stbbs']: #4758
        url_xml = 'http://{}.afreecatv.com:8080/api/video/get_video_info.php?'.format(subdomain) + params
        print_(url_xml)
        try:
            html = downloader.read_html(url_xml, session=session, referer=url)
            break
        except Exception as e:
            e_ = e
    else:
        raise e_
    soup = Soup(html)
    if '<flag>PARTIAL_ADULT</flag>' in html:
        raise errors.LoginRequired()
    title = soup.find('title').string.strip()
    urls_m3u8 = re.findall('https?://[^>]+playlist.m3u8', html)
    if not urls_m3u8:
        raise Exception('no m3u8')
    streams = []
    for url_m3u8 in urls_m3u8:
        try:
            stream = _get_stream(url_m3u8)
        except Exception as e:
            print(e)
            continue #2193
        streams.append(stream)
    for stream in streams[1:]:
        streams[0] += stream
    stream = streams[0]
    id = url.split('/')[(-1)].split('?')[0].split('#')[0]
    video = Video(stream, url, id, title, url_thumb)
    return video
