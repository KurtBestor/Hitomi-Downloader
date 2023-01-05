import downloader
import downloader_v3
from utils import Soup, LazyUrl, Downloader, query_url, get_outdir, get_print, cut_pair, format_filename, clean_title, get_resolution, try_n, Session, uuid
import hashlib, json
import os
from io import BytesIO
import ffmpeg
from translator import tr_
import math
import ree as re
import utils
import ytdl
from io import BytesIO
import constants
from putils import DIR
import threading
import errors
_VALID_URL = r'''(?x)
                    https?://
                        (?:(?:www|bangumi)\.)?
                        bilibili\.(?:tv|com)/
                        (?:
                            (?:
                                video/[aA][vV]|
                                anime/(?P<anime_id>\d+)/play\#
                            )(?P<id_bv>\d+)|
                            video/[bB][vV](?P<id>[^/?#&]+)
                        )
                    '''


class Video:

    def __init__(self, f_video, f_audio, referer, session, cw=None):
        print_ = get_print(cw)
        self.f_video = f_video
        self.f_audio = f_audio
        self.referer = referer
        self.session = session
        self.cw = cw
        self.url = LazyUrl(None, lambda _: f_video['url'], self, pp=self.pp)
        if f_audio:
            def f():
                audio = f_audio['url']
                path = os.path.join(DIR, f'{uuid()}_a.tmp')
                if cw is not None:
                    cw.trash_can.append(path)
                if constants.FAST:
                    downloader_v3.download(audio, session=self.session, chunk=1024*1024, n_threads=2, outdir=os.path.dirname(path), fileName=os.path.basename(path), customWidget=cw, overwrite=True)
                else:
                    downloader.download(audio, session=self.session, outdir=os.path.dirname(path), fileName=os.path.basename(path), customWidget=cw, overwrite=True)
                self.audio_path = path
                print_('audio done')
            self.thread_audio = threading.Thread(target=f, daemon=True)
            self.thread_audio.start()

    def pp(self, filename):
        if self.f_audio:
            self.thread_audio.join()
            ffmpeg.merge(filename, self.audio_path, cw=self.cw)
        return filename


# 1804
@try_n(2)
def fix_url(url, cw=None):
    print_ = get_print(cw)
    if '?' in url:
        tail = url.split('?')[1]
    else:
        tail = None
    html = downloader.read_html(url, methods={'requests'})
    soup = Soup(html)
    err = soup.find('div', class_='error-text')
    if err:
        raise errors.Invalid('{}: {}'.format(err.text.strip(), url))
    meta = soup.find('meta', {'itemprop': 'url'})
    if meta:
        url_new = meta.attrs['content']
        if tail:
            url_new = '{}?{}'.format(url_new, tail)
        print_('redirect: {} -> {}'.format(url, url_new))
    else:
        url_new = url
        print_('no redirect')
    return url_new



class Downloader_bili(Downloader):
    type = 'bili'
    URLS = [r'regex:'+_VALID_URL]
    lock = True
    detect_removed = False
    detect_local_lazy = False
    display_name = 'bilibili'
    single = True
    ACCEPT_COOKIES = [r'(.*\.)?bilibili\.com']

    def init(self):
        self.url = fix_url(self.url, self.cw)
        if 'bilibili.com' not in self.url.lower():
            self.url = 'https://www.bilibili.com/video/{}'.format(self.url)
        self.url = self.url.replace('m.bilibili', 'bilibili')
        self.session = Session()

    @property
    def id_(self):
        mobj = re.match(_VALID_URL, self.url)
        video_id = mobj.group('id')
        anime_id = mobj.group('anime_id')
        return video_id

    def read(self):
        self.print_('CURRENT_QUALITY: {}'.format(self.session.cookies.get('CURRENT_QUALITY', domain='.bilibili.com')))
        video, info = get_video(self.url, self.session, self.cw)
        self.urls.append(video.url)

        thumb = BytesIO()
        downloader.download(info['url_thumb'], buffer=thumb)
        self.setIcon(thumb)
        title = info['title']
        title = format_filename(title, self.id_, '.mp4')[:-4]
        n = int(math.ceil(8.0 / len([None])))
        self.print_('n_threads: {}'.format(n))
        self.enableSegment(n_threads=n, overwrite=True)
        self.title = title
        ext = info['ext']
        video.filename = '{}{}'.format(title, ext)


@try_n(4)
def get_video(url, session, cw=None):
    print_ = get_print(cw)

    mobj = re.match(_VALID_URL, url)
    video_id = mobj.group('id')
    anime_id = mobj.group('anime_id')
    print(video_id, anime_id)
    print_ = get_print(cw)

    options = {
            #'noplaylist': True, #5562
            #'extract_flat': True,
            'playlistend': 1,
            }
    ydl = ytdl.YoutubeDL(options, cw=cw)
    info = ydl.extract_info(url)

    #5562
    entries = info.get('entries')
    if entries:
        info.update(entries[0])

    fs = info['formats']
    res = max(get_resolution(), min(f.get('height', 0) for f in fs))
    print_(f'res: {res}')
    fs = [f for f in fs if f.get('height', 0) <= res]
    for f in fs:
        print_(f"{f['format']} - {f['url']}")

    f_video = sorted(fs, key=lambda f:(f.get('height', 0), f.get('vbr', 0)))[-1]
    print_('video: {}'.format(f_video['format']))

    if f_video.get('abr'):
        f_audio = None
    else:
        fs_audio = sorted([f_audio for f_audio in fs if f_audio.get('abr')], key=lambda f:f['abr'])
        if fs_audio:
            f_audio = fs_audio[-1]
        else:
            raise Exception('no audio')
    print_('audio: {}'.format(f_audio['format']))

    video = Video(f_video, f_audio, url, session, cw)
    title = info['title']
    url_thumb = info['thumbnail']
    ext = info['ext']
    if not ext.startswith('.'):
        ext = '.' + ext

    session.headers.update(info.get('http_headers', {}))

    info = {
        'title': clean_title(title),
        'url_thumb': url_thumb,
        'ext': ext,
        }
    return video, info
