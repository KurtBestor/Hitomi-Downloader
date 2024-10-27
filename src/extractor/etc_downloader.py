import downloader
import ytdl
from utils import Downloader, Session, try_n, LazyUrl, get_ext, format_filename, get_print, get_resolution, print_error, cut_pair, json
from io import BytesIO
import ree as re
from m3u8_tools import playlist2stream, M3u8_stream
import utils
import ffmpeg
import clf2
import os



class Downloader_etc(Downloader):
    type = 'etc'
    URLS = ['thisvid.com'] #5153
    single = True
    MAX_PARALLEL = 8
    display_name = 'Etc'
    PRIORITY = 10

    @try_n(2)
    def read(self):
        self.session = Session()
        name = ytdl.get_extractor_name(self.url)
        self.print_('extractor: {}'.format(name))
        if name == 'ixigua': #6290
            clf2.solve(self.url, session=self.session)
        #if name == 'generic':
        #    raise NotImplementedError()

        video = get_video(self.url, self.session, self.cw)

        if video.artist:
            self.artist = video.artist

        self.print_('url_thumb: {}'.format(video.url_thumb))
        self.setIcon(video.thumb)
        if video.header.lower() not in ['yourporn']:
            self.enableSegment()#
        if isinstance(video.url(), M3u8_stream):
            self.disableSegment()

        self.urls.append(video.url)

        self.title = os.path.splitext(video.filename)[0].replace('：', ':')


def int_or_none(s):
    try:
        return int(s)
    except:
        return None


def format_(f):
    if f is None:
        return 'None'
    return 'format:{} - resolution:{} - vbr:{} - audio:{} - url:{}'.format(f['format'], f['_resolution'], f['_vbr'], f['_audio'], f['url'])


class UnSupportedError(Exception):pass


def get_video(url, session, cw, ie_key=None):
    print_ = get_print(cw)
    try:
        video = _get_video(url, session, cw, ie_key, allow_m3u8=True)
        if isinstance(video, Exception):
            raise video
        if isinstance(video.url(), M3u8_stream):
            c = video.url().urls[0][1].download(cw)
            if not c:
                raise Exception('invalid m3u8')
        return video
    except Exception as e:
        if isinstance(e, UnSupportedError):
            raise e
        print_(print_error(e))
        return _get_video(url, session, cw, ie_key, allow_m3u8=False)


def extract_info_spankbang(url, session, cw): # temp fix
    print_ = get_print(cw)
    soup = downloader.read_soup(url, session=session)

    for script in soup.findAll('script'):
        script = script.string
        if script and 'var stream_data'in script:
            s = cut_pair(script.split('var stream_data')[-1].strip(' \t=').replace("'", '"'))
            break
    else:
        raise Exception('no stream_data')

    info = {}
    info['url'] = url
    info['title'] = soup.find('h1').text.strip()
    info['id'] = re.find(r'spankbang\.com/([^/]+)', soup.find('meta', {'property': 'og:url'})['content'], err='no id')
    info['thumbnail'] = soup.find('meta', {'property': 'og:image'})['content']
    info['formats'] = []
    data = json.loads(s)
    for res, item in data.items():
        if res == 'main':
            continue
        if item and isinstance(item,  list):
            item = item[0]
        else:
            continue
        ext = get_ext_(item, session, url)
        res = {'4k': '2160p', '8k': '4320p', '16k': '8640p'}.get(res, res)
        f = {'url': item, 'format': res}
        info['formats'].append(f)

    return info


@try_n(2)
def _get_video(url, session, cw, ie_key=None, allow_m3u8=True):
    print_ = get_print(cw)
    print_('get_video: {}, {}'.format(allow_m3u8, url))
    options = {
        'noplaylist': True,
        #'extract_flat': True,
        'playlistend': 1,
        'writesubtitles': True,
        }
    if ytdl.get_extractor_name(url) == 'spankbang':
        info = extract_info_spankbang(url, session, cw)
    else:
        ydl = ytdl.YoutubeDL(options, cw=cw)
        try:
            info = ydl.extract_info(url)
        except Exception as e:
            if 'ERROR: Unsupported URL' in str(e):
                return UnSupportedError(str(e))
            raise e
    if not ie_key:
        ie_key = ytdl.get_extractor_name(url)
    info['ie_key'] = ie_key
    url_new = info.get('url')
    formats = info.get('formats', [])

    if not formats and (info.get('entries') or 'title' not in info):
        if 'entries' in info:
            entry = info['entries'][0]
            url_new = entry.get('url') or entry['webpage_url']
        if url_new != url:
            return get_video(url_new, session, cw, ie_key=get_ie_key(info))

    session.headers.update(info.get('http_headers', {}))
    #session.cookies.update(ydl.cookiejar)

    if not formats:
        if url_new:
            f = {'url': url_new, 'format': ''}
            formats.append(f)

    fs = []
    for i, f in enumerate(formats):
        f['_index'] = i
        f['_resolution'] = int_or_none(re.find(r'([0-9]+)p', f['format'], re.I)) or f.get('height') or f.get('width') or int_or_none(f.get('quality')) or int(f.get('vcodec', 'none') != 'none') #5995
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

    f_video = filter_f(sorted(fs, key=lambda f:(f['_resolution'], int(bool(f['_audio'])), f['_vbr'], f['_index']), reverse=True)) #6072, #6118
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
        ext = get_ext(url)
    return ext


class Video:
    live = False

    def __init__(self, f, f_audio, info, session, referer, cw=None):
        self.f_audio = f_audio
        self.cw = cw
        print_ = get_print(cw)
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

        def foo():
            hdr = session.headers.copy()
            if referer:
                hdr['Referer'] = referer
            self.live = True
            return utils.LiveStream(self.url, headers=hdr, fragments=f.get('fragments') if ytdl.LIVE_FROM_START.get('etc') else None)

        if not ext:
            if f['_resolution']:
                ext = '.mp4'
            else:
                ext = '.mp3'

        if ext.lower() == '.m3u8':
            res = get_resolution() #4773
            ls = info.get('live_status')
            print_(f'live_status: {ls}')
            if ls == 'is_live':
                url = foo()
            else:
                try:
                    url = playlist2stream(self.url, referer, session=session)
                except:
                    url = M3u8_stream(self.url, referer=referer, session=session)
                print_(f'mpegts: {url.mpegts}')
                if url.ms or url.mpegts == False: #5110
                    url = url.live
                    url._cw = cw
            ext = '.mp4'
        elif ext.lower() == '.mpd': # TVer
            url = foo()
            ext = '.mp4'
        else:
            url = self.url
        self.url = LazyUrl(referer, lambda x: url, self, pp=self.pp)
        info_ext = info.get('ext')
        if info_ext == 'unknown_video': #vk
            info_ext = None
        self.filename = format_filename(title, self.id, info_ext or ext, header=self.header, live=self.live)

    def pp(self, filename):
        if self.f_audio:
            f = BytesIO()
            downloader.download(self.f_audio['url'], buffer=f, referer=self.referer, session=self.session)
            ffmpeg.merge(filename, f, cw=self.cw)
        utils.pp_subtitle(self, filename, self.cw)
        return filename
