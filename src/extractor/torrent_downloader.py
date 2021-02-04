from utils import Downloader, speed_text, clean_title
import constants, os, downloader
from size import Size
try:
    import torrent
except Exception as e:
    torrent = None
MAX_PBAR = 1000000
TIMEOUT = 300
    

@Downloader.register
class Downloader_torrent(Downloader):
    type = 'torrent'
    URLS = [r'regex:^magnet:\?', r'regex:\.torrent$']
    single = True
    update_filesize = False
    _info = None
    _name = None
    _filesize_prev = 0
    MAX_PARALLEL = 14

    def init(self):
        global torrent
        if torrent is None:
            import torrent

    @classmethod
    def key_id(cls, url):
        id_, e = torrent.key_id(url)
        if e:
            print(e)
        return id_

    @property
    def name(self):
        if self._name is None:
            self._name = clean_title(self._info.name())
        return self._name

    def read(self):
        cw = self.cw
        try:
            self._info = torrent.get_info(self.url, cw, timeout=TIMEOUT)
        except Exception as e:
            return self.Invalid('Faild to read metadata: {}'.format(self.url), e, fail=True)
        hash_ = self._info._hash.hex()
        self.print_('Hash: {}'.format(hash_))
        self.url = 'magnet:?xt=urn:btih:{}'.format(hash_)#

        self.urls = [self.url]
        self.title = self.name
        files = torrent.get_files(self._info)
        if not files:
            raise Exception('No files')
        cw.single = self.single = len(files) == 1
        for file in files:
            filename = os.path.join(self.dir, file)
            cw.imgs.append(filename)

    def start_(self):
        cw = self.cw
        self.read()
        if self.status == 'stop':
            return True
        cw.dir = self.dir
        cw.urls = self.urls
        self.size = Size()
        cw.setColor('downloading')
        cw.pbar.setMaximum(MAX_PBAR)
        cw.pbar.setFormat('%p%')
        cw.downloader_pausable = True
        self.update_tools_buttons()
        if cw.paused:
            data = cw.pause_data
            self._filesize_prev = data['filesize']
            cw.paused = False
            cw.pause_lock = False
            self.update_tools_buttons()
        torrent.download(self._info, save_path=self.dir, callback=self.callback)
        if cw.alive:
            cw.setSpeed('')
        if cw.pause_lock and cw.pbar.value() < cw.pbar.maximum():
            cw.pause_data = {'type': self.type, 'url': self.url, 
               'filesize': self._filesize_prev}
            cw.paused = True
            cw.pause_lock = False
            self.update_tools_buttons()
            return True
        self.title = self.name
        if not self.single:
            cw.pbar.setMaximum(len(cw.imgs))

    def callback(self, h, s, alerts):
        cw = self.cw
        try:
            title = self.name
        except Exception as e:
            print(e)
            title = self.url

        if cw.alive and not cw.pause_lock:
            if self._info is not None:
                sizes = torrent.get_progress(h, self._info)
                for i, (file, size) in enumerate(zip(cw.names, sizes)):
                    file = os.path.realpath(file.replace('\\\\?\\', ''))
                    if file in cw.dones:
                        continue
                    if size[0] == size[1]:
                        cw.dones.add(file)
                        file = constants.compact(file).replace('\\', '/')
                        files = file.split('/')
                        file = (u' / ').join(files[1:])
                        msg = (u'Completed: {}').format(file)
                        self.print_(msg)
                        if i == 0:
                            for try_ in range(4):
                                if cw.setIcon(cw.imgs[0]):
                                    break

            filesize = s.total_done
            if s.state_str in ('downloading', ):
                d_size = filesize - self._filesize_prev
                self._filesize_prev = filesize
                self.size += d_size
                downloader.total_download_size += d_size
            cw.pbar.setValue(s.progress * MAX_PBAR)
            if s.state_str == 'queued':
                title_ = (u'Waiting... {}').format(title)
            elif s.state_str == 'checking files':
                title_ = (u'Checking files... {}').format(title)
                self._filesize_prev = filesize
            elif s.state_str == 'downloading':
                title_ = (u'{}    (p: {}, s: {})').format(title, s.num_peers, s.num_seeds)
                cw.setFileSize(filesize)
                text = self.size.speed_text()
                cw.setSpeed(text)
            elif s.state_str == 'seeding':
                title_ = (u'{}').format(title)
                cw.setFileSize(filesize)
            else:
                title_ = (u'{}... {}').format(s.state_str.capitalize(), title)
            cw.setTitle(title_, update_filter=False)
        else:
            return 'abort'
