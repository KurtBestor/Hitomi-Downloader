from utils import Downloader, clean_title, lock
import constants, os, downloader
from size import Size
from timee import sleep
from translator import tr_
import utils
import filesize as fs
from datetime import datetime
import errors
import ips
torrent = None
TIMEOUT = 600
CACHE_INFO = True
TOO_MANY = 1000


def isInfoHash(s):
    if len(s) != 40:
        return False
    try:
        bytes.fromhex(s)
        return True
    except:
        return False
    


class Downloader_torrent(Downloader):
    type = 'torrent'
    URLS = [r'regex:^magnet:', r'regex:\.torrent$', isInfoHash]
    single = True
    update_filesize = False
    _info = None
    _name = None
    _filesize_prev = 0
    _upload_prev = 0
    _state = None
    _h = None
    _dn = None
    MAX_PARALLEL = 16
    MAX_CORE = 0
    skip_convert_imgs = True
    _filesize_init = False
    _max_speed = None
    _anon = False
    _proxy = '', '', 0, '', ''
    _seeding = False
    _virgin = True

    @classmethod
    def fix_url(cls, url):
        if isInfoHash(url):
            url = f'magnet:?xt=urn:btih:{url}'
        return url

    @classmethod
    def set_max_speed(cls, speed):
        cls._max_speed = speed
        cls.updateSettings()

    @classmethod
    def set_anon(cls, flag):
        cls._anon = flag
        cls.updateSettings()

    @classmethod
    def set_proxy(cls, protocol, host, port, username, password):
        cls._proxy = protocol, host, port, username, password
        cls.updateSettings()

    @classmethod
    @lock
    def updateSettings(cls):
        if torrent is None:
            print('torrent is None')
            return
        torrent.set_max_speed(cls._max_speed)
        torrent.set_anon(cls._anon)
        torrent.set_proxy(*cls._proxy)

    @classmethod
    def _import_torrent(cls):
        global torrent
        if torrent is None:
            import torrent

    @lock
    def __init(self):
        self._import_torrent()
        Downloader_torrent.updateSettings()

    @classmethod
    def key_id(cls, url):
        if torrent is None:
            print('torrent is None')
            return url
        id_, e = torrent.key_id(url)
        if e:
            print(e)
        return id_

    @property
    def name(self):
        if self._name is None:
            self._name = clean_title(self._info.name())
        return self._name

    @classmethod
    def get_dn(cls, url):
        if url.startswith('magnet:'):
            qs = utils.query_url(url)
            if 'dn' in qs:
                return utils.html_unescape(qs['dn'][0])

    def read(self):
        cw = self.cw
        self.cw.pbar.hide()
        self.__init()
        if cw:
            cw._torrent_s = None
        title = self.url
        self._dn = self.get_dn(self.url)
        info = getattr(cw, 'info?', None)
        if info is not None:
            self.print_('cached info')
            self._info = info
        if self._info is None:
            try:
                self._info = torrent.get_info(self.url, cw, timeout=TIMEOUT, callback=self.callback)
                if CACHE_INFO:
                    setattr(cw, 'info?', self._info)
            except Exception as e:
                self.update_pause()
                if not cw.paused:
                    raise errors.Invalid('Faild to read metadata: {}'.format(self.url), fail=True)
        if self._info is None:
            cw.paused = True
        if cw.paused:
            return
        hash_ = self._info.hash.hex()
        self.print_('v2: {}'.format(self._info.v2))
        self.print_('Hash: {}'.format(hash_))
        if not self._info.v2:
            self.url = 'magnet:?xt=urn:btih:{}'.format(hash_)#
        date = datetime.fromtimestamp(self._info.creation_date())
        date = date.strftime('%y-%m-%d %H:%M:%S')
        self.print_('Created on: {}'.format(date))
        self.print_('Total size: {}'.format(fs.size(self._info.total_size())))
        self.print_('Pieces: {} x {}'.format(self._info.num_pieces(), fs.size(self._info.piece_length())))
        self.print_('Creator: {}'.format(self._info.creator()))
        self.print_('Comment: {}'.format(self._info.comment()))
        cw.setTotalFileSize(self._info.total_size())

        cw.imgs.clear()
        cw.dones.clear()

        self.urls = [self.url]
        self.title = self.name
        self.update_files()

        if not self.single and not os.path.isdir(self.dir): #4698
            downloader.makedir_event(self.dir, cw)

        cw.pbar.show()

    def update_files(self):
        cw = self.cw
        files = torrent.get_files(self._info, cw=cw)
        if not files:
            raise Exception('No files')
        cw.single = self.single = len(files) <= 1
        for file in files:
            filename = os.path.join(self.dir, file.path)
            cw.imgs.append(filename)

    def update_pause(self):
        cw = self.cw
        if cw.pause_lock:
            if self._seeding:
                cw.pause_lock = False
                return
            cw.pause_data = {
                'type': self.type,
                'url': self.url,
                }
            cw.paused = True
            cw.pause_lock = False
            self.update_tools_buttons()

    def start_(self):
        cw = self.cw
        cw.pbar.setFormat('%p%')
        cw.setColor('reading')
        cw.downloader_pausable = True
        self._seeding = False
        if cw.paused:
            data = cw.pause_data
            cw.paused = False
            cw.pause_lock = False
            self.update_tools_buttons()
        try:
            self.read()
            if self.status == 'stop':
                self.stop()
                return True
            if cw.paused:
                pass
            else:
                cw.dir = self.dir
                cw.urls[:] = self.urls
                cw.clearPieces()
                self.size = Size()
                self.size_upload = Size()
                cw.pbar.setMaximum(self._info.total_size())
                cw.setColor('reading')
                torrent.download(self._info, save_path=self.dir, callback=self.callback, cw=cw)
                self.update_progress(self._h, False)
                cw.setSpeed(0.0)
                cw.setUploadSpeed(0.0)
            if not cw.alive:
                return
            self.update_pause()
            if cw.paused:
                return True
            self.title = self.name
            if not self.single:
                cw.pbar.setMaximum(len(cw.imgs))
        finally:
            cw.clearPieces()
            try:
                cw.set_extra('torrent_progress', torrent.get_file_progress(self._h, self._info, True))
            except Exception as e:
                cw.remove_extra('torrent_progress')
                self.print_error(e)
            self._h = None

    def _updateIcon(self):
        cw = self.cw
        n = 4
        for try_ in range(n):
            if cw.setIcon(cw.imgs[0], icon=try_==n-1):
                break
            sleep(.5)

    def update_progress(self, h, fast):
        if self._info is None:
            return
        cw = self.cw

        if not cw.imgs: #???
            self.print_('???')
            self.update_files()

        sizes = torrent.get_file_progress(h, self._info, fast)
        for i, (file, size) in enumerate(zip(cw.names, sizes)):
            if i > 0 and fast:
                break#
            file = os.path.realpath(file)
            if file in cw.dones:
                continue
            if size[0] == size[1]:
                cw.dones.add(file)
                file = constants.compact(file).replace('\\', '/')
                files = file.split('/')
                file = ' / '.join(files[1:])
                msg = 'Completed: {} | {}'.format(file, fs.size(size[1]))
                self.print_(msg)
                if i == 0 and size[0]:
                    self._updateIcon()

        cw.setPieces(torrent.pieces(h, self._info))

    def callback(self, h, s, alerts):
        try:
            return self._callback(h, s, alerts)
        except Exception as e:
            self.print_error(e)
            return 'abort'

    def _callback(self, h, s, alerts):
        self._h = h
        cw = self.cw

        if self._virgin:
            self._virgin = False
            try:
                ips.get('0.0.0.0')
            except Exception as e:
                self.print_error(e)

        if self._state != s.state_str:
            self._state = s.state_str
            self.print_('state: {}'.format(s.state_str))

