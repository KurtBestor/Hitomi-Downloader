import downloader
from utils import Soup, Downloader, get_outdir, Session, LazyUrl, try_n, format_filename, get_print, cut_pair
import ree as re
from timee import sleep, time
import os
from io import BytesIO
import shutil
from m3u8_tools import playlist2stream, M3u8_stream
import errors
import json


class Video:

    def __init__(self, stream, referer, id, title, url_thumb):
        self.url = LazyUrl(referer, lambda x: stream, self)
        self.id = id
        self.title = title
        self.filename = format_filename(title, id, '.mp4')
        self.url_thumb = url_thumb
        self.thumb = BytesIO()
        downloader.download(url_thumb, buffer=self.thumb)


class LoginRequired(errors.LoginRequired):
    def __init__(self, *args):
        super().__init__(*args, method='browser', url='https://login.afreecatv.com/afreeca/login.php')



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


def get_video(url, session, cw):
    print_ = get_print(cw)

    html = downloader.read_html(url, session=session)
    if "document.location.href='https://login." in html:
        raise LoginRequired()
    if len(html) < 2000:
        alert = re.find(r'''alert\(['"](.+?)['"]\)''', html)
        if alert:
            raise LoginRequired(alert)
    soup = Soup(html)

    url_thumb = soup.find('meta', {'property': 'og:image'}).attrs['content']
    print_('url_thumb: {}'.format(url_thumb))

    url_api = 'https://api.m.afreecatv.com/station/video/a/view'
    vid = re.find(f'/player/([0-9]+)', url, err='no vid')
    r = session.post(url_api, data={'nTitleNo': vid, 'nApiLevel': '10'}, headers={'Referer': url})
    try:
        s = cut_pair(r.text)
        d = json.loads(s)
    except Exception as e:
        print_(r.text)
        raise e
    data = d['data']

    title = data['full_title']

    if data.get('adult_status') == 'notLogin':
        raise LoginRequired(title)

    urls_m3u8 = []
    for file in data['files']:
        file = file['quality_info'][0]['file']
        urls_m3u8.append(file)
    print_(f'urls_m3u8: {len(urls_m3u8)}')

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
    video = Video(stream, url, vid, title, url_thumb)
    return video
