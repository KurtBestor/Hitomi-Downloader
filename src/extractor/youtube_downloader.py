#coding: utf-8
import ytdl
import downloader
import downloader_v3
from constants import isdeleted
from error_printer import print_error
from timee import sleep
import ree as re
from utils import urljoin, Downloader, Soup, try_n, get_print, filter_range, LazyUrl, query_url, compatstr, uuid, get_max_range, format_filename, clean_title, get_resolution, get_abr, Session
import ffmpeg
import sys
import constants
import requests
import chardet
import os
from random import randrange
import utils
from translator import tr, tr_
from datetime import datetime
import threading
from putils import DIR
import errors


def print_streams(streams, cw):
    print_ = get_print(cw)

    for stream in streams:
        print_('{}[{}][{}fps][{}{}][{}] {} [{} / {}] ─ {}'.format('LIVE ' if stream.live else '', stream.resolution, stream.fps, stream.abr_str, '(fixed)' if stream.abr_fixed else '', stream.tbr, stream.subtype, stream.video_codec, stream.audio_codec, stream.format))
    print_('')


class Video:
    _url = None
    vcodec = None
    filename0 = None

    def __init__(self, url, session, type='video', only_mp4=False, audio_included=False, max_res=None, max_abr=None, cw=None):
        self.type = type
        self.only_mp4 = only_mp4
        self.audio_included = audio_included
        self.max_res = max_res
        self.max_abr = max_abr
        self.cw = cw
        self.url = LazyUrl(url, self.get, self, pp=self.pp)
        self.session = session
        self.exec_queue = cw.exec_queue if cw else None#

    def get(self, url, force=False):
        if self._url:
            return self._url

        type = self.type
        only_mp4 = self.only_mp4
        audio_included = self.audio_included
        max_res = self.max_res
        max_abr = self.max_abr
        cw = self.cw
        print_ = get_print(cw)

        if force:
            max_abr = 0

        print('max_res: {}'.format(max_res))
        for try_ in range(4):
            try:
                yt = ytdl.YouTube(url, cw=cw)
                break
            except errors.Retry as e:
                raise e
            except Exception as e:
                e_ = e
                s = print_error(e)
                print_('### youtube retry...\n{}'.format(s))
                sleep(try_, cw)
        else:
            raise e_

        streams = yt.streams.all()
        print_streams(streams, cw)

        #3528
        time = datetime.strptime(yt.info['upload_date'], '%Y%m%d')
        self.utime = (time-datetime(1970,1,1)).total_seconds()
        print_('utime: {}'.format(self.utime))

        if type == 'video':
            streams[:] = [stream for stream in streams if stream.video_codec is not None]
            # Only mp4
            if only_mp4:
                streams_ = list(streams)
                streams[:] = []
                for stream in streams_:
                    if stream.subtype == 'mp4':
                        streams.append(stream)

            # Audio included; Non-HD
            if audio_included:
                streams_ = list(streams)
                streams[:] = []
                for stream in streams_:
                    if stream.audio_codec is not None:
                        streams.append(stream)

            # Maximum resolution
            streams_ = list(streams)
            streams[:] = []
            for stream in streams_:
                if stream.resolution is None:
                    continue
                res = int(stream.resolution.replace('p',''))
                if max_res is None or res <= max_res:
                    streams.append(stream)
            print_('')
        elif type == 'audio':
            streams[:] = [stream for stream in streams if stream.abr]
            # Maximum abr
            abrs = [stream.abr for stream in streams]
            max_abr = min(max(abrs), max_abr)
            streams_ = list(streams)
            streams[:] = []
            for stream in streams_:
                if stream.abr is None:
                    continue
                abr = stream.abr
                if max_abr is None or abr >= max_abr:
                    streams.append(stream)
            #'''
        else:
            raise Exception('type "{}" is not supported'.format(type))

        # Pick the best
        while streams:
            if type == 'video':
                ress = [int_(stream.resolution.replace('p', '')) for stream in streams]
                m = max(ress)
                prefer_format = 'mp4'
            elif type == 'audio':
                ress = [stream.abr for stream in streams]
                m = min(ress)
                prefer_format = 'webm'
            print('Resolutions:', ress)
            stream_final = None
            for stream, res in zip(streams, ress):
                if res == m:
                    if type == 'video':
                        foo = (stream_final is not None) and (stream_final.audio_codec is None) and bool(stream.audio_codec)
                    elif type == 'audio':
                        foo = False
                    if stream_final is None or (stream_final.fps <= stream.fps and (foo or (stream_final.subtype.lower()!=prefer_format and stream.subtype.lower()==prefer_format) or stream_final.fps < stream.fps)):
                        #print(foo)
                        print_('# stream_final {} {} {} {} {} {}fps'.format(stream, stream.format, stream.resolution, stream.subtype, stream.audio_codec, stream.fps))
                        stream_final = stream

            ok = downloader.ok_url(stream_final.url, referer=url, session=self.session) if isinstance(stream_final.url, str) else True
            if ok:
                break
            else:
                print_('stream is not valid')
                streams.remove(stream_final)
        else:
            if type == 'audio' and not force:
                return self.get(url, force=True) # 1776
            raise Exception('No videos')

        stream = stream_final

