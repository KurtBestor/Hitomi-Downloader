#coding:utf8
import downloader
from io import BytesIO
import ree as re
from utils import Downloader, get_print, format_filename, try_n, LazyUrl, get_abr, Session, get_resolution, print_error
import utils
import ffmpeg
import os
import ytdl
import threading
import errors


def get_id(url):
    if '/watch/' in url:
        return re.find('/watch/([a-zA-Z0-9]+)', url)


class LoginRequired(errors.LoginRequired):
    def __init__(self, *args):
        super().__init__(*args, method='browser', url='https://account.nicovideo.jp/login')


class Video:
    def __init__(self, session, info, format, cw, hb=None, d=None):
        self.session = session
        self.info = info
        self.title = info['title']
        self.ext = info['ext']
        self.id = info['id']
        self.format = format
        self.username = info['uploader']
        self.url = LazyUrl('https://www.nicovideo.jp/watch/{}'.format(self.id), self.get, self, pp=self.pp)
        self.cw = cw
        self.hb = hb
        self.d = d

        self.filename = format_filename(self.title, self.id, self.ext)

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
        return self.info['url']

    def pp(self, filename):
        if self.format == 'mp4':
            return
        name, ext_old = os.path.splitext(filename)
        filename_new = '{}.mp3'.format(name)
        ffmpeg.convert(filename, filename_new, '-shortest -preset ultrafast -b:a {}k'.format(get_abr()), cw=self.cw)

        if utils.ui_setting.albumArt.isChecked():
            self.thumb.seek(0)#
            ffmpeg.add_cover(filename_new, self.thumb, {'artist':self.username, 'title':self.title}, cw=self.cw)

        return filename_new

    def __repr__(self):
        return 'Video({})'.format(self.id)


def suitable(url):
    if 'live.nico' in url: #3986
        return False
    if 'nicovideo.jp' not in url.lower():
        return False
    return get_id(url) is not None



class Downloader_nico(Downloader):
    type = 'nico'
    single = True
    URLS = [suitable]
    display_name = 'Niconico'
    _format = 'mp4'
    MAX_SPEED = 2.0
    ACCEPT_COOKIES = [r'(.*\.)?nicovideo\.jp']

    @classmethod
    def fix_url(cls, url):
        id_ = get_id(url)
        if re.find(r'^https?://', id_):
            return url
        if re.find(r'^https?://', url):
            domain = utils.domain(url)
        else:
            domain = 'www.nicovideo.jp'
        return 'https://{}/watch/{}'.format(domain, id_)

    def read(self):
        if self.cw.format:
            self._format = self.cw.format

        if self._format == 'mp3':
            self.cw.setMusic(True)

        self.session = Session('chrome')
        video = get_video(self.session, self.url, self._format, self.cw, self)

        self.urls.append(video.url)
        self.setIcon(video.thumb)

        self.enableSegment()

        self.title = video.title


@try_n(2)
def get_video(session, url, format, cw=None, d=None):
    print_ = get_print(cw)

    if 'live.nico' in url: #3986
        raise NotImplementedError('nama')
    else:
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
        res = max(get_resolution(), min(f['height'] for f in fs))
        print_(f'res: {res}')
        fs = [f for f in fs if f['height'] <= res]
        for f in fs:
            print_(f"{f['format']} - {f['url']}")
        fs = [f for f in fs if f['url'].startswith('niconico_dmc:')]#
        f = fs[-1]
        print_(f'f_url: {f["url"]}')
        if f['url'].startswith('niconico_dmc:'):
            ie = ytdl.get_extractor(url)
            ie._downloader = ydl
            info_dict, heartbeat_info_dict = ie._get_heartbeat_info(f)
            f = info_dict
            hb = {'info': heartbeat_info_dict, 'ydl': ydl}
        else:
            hb = None
        session.headers.update(f.get('http_headers', {}))
        info['url'] = f['url']

    video = Video(session, info, format, cw, hb=hb, d=d)

    return video


import selector
@selector.options('nico')
def options(urls):
    return [
        {'text': 'MP4 (동영상)', 'format': 'mp4'},
        {'text': 'MP3 (음원)', 'format': 'mp3'},
        ]
