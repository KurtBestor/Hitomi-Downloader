#coding: utf8
import downloader
import ytdl
from utils import Downloader, LazyUrl, try_n, format_filename, get_ext, Session, get_print, get_resolution, get_max_range, print_error, json
from io import BytesIO
from m3u8_tools import M3u8_stream
import ree as re
import errors
import utils
import os



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
            url = f'https://www.twitch.tv/videos/{url}'
            self.url = url
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        url = url.replace('m.twitch.tv', 'www.twitch.tv')
        if re.search(r'/(videos|clips)\?filter=', url):
            return url.strip('/')
        url = url.split('?')[0].strip('/')
        filter = cls.get_filter(url)
        if filter == 'live':
            url = '/'.join(url.split('/')[:4])
        return url

    @classmethod
    def get_filter(cls, url):
        if url.count('/') == 3:
            if 'www.twitch.tv' in url or '//twitch.tv' in url:
                filter = 'live'
            else:
                filter = None
        elif url.count('/') == 4:
            filter = re.find(r'filter=([0-9a-zA-Z_]+)', url) or re.find(r'[0-9a-zA-Z_]+', url.split('/')[-1])
            if filter is not None and filter.isdigit():
                filter = None
        else:
            filter = None
        if filter in ['about', 'schedule']:
            filter = 'live'
        return filter

    def read(self):
        if '/directory/' in self.url.lower():
            raise errors.Invalid(f'[twitch] Directory is unsupported: {self.url}')

        filter = self.get_filter(self.url)

        if filter is None:
            video = Video(self.url, self.session, self.cw)
            video.url()
            self.urls.append(video.url)
            self.title = video.title
        elif filter == 'live':
            video = Video(self.url, self.session, self.cw, live=True)
            video.url()
            self.urls.append(video.url)
            self.title = os.path.splitext(video.filename)[0].replace('：', ':')
        elif filter == 'clips':
            info = get_videos(self.url, cw=self.cw)
            video = self.process_playlist('[Clip] {}'.format(info['name']), info['videos'])
        else:
            raise NotImplementedError(filter)

        self.artist = video.artist

        thumb = BytesIO()
        downloader.download(video.url_thumb, buffer=thumb) #5418

        self.setIcon(thumb)
        if filter == 'live':
            d = {}
            d['url'] = self.url
            d['title'] = self.artist
            d['thumb'] = thumb.getvalue()
            utils.update_live(d, self.cw)


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
        video = Video(e['url'], self.session, cw)
        video.id = int(e['id'])
        videos.append(video)
        if 'name' not in info:
            info['name'] = ydl.extract_info(e['url'])['creator']
    if not videos:
        raise Exception('no videos')
    info['videos'] = sorted(videos, key=lambda video: video.id, reverse=True)
    return info


def alter(seg, cw):
    if 'amazon' in seg.raw.title.lower():
        get_print(cw)('strip ads')
        return []
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

    def __init__(self, url, session, cw, live=False):
        self.url = LazyUrl(url, self.get, self)
        self.session = session
        self.cw = cw
        self._live = live

    @try_n(4)
    def get(self, url):
        print_ = get_print(self.cw)
        session = self.session
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
        id = info['display_id']

        if self._live:
            self.title = info['description']
            if utils.SD['twitch']['strip_ads']:
                video = M3u8_stream(video, n_thread=4, alter=alter, session=session)
            else:
                video = utils.LiveStream(video, headers=video_best.get('http_headers', {}))
            ext = '.mp4'
        else:
            self.title = info['title']
            if ext.lower() == '.m3u8':
                video = M3u8_stream(video, n_thread=4, alter=alter, session=session)
                ext = '.mp4'
        self.filename = format_filename(self.title, id, ext, artist=self.artist, live=self._live)
        self.url_thumb = info['thumbnail']
        self._url = video
        return self._url


def get_streamer_name(url):
    session = Session()
    session.purge('twitch')
    graphql_url = 'https://gql.twitch.tv/gql'
    headers = {
        'Client-ID': 'kimne78kx3ncx6brgo4mv6wki5h1ko',
        'Content-Type': 'application/json',
    }
    session.headers.update(headers)

    id = url.split('/')[3]

    payload = {'operationName': 'PlaybackAccessToken_Template', 'query': 'query PlaybackAccessToken_Template($login: String!, $isLive: Boolean!, $vodID: ID!, $isVod: Boolean!, $playerType: String!) {  streamPlaybackAccessToken(channelName: $login, params: {platform: "web", playerBackend: "mediaplayer", playerType: $playerType}) @include(if: $isLive) {    value    signature   authorization { isForbidden forbiddenReasonCode }   __typename  }  videoPlaybackAccessToken(id: $vodID, params: {platform: "web", playerBackend: "mediaplayer", playerType: $playerType}) @include(if: $isVod) {    value    signature   __typename  }}', 'variables': {'isLive': True, 'login': id, 'isVod': False, 'vodID': '', 'playerType': 'site'}}
    r = session.post(graphql_url, json=payload)
    r.raise_for_status()
    data = r.json()
    value = json.loads(data['data']['streamPlaybackAccessToken']['value'])
    cid = value['channel_id']
    utils.log(data)

    payload = [{"operationName":"EmotePicker_EmotePicker_UserSubscriptionProducts","variables":{"channelOwnerID":f"{cid}"},"extensions":{"persistedQuery":{"version":1,"sha256Hash":"71b5f829a4576d53b714c01d3176f192cbd0b14973eb1c3d0ee23d5d1b78fd7e"}}}]
    r = session.post(graphql_url, json=payload)
    r.raise_for_status()
    data = r.json()
    return data[0]['data']['user']['displayName']


class Live_twitch(utils.Live):
    type = 'twitch'

    @classmethod
    def is_live(cls, url):
        return Downloader.get('twitch').get_filter(url) == 'live'

    @classmethod
    def check_live(cls, url, info=None):
        if info is not None:
            try:
                info['title'] = get_streamer_name(url)
            except Exception as e:
                utils.log(print_error(e))
        ydl = ytdl.YoutubeDL(type='twitch')
        try:
            ydl.extract_info(url)
            return True
        except Exception as e:
            print(e)
            return False
