from utils import Downloader, LazyUrl, clean_title
import utils
import os
from hashlib import md5
from translator import tr_
import ffmpeg
##DEFAULT_N_THREAD = 1


@Downloader.register
class Downloader_m3u8(Downloader):
    type = 'm3u8'
    URLS = ['.m3u8']
    single = True
    display_name = 'M3U8'
    
    @classmethod
    def fix_url(cls, url):
        if '://' not in url:
            url = 'http://' + url
        return url

    def read(self):
##        n_thread = self.cw.format or DEFAULT_N_THREAD
##        self.print_('n_thread: {}'.format(n_thread))
        video = Video(self.url, self.cw)
        self.urls.append(video.url)
        self.title = '{} ({})'.format(video.title, video.id_)


class Video(object):
    def __init__(self, url, cw):
        m = ffmpeg.Stream(url, cw=cw)
        self.url = LazyUrl(url, lambda _: m, self)
        self.title = os.path.splitext(os.path.basename(url))[0]
        self.id_ = md5(url.encode('utf8')).hexdigest()[:8]
        tail = ' ({}).mp4'.format(self.id_)
        self.filename = clean_title(self.title, n=-len(tail)) + tail


##import selector
##@selector.options('m3u8')
##def options():
##    def f(urls):
##        n_thread, ok = utils.QInputDialog.getInt(Downloader.mainWindow, tr_('Set number of threads'), tr_('Number of threads?'), value=DEFAULT_N_THREAD, min=1, max=4, step=1)
##        if not ok:
##            return
##        return n_thread
##    return [
##        {'text': 'Set number of threads...', 'format': f},
##        ]
