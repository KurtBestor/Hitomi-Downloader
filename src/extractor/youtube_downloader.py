#coding: utf-8
import ytdl
import downloader
import downloader_v3
from error_printer import print_error
from timee import sleep
import ree as re
from utils import urljoin, Downloader, try_n, get_print, filter_range, compatstr, uuid, get_max_range, format_filename, get_resolution, get_abr, Session, fix_dup, File, clean_title
import ffmpeg
import constants
import os
import utils
from translator import tr, tr_
from datetime import datetime
import threading
from putils import DIR
import errors
MODE = 'query'
utils.TOKENS['youtube'] = ['title', 'id', 'artist', 'date'] + utils.ADD_TOKENS


def print_streams(streams, cw):
    print_ = get_print(cw)

    for stream in streams:
        print_(f'{"LIVE " if stream.live else ""}[{stream.resolution}][{stream.fps}fps][{stream.abr_str}{"(fixed)" if stream.abr_fixed else ""}][{stream.tbr}] {stream.subtype} [{stream.video_codec} / {stream.audio_codec}] ─ {stream.format}')
    print_('')


class Video(File):
    type = 'youtube'
    vcodec = None
    filename0 = None
    chapters = None

    def get(self):
        type = self['type']
        only_mp4 = self['only_mp4']
        audio_included = self['audio_included']
        max_res = self['max_res']
        max_abr = self['max_abr']
        cw = self.cw
        session = self.session
        url = self['referer']
        print_ = get_print(cw)

        print('max_res: {}'.format(max_res))
        for try_ in range(4):
            try:
                self.yt = yt = ytdl.YouTube(url, cw=cw)
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

        if utils.ui_setting.chapterMarkerCheck.isChecked():
            self.chapters = yt.info.get('chapters')

        streams = yt.streams.all()
        print_streams(streams, cw)

        #3528
        time = datetime.strptime(yt.info['upload_date'], '%Y%m%d')
        if utils.ui_setting.youtubeMtimeCheck.isChecked(): #6092
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
            def key(stream):
                fps = stream.fps
                vc = stream.video_codec
                if vc:
                    vc = vc.lower().split('.')[0].lower()
                if vc == 'av01':
                    vc = 'av1'
                if vc == 'vp09':
                    vc = 'vp9'
                try:
                    i = constants.CODECS_PRI.index(vc)
                except ValueError:
                    i = 999
                pr = 'premium' in stream.format.lower() #6350
                return not pr, i, -fps, -stream.tbr
            streams = sorted(streams, key=key) #6079
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
                prefer_format = None#'mp4'
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
                    if stream_final is None or (foo or (stream_final.subtype.lower()!=prefer_format and stream.subtype.lower()==prefer_format)):
                        #print(foo)
                        print_('# stream_final')
                        print_streams([stream], cw)
                        stream_final = stream

            ok = downloader.ok_url(stream_final.url, referer=url, session=session) if isinstance(stream_final.url, str) else True
            if ok:
                break
            else:
                print_('stream is not valid')
                streams.remove(stream_final)
        else:
            if type == 'audio' and max_abr > 0:
                self['max_abr'] = 0
                return self.get(url) # 1776
            raise Exception('No videos')

        stream = stream_final