##        for alert in alerts:
##            self.print_('⚠️ {}'.format(alert))

        title = (self._dn or self.url) if self._info is None else self.name

        if cw.alive and cw.valid and not cw.pause_lock:
            seeding = False
            cw._torrent_s = s
            fast = len(cw.imgs) > TOO_MANY
            self.update_progress(h, fast)

            filesize = s.total_done
            upload = s.total_upload
            color = 'downloading'
            if s.state_str in ('downloading', 'seeding'):
                # init filesize
                if not self._filesize_init:
                    self._filesize_prev = filesize
                    self._filesize_init = True
                    self.print_('init filesize: {}'.format(fs.size(filesize)))

                # download
                d_size = filesize - self._filesize_prev
                self._filesize_prev = filesize
                self.size += d_size
                downloader.total_download_size_torrent += d_size
                # upload
                d_size = upload - self._upload_prev
                self._upload_prev = upload
                self.size_upload += d_size
                downloader.total_upload_size_torrent += d_size
            if self._info is not None:
                cw.pbar.setValue(s.progress * self._info.total_size())
            if s.state_str == 'queued':
                color = 'reading'
                title_ = 'Waiting... {}'.format(title)
            elif s.state_str == 'checking files':
                color = 'reading'
                title_ = 'Checking files... {}'.format(title)
                self._filesize_prev = filesize
            elif s.state_str == 'downloading':
                title_ = '{}'.format(title)
                cw.setFileSize(filesize)
                cw.setSpeed(self.size.speed)
                cw.setUploadSpeed(self.size_upload.speed)
            elif s.state_str == 'seeding':
                cw.setFileSize(filesize)
                if not cw.seeding:
                    return 'abort'
                seeding = True
                title_ = 'Seeding... {}'.format(title)
                cw.setSpeed(self.size_upload.speed)
            elif s.state_str == 'reading':
                color = 'reading'
                title_ = 'Reading... {}'.format(title)
            elif s.state_str == 'finished':
                return 'abort'
            else:
                title_ = '{}... {}'.format(s.state_str.capitalize(), title)
            cw.setTitle(title_, update_filter=False)
            cw.setColor(color)
            self._seeding = seeding
        else:
            self.print_('abort')
            if cw:
                cw._torrent_s = None
            return 'abort'


