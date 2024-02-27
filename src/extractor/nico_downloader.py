#coding:utf8
import downloader
from io import BytesIO
import ree as re
from utils import Downloader, get_print, format_filename, try_n, LazyUrl, get_abr, Session, get_resolution, print_error, urljoin
import utils
import ffmpeg
import os
import ytdl
import threading
import errors
import websockets # for nama
from m3u8_tools import M3u8_stream


def get_id(url):
    if '/watch/' in url:
        return re.find('/watch/([a-zA-Z0-9]+)', url)


class LoginRequired(errors.LoginRequired):
    def __init__(self, *args):
        super().__init__(*args, method='browser', url='https://account.nicovideo.jp/login')


class Video:
    def __init__(self, session, info, format, cw, hb=None, d=None, live=False, ydl=None):
        self.session = session
        self.info = info
        self.title = info.get('fulltitle') or info['title']
        self.ext = info['ext']
        self.id = info['id']
        self.format = format
        self.username = info['uploader']
        self.url = LazyUrl(f'https://www.nicovideo.jp/watch/{self.id}', self.get, self, pp=self.pp)
        self.cw = cw
        self.hb = hb
        self.d = d
        self.live = live
        self.ydl = ydl

        self.filename = format_filename(self.title, self.id, self.ext, live=live, artist=self.username)

        self.url_thumb = info['thumbnail']
        print('thumb:', self.url_thumb)
        self.thumb = BytesIO()
        downloader.download(self.url_thumb, buffer=self.thumb)

    def get(self, _):
        print_ = get_print(self.cw)
        hb = self.hb
        if hb:
            heartbeat_info_dict = hb['info']
            heartbeat_url = heartbeat_info_dict['url']
            heartbeat_data = heartbeat_info_dict['data'].encode()
            heartbeat_interval = heartbeat_info_dict.get('interval', 30)

            request = ytdl.get_ytdl().utils.sanitized_Request(heartbeat_url, heartbeat_data)

            def heartbeat():
                if self.d.status == 'stop':
                    print_('Heartbeat end')
                    return
                try:
                    hb['ydl'].urlopen(request).read()
                except Exception as e:
                    e_msg = print_error(e)
                    print_(f'Heartbeat failed:\n{e_msg}')

                self.timer = threading.Timer(heartbeat_interval, heartbeat)
                self.timer.start()

            heartbeat_info_dict['ping']()
            print_('Heartbeat with %d second interval ...' % heartbeat_interval)
            heartbeat()
        url = self.info['url']
        if self.live:
            url = ytdl.Downloader(self.ydl, self.info, self.info['format_'], live=True, cw=self.cw)
        return url

    def pp(self, filename):
        if self.format == 'mp4':
            return
        name, ext_old = os.path.splitext(filename)
        filename_new = f'{name}.mp3'
        ffmpeg.convert(filename, filename_new, f'-shortest -preset ultrafast -b:a {get_abr()}k', cw=self.cw)

        if utils.ui_setting.albumArt.isChecked():
            self.thumb.seek(0)#
            ffmpeg.add_cover(filename_new, self.thumb, {'artist':self.username, 'title':self.title}, cw=self.cw)

        return filename_new

    def __repr__(self):
        return f'Video({self.id})'


def suitable(url):
    if 'nicovideo.jp' not in url.lower():
        return False
    if 'nicovideo.jp/user/' in url.lower():
        return True
    return get_id(url) is not None



class Downloader_nico(Downloader):
    type = 'nico'
    single = True
    URLS = [suitable, 'ch.nicovideo.jp']
    display_name = 'Niconico'
    _format = 'mp4'
    MAX_SPEED = 2.0
    ACCEPT_COOKIES = [r'(.*\.)?nicovideo\.jp']

    @classmethod
    def fix_url(cls, url):
        id_ = get_id(url)
        if not id_:
            return url.split('?')[0].split('#')[0]
        if re.find(r'^https?://', id_):
            return url
        if re.find(r'^https?://', url):
            domain = utils.domain(url)
        else:
            domain = 'www.nicovideo.jp'
        return f'https://{domain}/watch/{id_}'

    def init(self):
        self.session = Session('chrome')
        self.url0 = self.url
        if not get_id(self.url):
            self.url = get_live_from_user(self.url, self.session)

    def read(self):
        if self.cw.format:
            self._format = self.cw.format

        if self._format == 'mp3':
            self.cw.setMusic(True)

        video = get_video(self.session, self.url, self._format, self.cw, self)

        self.urls.append(video.url)
        self.setIcon(video.thumb)

        self.title = os.path.splitext(video.filename)[0].replace('：', ':')
        self.artist = video.username

        if video.live:
            d = {}
            d['url'] = self.url0
            d['title'] = video.username
            d['thumb'] = video.thumb.getvalue()
            utils.update_live(d, self.cw)
        else:
            self.enableSegment()


