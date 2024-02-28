import downloader
from utils import Soup, Downloader, Session, try_n, format_filename, cut_pair, File, get_print, print_error, json
import ree as re
from io import BytesIO
from m3u8_tools import playlist2stream, M3u8_stream
import errors
import utils
import os


class LoginRequired(errors.LoginRequired):
    def __init__(self, *args):
        super().__init__(*args, method='browser', url='https://login.afreecatv.com/afreeca/login.php')



class Downloader_afreeca(Downloader):
    type = 'afreeca'
    URLS = ['afreecatv.com']
    single = True
    display_name = 'AfreecaTV'
    ACCEPT_COOKIES = [r'(.*\.)?afreecatv\.com']

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        if Live_afreeca.is_live(url):
            url = Live_afreeca.fix_url(url)
        return url.rstrip(' /')

    def read(self):
        video = Video({'referer': self.url})
        video.ready(self.cw)
        self.urls.append(video)

        thumb = BytesIO()
        downloader.download(video['url_thumb'], buffer=thumb)
        self.setIcon(thumb)

        self.title = os.path.splitext(video['name'])[0].replace('：', ':')
        self.artist = video['artist']

        if video['live']:
            d = {}
            d['url'] = self.url
            d['title'] = self.artist
            d['thumb'] = thumb.getvalue()
            utils.update_live(d, self.cw)


@try_n(4)
def _get_stream(url_m3u8, session, referer, cw=None):
    print_ = get_print(cw)
    print_(f'_get_stream: {url_m3u8}')
    try:
        stream = playlist2stream(url_m3u8, referer=referer, session=session)
    except Exception as e:
        print_(print_error(e))
        stream = M3u8_stream(url_m3u8, referer=referer, session=session)
    return stream



class Video(File):
    type = 'afreeca'
    _live_info = None

    def get(self):
        print_ = get_print(self.cw)
        url, session = self['referer'], self.session
        if session is None:
            session = Session()
            session.purge('afreeca')

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

        vid = re.find('/player/([0-9]+)', url)
        if vid is None: # live
            bid = re.find('afreecatv.com/([^/]+)', url, err='no bid')

            url_api = f'https://st.afreecatv.com/api/get_station_status.php?szBjId={bid}'
            r = session.post(url_api, headers={'Referer': url})
            d = json.loads(r.text)
            artist = d['DATA']['user_nick']
            if self._live_info is not None:
                self._live_info['title'] = artist

            url_api = f'https://live.afreecatv.com/afreeca/player_live_api.php?bjid={bid}'
            #bno = re.find('afreecatv.com/[^/]+/([0-9]+)', url, err='no bno')
            bno = re.find(r'nBroadNo\s=\s([0-9]+)', html, err='no bno') #6915
            r = session.post(url_api, data={'bid': bid, 'bno': bno, 'type': 'aid', 'pwd': '', 'player_type': 'html5', 'stream_type': 'common', 'quality': 'master', 'mode': 'landing', 'from_api': '0'}, headers={'Referer': url})
            d = json.loads(r.text)
            res = d['CHANNEL'].get('RESULT')
            print_(f'result: {res}')
            if res == -6:
                raise LoginRequired()
            aid = d['CHANNEL']['AID']

            data = {}
            data['title'] = soup.find('meta', {'property': 'og:title'})['content'].strip()
            data['files'] = [{'file': f'https://pc-web.stream.afreecatv.com/live-stm-16/auth_master_playlist.m3u8?aid={aid}'}]
            data['writer_nick'] = artist
            data['live'] = True
        elif f'{vid}/catch' in url: #6215
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
        artist = data.get('copyright_nickname') or data.get('original_user_nick') or data['writer_nick']

        if data.get('adult_status') == 'notLogin':
            raise LoginRequired(title)

        urls_m3u8 = []
        for file in data['files']:
            if file.get('quality_info'):
                file = file['quality_info'][0]['file']
            else:
                file = file['file']
            urls_m3u8.append(file)
        print_(f'urls_m3u8: {len(urls_m3u8)}')

        if data.get('live'):
            hdr = session.headers.copy()
            hdr['Referer'] = url
            stream = utils.LiveStream(urls_m3u8[0], headers=hdr, cw=self.cw)
        else:
            streams = []
            for url_m3u8 in urls_m3u8:
                try:
                    stream = _get_stream(url_m3u8, session, url, cw=self.cw)
                except Exception as e:
                    print_(print_error(e))
                    continue #2193
                streams.append(stream)
            for stream in streams[1:]:
                streams[0] += stream
            stream = streams[0]

        live = data.get('live') or False
        return {'url': stream, 'title': title, 'name': format_filename(title, vid, '.mp4', artist=artist, live=live), 'url_thumb': url_thumb, 'artist': artist, 'live': live}



class Live_afreeca(utils.Live):
    type = 'afreeca'

    @classmethod
    def is_live(cls, url):
        return bool(re.match(r'https?://(play|bj).afreecatv.com/([^/?#]+)', url)) and url.strip('/').count('/') <= 4

    @classmethod
    def fix_url(cls, url):
        bj = re.find(r'https?://(play|bj).afreecatv.com/([^/?#]+)', url)[1]
        return f'https://play.afreecatv.com/{bj}'

    @classmethod
    def check_live(cls, url, info=None):
        try:
            video = Video({'referer': url})
            video._live_info = info
            video.ready(None)
            return True
        except Exception as e:
            print(e)
            return False