##        if stream.video_codec and stream_final.video_codec.lower().startswith('av'):
##            self.vcodec = 'h264'

        self.yt = yt
        self.id = yt.video_id
        self.stream = stream
        self.username = yt.info['uploader']
        self.stream_audio = None
        self.audio = None
        self.thumb_url = None
        self.subs = yt.subtitles

        if type == 'audio' and 'DASH' in self.stream.format:
            self.stream.setDashType('audio')

        # Audio
        if type=='video' and stream.audio_codec is None:
            print('audio required')
            streams = [stream for stream in yt.streams.all() if stream.abr]
            print_streams(streams, cw)
            # only mp4; https://github.com/KurtBestor/Hitomi-Downloader/issues/480
            def isGood(stream):
                return stream.audio_codec.lower().startswith('mp4')
            streams_good = [stream for stream in streams if isGood(stream)]
            if streams_good:
                streams = streams_good
                print_streams(streams, cw)
            # only audio?
            if any(stream.resolution is None for stream in streams):
                streams = [stream for stream in streams if stream.resolution is None]
                print_streams(streams, cw)
            best_audio = None
            best_abr = 0
            for stream in streams:
                abr = stream.abr
                if abr > best_abr:
                    best_abr = abr
                    best_audio = stream
            if best_audio is None:
                raise Exception('No audio')
            print(best_audio)
            self.stream_audio = best_audio
            if 'DASH' in self.stream_audio.format:
                self.stream_audio.setDashType('audio')
            self.audio = best_audio.url
            if callable(self.audio):
                self.audio = self.audio()

        # Thumbnail
        self._thumb = None
        def thumb():
            if self._thumb is None:
                self.thumb_url, self._thumb = ytdl.download_thumb(yt.thumbnail_url, cw, self.session)
            self._thumb.seek(0)
            return self._thumb
        self.thumb = thumb

        #
        _url = self.stream.url
        if callable(_url):
            _url = _url()
        self._url = _url
        title = yt.title
        #soup = Soup(yt.watch_html)
        #title =  soup.title.text.replace('- YouTube', '').strip()
        self.title = title
        ext = '.' + self.stream.subtype
        self.filename = format_filename(title, self.id, ext, artist=self.username) #4953
        print_(f'filename: {self.filename}')

        if type == 'audio':
            self.filename0 = self.filename
            self.filename = f'{uuid()}_audio.tmp' #4776

        print_('Resolution: {}'.format(stream.resolution))
        print_('Codec: {} / {}'.format(stream.video_codec, stream.audio_codec))
        print_('Abr: {}'.format(stream.abr))
        print_('Subtype: {}'.format(stream.subtype))
        print_('FPS: {}\n'.format(stream.fps))

        if self.audio is not None: #5015
            def f(audio):
                print_('Download audio: {}'.format(audio))
                path = os.path.join(DIR, f'{uuid()}_a.tmp')
                if cw is not None:
                    cw.trash_can.append(path)
                if constants.FAST:
                    downloader_v3.download(audio, session=self.session, chunk=1024*1024, n_threads=2, outdir=os.path.dirname(path), fileName=os.path.basename(path), customWidget=cw, overwrite=True)
                else:
                    downloader.download(audio, session=self.session, outdir=os.path.dirname(path), fileName=os.path.basename(path), customWidget=cw, overwrite=True)
                self.audio_path = path
                print_('audio done')
            self.thread_audio = threading.Thread(target=f, args=(self.audio,), daemon=True)
            self.thread_audio.start()

        return self._url

    def pp(self, filename, i=0):
        cw = self.cw
        print_ = get_print(cw)
        ui_setting = utils.ui_setting
        ext = os.path.splitext(filename)[1].lower()
        if not os.path.isfile(filename):
            print('no file: {}'.format(filename))
            return

        filename_new = filename
        if self.type == 'video' and (self.audio is not None or ext != '.mp4') and not self.stream.live: # UHD or non-mp4
            if self.audio is not None: # merge
                self.thread_audio.join()
                ext, out = ffmpeg.merge(filename, self.audio_path, cw=cw, vcodec=self.vcodec)
                #print(out)
                name, ext_old = os.path.splitext(filename)
                if ext_old.lower() != ext.lower():
                    print_('rename ext {} --> {}'.format(ext_old, ext))
                    filename_new = '{}{}'.format(name, ext)
                    if os.path.isfile(filename_new):
                        os.remove(filename_new)
                    os.rename(filename, filename_new)
            else: # convert non-mp4 video -> mp4
                name, ext_old = os.path.splitext(filename)
                filename_new = '{}.mp4'.format(name)
                print_('Convert video: {} -> {}'.format(filename, filename_new))
                ffmpeg.convert(filename, filename_new, cw=cw)
        elif self.type == 'audio' and ext != '.mp3': # convert non-mp3 audio -> mp3
            name, ext_old = os.path.splitext(filename)
            filename_new = '{}.mp3'.format(name)
            ffmpeg.convert(filename, filename_new, '-shortest -preset ultrafast -b:a {}k'.format(get_abr()), cw=cw)

        if self.filename0 and os.path.basename(filename_new) != self.filename0: #4776
            filename0 = utils.fix_enumerate(self.filename0, i, cw)
            filename_old = filename_new
            ext = '.mp4' if self.type == 'video' else '.mp3'
            filename_new = os.path.join(os.path.dirname(filename_old), os.path.splitext(filename0)[0]+ext)
            print_(f'rename: {filename_old} -> {filename_new}')
            if filename_old != filename_new:
                if os.path.isfile(filename_new):
                    os.remove(filename_new)
                os.rename(filename_old, filename_new)

        if self.type == 'audio' and ui_setting.albumArt.isChecked():
            try:
                ffmpeg.add_cover(filename_new, self.thumb(), {'artist':self.username, 'title':self.title}, cw=cw)
            except Exception as e:
                s = print_error(e)
                print_(s)

        utils.pp_subtitle(self, filename_new, cw)

        return filename_new


