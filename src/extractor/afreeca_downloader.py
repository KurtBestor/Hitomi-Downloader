import downloader
from utils import Soup, Downloader, get_outdir, Session, LazyUrl, try_n, format_filename, cut_pair, File
import ree as re
from timee import sleep, time
import os
from io import BytesIO
import shutil
from m3u8_tools import playlist2stream, M3u8_stream
import errors
import json


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
        video = Video({'referer': self.url})
        video.ready(self.cw)
        self.urls.append(video)

        thumb = BytesIO()
        downloader.download(video['url_thumb'], buffer=thumb)
        self.setIcon(thumb)

        self.title = video['title']


@try_n(4)
def _get_stream(url_m3u8):
    print('_get_stream', url_m3u8)
    try:
        stream = playlist2stream(url_m3u8)
    except Exception as e:
        print(e)
        stream = M3u8_stream(url_m3u8)
    return stream



class Video(File):
    type = 'afreeca'

    def get(self):
        url, session = self['referer'], self.session

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

        vid = re.find(f'/player/([0-9]+)', url, err='no vid')
        if f'{vid}/catch' in url: #6215
            url_api = 'https://api.m.afreecatv.com/station/video/a/catchview'
            r = session.post(url_api, data={'nPageNo': '1', 'nLimit': '10', 'nTitleNo': vid}, headers={'Referer': url})
            try:
                s = cut_pair(r.text)
                d = json.loads(s)
            except Exception as e:
                print_(r.text)
                raise e
            data = d['data'][0]
        else:
            url_api = 'https://api.m.afreecatv.com/station/video/a/view'
            r = session.post(url_api, data={'nTitleNo': vid, 'nApiLevel': '10', 'nPlaylistIdx': '0'}, headers={'Referer': url})
            try:
                s = cut_pair(r.text)
                d = json.loads(s)
            except Exception as e:
                print_(r.text)
                raise e
            data = d['data']

        title = data.get('full_title') or data['title']

        if data.get('adult_status') == 'notLogin':
            raise LoginRequired(title)

        urls_m3u8 = []
        for file in data['files']:
            if file.get('quality_info'):
                file = file['quality_info'][0]['file']
            else:
                file = file['file']
            urls_m3u8.append(file)
        self.cw.print_(f'urls_m3u8: {len(urls_m3u8)}')

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

        return {'url': stream, 'title': title, 'name': format_filename(title, id, '.mp4'), 'url_thumb': url_thumb}