@utils.actions('torrent')
def actions(cw):
    if cw.type != 'torrent':
        return
    items = [item for item in cw.listWidget().selectedItems() if item.type == 'torrent']
    seeding = int(all(item._seeding for item in items)) * 2
    if not seeding:
        seeding = int(all(item._seeding is False for item in items))
        if not seeding:
            seeding = 0 if all(item._seeding is None for item in items) else None
    if seeding is None:
        mix_seeding = any(item._seeding for item in items)
        mix_no_seeding = any(item._seeding is False for item in items)
        mix_pref = any(item._seeding is None for item in items)
    else:
        mix_seeding = mix_no_seeding = mix_pref = False
    return [
        {'icon': 'list', 'text': '파일 목록', 'clicked': cw.showFiles},
        {'icon': 'peer', 'text': 'Peers', 'clicked': cw.showPeers},
        {'icon': 'tracker', 'text': '트래커 수정', 'clicked': cw.editTrackers},
        {'text':'-'},
        {'text': '시딩', 'clicked': lambda:cw.setSeedings(True), 'checkable': True, 'checked': seeding==2, 'group': 'seeding', 'mixed': mix_seeding},
        {'text': '시딩 하지 않음', 'clicked': lambda:cw.setSeedings(False), 'checkable': True, 'checked': seeding==1, 'group': 'seeding', 'mixed': mix_no_seeding},
        {'text': '설정을 따름', 'clicked': lambda:cw.setSeedings(None), 'checkable': True, 'checked': seeding==0, 'group': 'seeding', 'mixed': mix_pref},
        ]