##        if stream.video_codec and stream_final.video_codec.lower().startswith('av'):
##            self.vcodec = 'h264'

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
            def key(stream):
                abr = stream.abr
                format_note = stream.video.get('format_note')
                if format_note and 'original' in format_note.lower():
                    org = 0
                else:
                    org = 1
                lang = stream.video.get('language')
                if lang and constants.ALANG:
                    match_full = lang.lower().startswith(constants.ALANG)
                    match_part = lang.lower().startswith(constants.ALANG.split('-')[0])
                    if match_full or match_part:
                        lang = -1 if match_full else 0
                    else:
                        lang = 1
                else:
                    lang = 1
                return lang, org, -abr
            streams = sorted(streams, key=key) #6332
            best_audio = streams[0]
            print_streams([best_audio], cw)
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
                self.thumb_url, self._thumb = ytdl.download_thumb(yt.thumbnail_url, cw, session)
            self._thumb.seek(0)
            return self._thumb
        self.thumb = thumb

        #
        _url = self.stream.url
        if callable(_url):
            _url = _url()
        title = yt.title
        #soup = Soup(yt.watch_html)
        #title =  soup.title.text.replace('- YouTube', '').strip()
        self.title = title
        ext = '.' + self.stream.subtype

        #6425
        d = {}
        v = self.stream.video
        if type != 'audio':
            d['width'] = v['width']
            d['height'] = v['height']
        tokens = ['fps',  'vcodec', 'acodec', 'audio_channels', 'language', 'vbr', 'abr', 'tbr']
        for token in tokens:
            value = v.get(token)
            if isinstance(value, str):
                value = clean_title(value)
            d[token] = value
        if self.stream_audio:
            v = self.stream_audio.video
            for token in tokens:
                value = v.get(token)
                if isinstance(value, str):
                    value = clean_title(value)
                _ = d.get(token)
                if not _ or _ == 'none':
                    d[token] = value

        filename = format_filename(title, yt.video_id, ext, artist=yt.info['uploader'], date=time, d=d) #4953, #5529
        filename = fix_dup(filename, CACHE_FILENAMES[self['uid_filenames']]) #6235
        print_(f'filename: {filename}')

        if type == 'audio':
            self.filename0 = filename
            filename = f'{uuid()}_audio.tmp' #4776

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
                    downloader_v3.download(audio, session=session, chunk=1024*1024, n_threads=2, outdir=os.path.dirname(path), fileName=os.path.basename(path), customWidget=cw, overwrite=True, mode=MODE)
                else:
                    downloader.download(audio, session=session, outdir=os.path.dirname(path), fileName=os.path.basename(path), customWidget=cw, overwrite=True)
                self.audio_path = path
                print_('audio done')
            self.thread_audio = threading.Thread(target=f, args=(self.audio,), daemon=True)
            self.thread_audio.start()

        return {'url': _url, 'name': filename}

    def pp(self, filename, i=0):
        cw = self.cw
        print_ = get_print(cw)
        ui_setting = utils.ui_setting
        ext = os.path.splitext(filename)[1].lower()
        if not os.path.isfile(filename):
            print('no file: {}'.format(filename))
            return

        filename_new = filename
        if self['type'] == 'video' and (self.audio is not None or ext != '.mp4') and not self.stream.live: # UHD or non-mp4
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
        elif self['type'] == 'audio' and ext != '.mp3': # convert non-mp3 audio -> mp3
            name, ext_old = os.path.splitext(filename)
            filename_new = '{}.mp3'.format(name)
            ffmpeg.convert(filename, filename_new, '-shortest -preset ultrafast -b:a {}k'.format(get_abr()), cw=cw)

        if self.filename0 and os.path.basename(filename_new) != self.filename0: #4776
            filename0 = utils.fix_enumerate(self.filename0, i, cw)
            filename_old = filename_new
            ext = '.mp4' if self['type'] == 'video' else '.mp3'
            filename_new = os.path.join(os.path.dirname(filename_old), os.path.splitext(filename0)[0]+ext)
            print_(f'rename: {filename_old} -> {filename_new}')
            if filename_old != filename_new:
                if not os.path.exists(os.path.dirname(filename_new)):
                    os.makedirs(os.path.dirname(filename_new))
                if os.path.isfile(filename_new):
                    os.remove(filename_new)
                os.rename(filename_old, filename_new)

        if self['type'] == 'audio' and ui_setting.albumArt.isChecked():
            try:
                ffmpeg.add_cover(filename_new, self.thumb(), {'artist':self.yt.info['uploader'], 'title':self.title}, cw=cw)
            except Exception as e:
                s = print_error(e)
                print_(s)

        if self.chapters and self['type'] == 'video': #6085
            try:
                chapters = []
                for chapter in self.chapters:
                    chapter = ffmpeg.Chapter(chapter['title'], chapter['start_time'], chapter['end_time'])
                    chapters.append(chapter)
                ffmpeg.add_chapters(filename_new, chapters, cw=cw)
            except Exception as e:
                s = print_error(e)
                print_(s)

        if utils.ui_setting.thumbCheck.isChecked():
            import filetype
            s = self.thumb().getvalue()
            ext = filetype.guess(s)
            if ext is None:
                raise Exception('unknown ext')
            filename_thumb = os.path.splitext(filename_new)[0] + '.' + ext.extension
            print_(f'filename_thumb: {filename_thumb}')
            with open(filename_thumb, 'wb') as f:
                f.write(s)
            cw.imgs.append(filename_thumb)
            cw.dones.add(os.path.realpath(filename_thumb))

        utils.pp_subtitle(self, filename_new, cw)

        return filename_new