def get_id(url):
    id_ = re.find(r'youtu.be/([0-9A-Za-z-_]{10,})', url) or re.find(r'[?&]v=([0-9A-Za-z-_]{10,})', url) or re.find(r'/(v|embed|shorts)/([0-9A-Za-z-_]{10,})', url) or re.find(r'%3Fv%3D([0-9A-Za-z-_]{10,})', url)
    if isinstance(id_, tuple):
        id_ = id_[-1]
    return id_


class Downloader_youtube(Downloader):
    type = 'youtube'
    single = True
    yt_type = None
    URLS = ['youtube.co', 'youtu.be']
    lock = True
    display_name = 'YouTube'
    keep_date = True #3528
    __format = {}
    ACCEPT_COOKIES = [r'.*(youtube|youtu\.be|google).*']

    def init(self):
        format = self.cw.format
        if format:
            if isinstance(format, str):
                ext_result = format
            elif isinstance(format, dict):
                ext_result = format['format']
                self.__format = format
            else:
                raise NotImplementedError(format)
        else:
            ext_result = default_option()
            self.cw.format = ext_result

        if ext_result in ['mp4', 'mkv', '3gp']:
            self.yt_type = 'video'
        else:
            self.yt_type = 'audio'
            self.cw.setMusic(True)
        self.session = Session()

    @classmethod
    def fix_url(cls, url): #2033
        if not re.match('https?://.+', url, re.IGNORECASE):
            url = 'https://www.youtube.com/watch?v={}'.format(url)
        qs = query_url(url)
        if 'v' in qs:
            url = url.split('?')[0] + '?v={}'.format(qs['v'][0])

        for header in ['channel', 'user', 'c']: #5365, #5374
            tab = re.find(rf'/{header}/[^/]+/?(.+)?', url, re.IGNORECASE)
            if tab == 'playlists':
                url = re.sub(rf'(/{header}/[^/]+/?)(.+)?', r'\1', url, flags=re.IGNORECASE)
                tab = ''
            if tab in ['', 'featured'] and '/{}/'.format(header) in url.lower():
                username = re.find(r'/{}/([^/\?]+)'.format(header), url, re.IGNORECASE)
                url = urljoin(url, '/{}/{}/videos'.format(header, username))
        return url.strip('/')

    @classmethod
    def key_id(cls, url):
        return get_id(url) or url

    def read(self):
        ui_setting = self.ui_setting
        cw = self.cw
        print_ = get_print(cw)
        if self.yt_type == 'video':
            res = self.__format.get('res', get_resolution())
            info = get_videos(self.url, self.session, type=self.yt_type, max_res=res, only_mp4=False, audio_included=not True, cw=cw)
        else:
            abr = self.__format.get('abr', get_abr())
            info = get_videos(self.url, self.session, type=self.yt_type, max_abr=abr, cw=cw)
        videos = info['videos']

        if not videos:
            raise Exception('No videos')

        self.enableSegment(overwrite=True)

        # first video must be valid
        while videos:
            video = videos[0]
            try:
                video.url()
                break
            except Exception as e:
                e_ = e
                self.print_(print_error(e))
                videos.remove(video)
        else:
            raise e_

        if info['type'] != 'single':
            video = self.process_playlist(info['title'], videos)
        else:
            self.urls.append(video.url)
            self.title = video.title
            if video.stream.live:
                self.lock = False

        self.artist = video.username
        self.setIcon(video.thumb())