@try_n(2)
def get_video(session, url, format, cw=None, d=None):
    print_ = get_print(cw)

    live = 'live.nico' in url
    if cw and live:
        cw.live = True#

    options = {
        'noplaylist': True,
        #'extract_flat': True,
        'playlistend': 1,
        }
    ydl = ytdl.YoutubeDL(options, cw=cw)
    try:
        info = ydl.extract_info(url)
    except Exception as e:
        e_ = e
        soup = downloader.read_soup(url, session=session)
        box = soup.find('div', class_='channel-invitation-box')
        if box:
            msg = box.find('p', class_='channel-invitation-box-body-channel-desc-msg1')
            if msg:
                msg = msg.text.strip()
            raise LoginRequired(msg or None)
        else:
            raise e_
    fs = info['formats']
    res = max(get_resolution(), min(f.get('height', 0) for f in fs))
    print_(f'res: {res}')
    fs = [f for f in fs if f.get('height', 0) <= res]
    for f in fs:
        print_(f"{f.get('height')} {f['protocol']} {f['format']} - {f['url']}")
##    if not live:
##        fs = [f for f in fs if f['url'].startswith('niconico_dm')]#
    f = fs[-1]
    print_(f'f_url: {f["url"]}')
    if f['url'].startswith('niconico_dmc:'):
        ie = ytdl.get_extractor(url)
        ie._downloader = ydl
        info_dict, heartbeat_info_dict = ie._get_heartbeat_info(f)
        f = info_dict
        hb = {'info': heartbeat_info_dict, 'ydl': ydl}
    elif f['url'].startswith('niconico_dms:'):
        ie = ytdl.get_extractor(url)
        ie._downloader = ydl
        url_m3u8 = ie._get_dms_manifest_url(info)
        print_(f'url_m3u8: {url_m3u8}')
        f['url'] = url_m3u8
        f['protocol'] = 'm3u8'
        _ = info.copy()
        _['formats'] = [f]
        m = ytdl.Downloader(ydl, _, _, cw=cw)
        f['url'] = m
        hb = None
    elif f['protocol'].startswith('m3u8'):
        m = M3u8_stream(f['url'], referer=url, session=session)
##        session.headers.update(f.get('http_headers', {}))
##        hdr = session.headers.copy()
##        m = ffmpeg.Stream(f['url'], headers=hdr, cw=cw)
        f['url'] = m
        hb = None
    else:
        hb = None
    session.headers.update(f.get('http_headers', {}))
    info['url'] = f['url']
    info['format_'] = f

    video = Video(session, info, format, cw, hb=hb, d=d, live=live, ydl=ydl)

    return video


import selector
@selector.options('nico')
def options(urls):
    return [
        {'text': 'MP4 (동영상)', 'format': 'mp4'},
        {'text': 'MP3 (음원)', 'format': 'mp3'},
        ]


def get_live_from_user(url, session):
    if 'ch.nicovideo.jp' in url:
        cid = re.find(r'ch\.nicovideo\.jp/([^/?#]+)', url)
        url = f'https://ch.nicovideo.jp/{cid}/live'
        soup = downloader.read_soup(url, session=session)
        if live_now := soup.find(id='live_now'):
            return urljoin(url, live_now.find('a')['href'])
        raise Exception('no live')
    elif 'nicovideo.jp/user/' in url:
        cid = re.find(r'nicovideo\.jp/user/([^/?#]+)', url)
        d = downloader.read_json(f'https://live.nicovideo.jp/front/api/v1/user-broadcast-history?providerId={cid}&providerType=user&isIncludeNonPublic=false&offset=0&limit=100&withTotalCount=true', session=session)
        for pg in d['data']['programsList']:
            if pg['program']['schedule']['status'] == 'ON_AIR':
                id_ = pg['id']['value']
                return f'https://live.nicovideo.jp/watch/{id_}'
        raise Exception('no live')
    else:
        raise NotImplementedError(url)


class Live_nico(utils.Live):
    type = 'nico'

    @classmethod
    def is_live(cls, url):
        if 'nicovideo.jp/user/' in url.lower():
            return True
        if 'ch.nicovideo.jp' in url.lower():
            return True

    @classmethod
    def fix_url(cls, url):
        if 'nicovideo.jp/user/' in url.lower():
            return '/'.join(url.split('/')[:5]).split('?')[0].split('#')[0]
        return '/'.join(url.split('/')[:4]).split('?')[0].split('#')[0]

    @classmethod
    def check_live(cls, url, info=None):
        try:
            session = Session('chrome')
            get_live_from_user(url, session)
            return True
        except Exception as e:
            print(e)
            return False
