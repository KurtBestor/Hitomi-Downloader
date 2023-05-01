from utils import Downloader, LazyUrl, clean_title, Session, get_ext
import utils
from m3u8_tools import playlist2stream, M3u8_stream
import os
from hashlib import md5
from translator import tr_
DEFAULT_N_THREAD = 2


def suitable(url):
    ext = get_ext(url).lower()
    return ext in ('.m3u8', '.mpd')


class Downloader_m3u8(Downloader):
    type = 'm3u8'
    URLS = [suitable]
    single = True
    display_name = 'M3U8'

    @classmethod
    def fix_url(cls, url):
        if '://' not in url:
            url = 'http://' + url
        return url

    def read(self):
        n_thread = self.cw.format or DEFAULT_N_THREAD
        self.print_('n_thread: {}'.format(n_thread))
        video = Video(self.url, n_thread)
        self.urls.append(video.url)
        self.title = os.path.splitext(os.path.basename(video.filename))[0].replace(b'\xef\xbc\x9a'.decode('utf8'), ':')


class Video:
    def __init__(self, url, n_thread):
        session = Session()
        session.purge([rf'(.*\.)?{utils.domain(url)}'])
        if get_ext(url).lower() == '.mpd':
            def m():
                hdr = session.headers.copy()
                hdr['Referer'] = url
                return utils.LiveStream(url, headers=hdr)
            ms = [m]
        else:
            ms = [
                lambda: playlist2stream(url, n_thread=n_thread, session=session),
                lambda: M3u8_stream(url, n_thread=n_thread, session=session),
                ]
        for m in ms:
            try:
                m = m()
                break
            except Exception as e:
                e_ = e
        else:
            raise e_
        if getattr(m, 'live', None) is not None: #5110
            m = m.live
            live = True
        else:
            live = False
        self.url = LazyUrl(url, lambda _: m, self)
        self.title = os.path.splitext(os.path.basename(url).split('?')[0])[0][:50]
        self.id_ = md5(url.encode('utf8')).hexdigest()[:8]
        tail = f' ({self.id_}).mp4'
        if live: #5110
            from datetime import datetime
            now = datetime.now()
            tail = ' ' + clean_title(now.strftime('%Y-%m-%d %H:%M')) + tail
        self.filename = clean_title(self.title, n=-len(tail)) + tail


import selector
@selector.options('m3u8')
def options(urls):
    def f(urls):
        n_thread, ok = utils.QInputDialog.getInt(Downloader.mainWindow, tr_('Set number of threads'), tr_('Number of threads?'), value=DEFAULT_N_THREAD, min=1, max=4, step=1)
        if not ok:
            return
        return n_thread
    return [
        {'text': 'Set number of threads...', 'format': f},
        ]