def int_(x):
    try:
        return int(x)
    except:
        return 0


@try_n(2, sleep=1)
def get_videos(url, session, type='video', only_mp4=False, audio_included=False, max_res=None, max_abr=None, cw=None):
    info = {}

    n = get_max_range(cw)

    if '/channel/' in url or '/user/' in url or '/c/' in url or ''.join(url.split('/')[3:4]).startswith('@'): #5445
        info = read_channel(url, n=n, cw=cw)
        info['type'] = 'channel'
        info['title'] = '[Channel] {}'.format(info['uploader'])
        if cw:
            info['urls'] = filter_range(info['urls'], cw.range)
            cw.fped = True
    elif '/playlist' in url:
        info = read_playlist(url, n=n, cw=cw)
        info['type'] = 'playlist'
        info['title'] = '[Playlist] {}'.format(info['title'])
        if cw:
            info['urls'] = filter_range(info['urls'], cw.range)
            cw.fped = True
    elif get_id(url):
        info['type'] = 'single'
        info['urls'] = [url]
    else:
        raise NotImplementedError(url)

    info['videos'] = [Video(url, session, type, only_mp4, audio_included, max_res, max_abr, cw) for url in info['urls']]

    return info



def read_channel(url, n, cw=None):
    return read_playlist(url, n, cw)


@try_n(2)
def read_playlist(url, n, cw=None):
    print_ = get_print(cw)

    options = {
            'extract_flat': True,
            'playlistend': n,
            }
    ydl = ytdl.YoutubeDL(options, cw=cw)
    info = ydl.extract_info(url)

    es = info['entries']
    urls = []
    for e in es:
        href = 'https://www.youtube.com/watch?v={}'.format(e['id'])
        urls.append(href)
    info['urls'] = urls

    if not info.get('uploader'):
        title = info['title']
        if title.lower().endswith(' - videos'):
            title = title[:-len(' - videos')]
        info['uploader'] = title
        print_('⚠️ Fix uploader: None -> {}'.format(title))

    return info