def get_id(url):
    id_ = re.find(r'youtu.be/([0-9A-Za-z-_]{10,})', url) or re.find(r'[?&]v=([0-9A-Za-z-_]{10,})', url) or re.find(r'/(v|embed|shorts|live)/([0-9A-Za-z-_]{10,})', url) or re.find(r'%3Fv%3D([0-9A-Za-z-_]{10,})', url) #5679
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
        if not re.match('https?://.+', url, re.I):
            url = 'https://www.youtube.com/watch?v={}'.format(url)

        id_ = get_id(url)
        if id_: #6485
            url = 'https://www.youtube.com/watch?v={}'.format(id_)

        for header in ['channel', 'user', 'c']: #5365, #5374
            tab = re.find(rf'/{header}/[^/]+/?(.+)?', url, re.I)
            if tab == 'playlists':
                url = re.sub(rf'(/{header}/[^/]+/?)(.+)?', r'\1', url, flags=re.I)
                tab = ''
            if tab in ['', 'featured'] and '/{}/'.format(header) in url.lower():
                username = re.find(r'/{}/([^/\?]+)'.format(header), url, re.I)
                url = urljoin(url, '/{}/{}/videos'.format(header, username))
        m = re.find(r'youtube.com/(@[^/]+)/?(.+)?', url, re.I)
        if m and m[1] in ['', 'featured']: #6129
            url = urljoin(url, f'/{m[0]}/videos')
        return url.strip('/')

    @classmethod
    def key_id(cls, url):
        return get_id(url) or url

    @classmethod
    def is_channel_url(cls, url):
        return '/channel/' in url or '/user/' in url or '/c/' in url or ''.join(url.split('/')[3:4]).startswith('@')

    def read(self):
        cw = self.cw
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
        self.cw.v3['mode'] = MODE

        # first video must be valid
        while videos:
            video = videos[0]
            try:
                video.ready(cw)
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
            self.urls.append(video)
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


CACHE_FILENAMES = {}
@try_n(2, sleep=1)
def get_videos(url, session, type='video', only_mp4=False, audio_included=False, max_res=None, max_abr=None, cw=None):
    info = {}

    n = get_max_range(cw)

    if Downloader.get('youtube').is_channel_url(url): #5445
        reverse = utils.SD['youtube']['channel_reverse'] #5848
        tab = ''.join(url.split('/')[4:5])
        if tab == '': #5901
            url = '/'.join(url.split('/')[:4]) + '/videos'
        info = read_channel(url, n=n, cw=cw, reverse=reverse)
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

    uid_filenames = uuid()
    CACHE_FILENAMES[uid_filenames] = {}
    info['videos'] = [Video({'referer':url, 'type':type, 'only_mp4':only_mp4, 'audio_included':audio_included, 'max_res':max_res, 'max_abr':max_abr, 'uid_filenames': uid_filenames}) for url in info['urls']]

    return info



def read_channel(url, n, cw=None, reverse=False):
    return read_playlist(url, n, cw, reverse=reverse)


@try_n(2)
def read_playlist(url, n, cw=None, reverse=False):
    print_ = get_print(cw)

    options = {
            'extract_flat': True,
            'playlistend': n,
            'writesubtitles': True,
            }
    ydl = ytdl.YoutubeDL(options, cw=cw)
    info = ydl.extract_info(url)

    es = info['entries']
    urls = []
    for e in es:
        href = 'https://www.youtube.com/watch?v={}'.format(e['id'])
        urls.append(href)
    if reverse:
        urls = urls[::-1]
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
            youtubeCombo_type.setItemIcon(i, utils.ui_setting.youtubeCombo_type.itemIcon(i))
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
            res = win.exec()
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
        {'text': 'MP4 (동영상)', 'format': 'mp4', 'icon': 'movie'},
        {'text': 'MP3 (음원)', 'format': 'mp3', 'icon': 'music'},
        ]

@selector.default_option('youtube')
def default_option():
    return compatstr(utils.ui_setting.youtubeCombo_type.currentText()).lower().split()[0]
