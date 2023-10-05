#coding: utf8
import downloader
import ytdl
from utils import Downloader, get_outdir, Soup, LazyUrl, try_n, compatstr, format_filename, get_ext, clean_title, Session, get_print, get_resolution, get_max_range
from io import BytesIO
from m3u8_tools import M3u8_stream
import ree as re
from translator import tr_
import errors
import utils



class Downloader_twitch(Downloader):
    type = 'twitch'
    URLS = ['twitch.tv']
    single = True
    ACCEPT_COOKIES = [r'.*(twitch|ttvnw|jtvnw).*']

    def init(self):
        url = self.url
        if 'twitch.tv' in url:
            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'https://' + url
            self.url = url
        else:
            url = 'https://www.twitch.tv/videos/{}'.format(url)
            self.url = url
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        if re.search(r'/(videos|clips)\?filter=', url):
            return url.strip('/')
        return url.split('?')[0].strip('/')

    def read(self):
        if '/directory/' in self.url.lower():
            raise errors.Invalid('[twitch] Directory is unsupported: {}'.format(self.url))

        if self.url.count('/') == 3:
            if 'www.twitch.tv' in self.url or '//twitch.tv' in self.url:
                filter = 'live'
            else:
                filter = None
        elif self.url.count('/') == 4:
            filter = re.find(r'filter=([0-9a-zA-Z_]+)', self.url) or re.find(r'[0-9a-zA-Z_]+', self.url.split('/')[-1])
            if filter is not None and filter.isdigit():
                filter = None
        else:
            filter = None

        if filter is None:
            video = Video(self.url, self.cw)
            video.url()
            self.urls.append(video.url)
            self.title = video.title
        elif filter == 'live':
            video = Video(self.url, self.cw, live=True)
            video.url()
            self.urls.append(video.url)
            self.title = video.title
        elif filter == 'clips':
            info = get_videos(self.url, cw=self.cw)
            video = self.process_playlist('[Clip] {}'.format(info['name']), info['videos'])
        else:
            raise NotImplementedError(filter)

        self.artist = video.artist

        thumb = BytesIO()
        downloader.download(video.url_thumb, buffer=thumb) #5418

        self.setIcon(thumb)


@try_n(2)
def get_videos(url, cw=None):
    print_ = get_print(cw)
    print_(f'get_videos: {url}')
    info = {}
    options = {
            'extract_flat': True,
            'playlistend': get_max_range(cw),
            }
    videos = []
    ydl = ytdl.YoutubeDL(options, cw=cw)
    info = ydl.extract_info(url)
    for e in info['entries']:
        video = Video(e['url'], cw)
        video.id = int(e['id'])
        videos.append(video)
        if 'name' not in info:
            info['name'] = ydl.extract_info(e['url'])['creator']
    if not videos:
        raise Exception('no videos')
    info['videos'] = sorted(videos, key=lambda video: video.id, reverse=True)
    return info


def alter(seg):
    segs = []
    if '-muted' in seg.url:
        seg_ = seg.copy()
        seg_.url = seg.url.replace('-muted', '')
        segs.append(seg_)
    segs.append(seg)
    return segs


def extract_info(url, cw=None):
    print_ = get_print(cw)
    ydl = ytdl.YoutubeDL(cw=cw)
    try:
        info = ydl.extract_info(url)
    except Exception as e:
        ex = type(ytdl.get_extractor(url))(ydl)
        _download_info = getattr(ex, '_download_info', None)
        if _download_info is not None:
            vod_id = ex._match_id(url)
            info = _download_info(vod_id)
            print_(info)
        if 'HTTPError 403' in str(e):
            raise errors.LoginRequired()
        raise
    return info


class Video:
    _url = None

    def __init__(self, url, cw, live=False):
        self.url = LazyUrl(url, self.get, self)
        self.cw = cw
        self._live = live

    @try_n(4)
    def get(self, url):
        print_ = get_print(self.cw)
        if self._url:
            return self._url
        info = extract_info(url, self.cw)
        self.artist = info.get('creator') or info.get('uploader') #4953, #5031

        def print_video(video):
            #print_(video)#
            print_('{}[{}] [{}] [{}] {}'.format('LIVE ', video['format_id'], video.get('height'), video.get('tbr'), video['url']))

        videos = [video for video in info['formats'] if video.get('height')]

        videos = sorted(videos, key=lambda video:(video.get('height', 0), video.get('tbr', 0)), reverse=True)

        for video in videos:
            print_video(video)

        for video in videos:
            if video.get('height', 0) <= get_resolution(): #3723
                video_best = video
                break
        else:
            video_best = videos[-1]
        print_video(video)

        video = video_best['url']

        ext = get_ext(video)
        self.title = info['title']
        id = info['display_id']

        if self._live:
            video = utils.LiveStream(video, headers=video_best.get('http_headers', {}))
            ext = '.mp4'
        else:
            if ext.lower() == '.m3u8':
                video = M3u8_stream(video, n_thread=4, alter=alter)
                ext = '.mp4'
        self.filename = format_filename(self.title, id, ext, artist=self.artist)
        self.url_thumb = info['thumbnail']
        self._url = video
        return self._url