import selector
@selector.register('youtube')
def select():
    from Qt import Qt, QDialog, QFormLayout, QLabel, QComboBox, QWidget, QVBoxLayout, QDialogButtonBox
    if utils.ui_setting.askYoutube.isChecked():
        win = QDialog(constants.mainWindow)
        win.setWindowTitle('Youtube format')
        utils.windows.append(win)
        layout = QFormLayout(win)

        youtubeCombo_type = QComboBox()
        layout.addRow('파일 형식', youtubeCombo_type)
        for i in range(utils.ui_setting.youtubeCombo_type.count()):
            youtubeCombo_type.addItem(utils.ui_setting.youtubeCombo_type.itemText(i))
        youtubeCombo_type.setCurrentIndex(utils.ui_setting.youtubeCombo_type.currentIndex())

        youtubeLabel_res = QLabel('해상도')
        youtubeCombo_res = QComboBox()
        for i in range(utils.ui_setting.youtubeCombo_res.count()):
            youtubeCombo_res.addItem(utils.ui_setting.youtubeCombo_res.itemText(i))
        youtubeCombo_res.setCurrentIndex(utils.ui_setting.youtubeCombo_res.currentIndex())

        youtubeLabel_abr = QLabel('음질')
        youtubeCombo_abr = QComboBox()
        for i in range(utils.ui_setting.youtubeCombo_abr.count()):
            youtubeCombo_abr.addItem(utils.ui_setting.youtubeCombo_abr.itemText(i))
        youtubeCombo_abr.setCurrentIndex(utils.ui_setting.youtubeCombo_abr.currentIndex())

        aa = QWidget()
        a = QVBoxLayout(aa)
        a.setContentsMargins(0,0,0,0)
        a.addWidget(youtubeLabel_res)
        a.addWidget(youtubeLabel_abr)
        bb = QWidget()
        b = QVBoxLayout(bb)
        b.setContentsMargins(0,0,0,0)
        b.addWidget(youtubeCombo_res)
        b.addWidget(youtubeCombo_abr)
        layout.addRow(aa, bb)

        def currentIndexChanged(index):
            text_type = compatstr(youtubeCombo_type.currentText())
            print(text_type)
            if tr_('동영상') in text_type:
                youtubeLabel_abr.hide()
                youtubeCombo_abr.hide()
                youtubeLabel_res.show()
                youtubeCombo_res.show()
            elif tr_('음원') in text_type:
                youtubeLabel_res.hide()
                youtubeCombo_res.hide()
                youtubeLabel_abr.show()
                youtubeCombo_abr.show()
        youtubeCombo_type.currentIndexChanged.connect(currentIndexChanged)
        youtubeCombo_type.currentIndexChanged.emit(youtubeCombo_type.currentIndex())

        buttonBox = QDialogButtonBox()
        layout.addWidget(buttonBox)
        buttonBox.setOrientation(Qt.Horizontal)
        buttonBox.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttonBox.accepted.connect(win.accept)
        buttonBox.rejected.connect(win.reject)

        tr(win)
        win.setWindowOpacity(constants.opacity_max)
        try:
            res = win.exec_()
            utils.log(f'youtube.select.res: {res}')
            if not res:
                return selector.Cancel
            utils.windows.remove(win)
            format = {}
            format['format'] = compatstr(youtubeCombo_type.currentText()).lower().split()[0]
            format['res'] = get_resolution(compatstr(youtubeCombo_res.currentText()))
            format['abr'] = get_abr(compatstr(youtubeCombo_abr.currentText()))
        finally:
            win.deleteLater()
        return format


@selector.options('youtube')
def options(urls):
    return [
        {'text': 'MP4 (동영상)', 'format': 'mp4'},
        {'text': 'MP3 (음원)', 'format': 'mp3'},
        ]

@selector.default_option('youtube')
def default_option():
    return compatstr(utils.ui_setting.youtubeCombo_type.currentText()).lower().split()[0]
