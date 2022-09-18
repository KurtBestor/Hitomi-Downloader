#coding:utf8
import downloader
import nndownload
from io import BytesIO
import ree as re
from utils import Downloader, get_print, compatstr, format_filename, try_n, LazyUrl, get_abr
import utils
from nico_login import login, logout
import ffmpeg
import os
import errors


def get_id(url):
    if '/watch/' in url:
        return re.find('/watch/([a-zA-Z0-9]+)', url)


class Video:
    def __init__(self, session, info, format, cw):
        self.session = session
        self.info = info
        self.title = info['title']
        self.ext = info['ext']
        self.id = info['id']
        self.format = format
        self.username = info['uploader']
        self.url = LazyUrl('https://www.nicovideo.jp/watch/{}'.format(self.id), lambda _: info['url'], self, pp=self.pp)
        self.cw = cw

        self.filename = format_filename(self.title, self.id, self.ext)

        self.url_thumb = info['thumbnail_url']
        print('thumb:', self.url_thumb)
        self.thumb = BytesIO()
        downloader.download(self.url_thumb, buffer=self.thumb)

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
        return u'Video({})'.format(self.id)


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
        ui_setting = self.ui_setting
        if self.cw.format:
            self._format = self.cw.format

        if self._format == 'mp3':
            self.cw.setMusic(True)

        if ui_setting.nicoBox.isChecked():
            username = compatstr(ui_setting.nico_id.text())
            password = compatstr(ui_setting.nico_pw.text())
        else:
            username = ''
            password = ''

        try:
            session = login(username, password)
        except Exception as e:
            logout()
            raise errors.Invalid(u'Failed to login: {}'.format(self.url), fail=True)

        self.session = session
        try:
            video = get_video(session, self.url, self._format, self.cw)
        except Exception as e:
            logout()
            raise

        self.urls.append(video.url)
        self.setIcon(video.thumb)

        self.enableSegment()

        self.title = video.title


@try_n(2)
def get_video(session, url, format, cw=None):
    print_ = get_print(cw)

    id = get_id(url)
    if 'live.nico' in url: #3986
        raise NotImplementedError('nama')
        #info = nndownload.request_nama(session, id)
    else:
        info = nndownload.request_video(session, id)
    video = Video(session, info, format, cw)

    return video


import selector
@selector.options('nico')
def options(urls):
    return [
        {'text': 'MP4 (동영상)', 'format': 'mp4'},
        {'text': 'MP3 (음원)', 'format': 'mp3'},
        ]
