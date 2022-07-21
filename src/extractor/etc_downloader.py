import downloader
import ytdl
from utils import Downloader, Session, try_n, LazyUrl, get_ext, format_filename, clean_title, get_print, get_resolution
from io import BytesIO
import ree as re
from m3u8_tools import playlist2stream, M3u8_stream
import utils
import ffmpeg



class Downloader_etc(Downloader):
    type = 'etc'
    URLS = []
    single = True
    MAX_PARALLEL = 8
    display_name = 'Etc'

    def init(self):
        self.session = Session()
        name = ytdl.get_extractor_name(self.url)
        self.print_('extractor: {}'.format(name))
        if name == 'generic':
            raise NotImplementedError()

    def read(self):
        video = get_video(self.url, self.session, self.cw)

        if video.artist:
            self.artist = video.artist

        self.urls.append(video.url)

        self.print_('url_thumb: {}'.format(video.url_thumb))
        self.setIcon(video.thumb)
        if video.header.lower() not in ['yourporn', 'spankbang']:
            self.enableSegment()#
        if isinstance(video.url(), M3u8_stream):
            self.disableSegment()

        self.title = '[{}] {}'.format(video.header, video.title)


def int_or_none(s):
    try:
        return int(s)
    except:
        return None


def format_(f):
    if f is None:
        return 'None'
    return 'format:{} - resolution:{} - vbr:{} - audio:{} - url:{}'.format(f['format'], f['_resolution'], f['_vbr'], f['_audio'], f['url'])


def get_video(url, session, cw, ie_key=None):
    print_ = get_print(cw)
    try:
        video = _get_video(url, session, cw, ie_key, allow_m3u8=True)
        if isinstance(video.url(), M3u8_stream):
            c = video.url().segs[0].download(cw)
            if not c:
                raise Exception('invalid m3u8')
        return video
    except Exception as e:
        print_(e)
        return _get_video(url, session, cw, ie_key, allow_m3u8=False)

@try_n(4)
def _get_video(url, session, cw, ie_key=None, allow_m3u8=True):
    print_ = get_print(cw)
    print_('get_video: {}, {}'.format(allow_m3u8, url))
    options = {
        'noplaylist': True,
        #'extract_flat': True,
        'playlistend': 1,
        }
    ydl = ytdl.YoutubeDL(options, cw=cw)
    info = ydl.extract_info(url)
    if not ie_key:
        ie_key = ytdl.get_extractor_name(url)
    info['ie_key'] = ie_key
    url_new = info.get('url')
    print('url: {} -> {}'.format(url, url_new))
    formats = info.get('formats', [])
    print(info.keys())

    if not formats and (info.get('entries') or 'title' not in info):
        if 'entries' in info:
            entry = info['entries'][0]
            url_new = entry.get('url') or entry['webpage_url']
        if url_new != url:
            return get_video(url_new, session, cw, ie_key=get_ie_key(info))

    session.headers.update(info.get('http_headers', {}))
    #session.cookies.update(ydl.cookiejar)

    if not formats:
        print('no formats')
        if url_new:
            f = {'url': url_new, 'format': ''}
            formats.append(f)

    fs = []
    for i, f in enumerate(formats):
        f['_index'] = i
        f['_resolution'] = int_or_none(re.find('([0-9]+)p', f['format'], re.IGNORECASE)) or f.get('height') or f.get('width') or int(f.get('vcodec', 'none') != 'none')
        f['_vbr'] = f.get('vbr') or 0
        f['_audio'] = f.get('abr') or f.get('asr') or int(f.get('acodec', 'none') != 'none')
        print_(format_(f))
        fs.append(f)

    #4773
    res = max(get_resolution(), min(f['_resolution'] for f in fs))
    print_(f'res: {res}')
    fs = [f for f in fs if f['_resolution'] <= res]

    if not fs:
        raise Exception('No videos')

    def filter_f(fs):
        for f in fs:
            if allow_m3u8:
                return f
            ext = get_ext_(f['url'], session, url)
            if ext.lower() != '.m3u8':
                return f
            print_('invalid url: {}'.format(f['url']))
        return list(fs)[0]#

    f_video = filter_f(reversed(sorted(fs, key=lambda f:(f['_resolution'], f['_vbr'], f['_index']))))
    print_('video0: {}'.format(format_(f_video)))

    if f_video['_audio']:
        f_audio = None
    else:
        fs_audio = sorted([f_audio for f_audio in fs if (not f_audio['_resolution'] and f_audio['_audio'])], key=lambda f:(f['_audio'], f['_vbr'], f['_index']))
        if fs_audio:
            f_audio = fs_audio[-1]
        else:
            try:
                print_('trying to get f_video with audio')
                f_video = filter_f(reversed(sorted([f for f in fs if f['_audio']], key=lambda f:(f['_resolution'], f['_index']))))
            except Exception as e:
                print_('failed to get f_video with audio: {}'.format(e))
            f_audio = None
    print_('video: {}'.format(format_(f_video)))
    print_('audio: {}'.format(format_(f_audio)))
    video = Video(f_video, f_audio, info, session, url, cw=cw)

    return video


def get_ie_key(info):
    ie_key = info.get('ie_key') or info['extractor']
    ie_key = ie_key.split(':')[0]
    if ie_key.lower().endswith('playlist'):
        ie_key = ie_key[:-len('playlist')]
    return ie_key


def get_ext_(url, session, referer):
    try:
        ext = downloader.get_ext(url, session, referer)
    except Exception as e:
        print(e)
        ext = get_ext(url)
    return ext


class Video(object):
    def __init__(self, f, f_audio, info, session, referer, cw=None):
        self.f_audio = f_audio
        self.cw = cw
        self.title = title = info['title']
        self.id = info['id']
        self.url = f['url']
        self.artist = info.get('uploader')
        self.header = utils.capitalize(get_ie_key(info))
        self.session = session
        self.referer = referer
        self.subs = ytdl.get_subtitles(info)

        self.url_thumb = info.get('thumbnail')
        self.thumb = BytesIO()
        if self.url_thumb:
            downloader.download(self.url_thumb, referer=referer, buffer=self.thumb, session=session)

        ext = get_ext_(self.url, session, referer)

        if not ext:
            print('empty ext')
            if f['_resolution']:
                ext = '.mp4'
            else:
                ext = '.mp3'

        if ext.lower() == '.m3u8':
            res = get_resolution() #4773
            try:
                url = playlist2stream(self.url, referer, session=session, n_thread=4, res=res)
            except:
                url = M3u8_stream(self.url, referer=referer, session=session, n_thread=4)
            ext = '.mp4'
        else:
            url = self.url
        self.url = LazyUrl(referer, lambda x: url, self, pp=self.pp)
        self.filename = format_filename(title, self.id, ext, header=self.header)

    def pp(self, filename):
        if self.f_audio:
            f = BytesIO()
            downloader.download(self.f_audio['url'], buffer=f, referer=self.referer, session=self.session)
            ffmpeg.merge(filename, f, cw=self.cw)
        utils.pp_subtitle(self, filename, self.cw)
        return filename
