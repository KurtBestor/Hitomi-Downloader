#coding: utf8
import downloader
import ytdl
from utils import Downloader, get_outdir, Soup, LazyUrl, try_n, compatstr, format_filename, get_ext, clean_title, Session, cut_pair, json_loads, get_print
from io import BytesIO
from m3u8_tools import M3u8_stream
import ree as re
from translator import tr_
import errors


@Downloader.register
class Downloader_twitch(Downloader):
    type = 'twitch'
    URLS = ['twitch.tv']
    single = True

    def init(self):
        url = self.url
        if 'twitch.tv' in url:
            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'https://' + url
            self.url = url
        else:
            url = 'https://www.twitch.tv/videos/{}'.format(url)
            self.url = url

    @classmethod
    def fix_url(cls, url):
        if re.search(r'/(videos|clips)\?filter=', url):
            return url.strip('/')
        return url.split('?')[0].strip('/')

    def read(self):
        if '/directory/' in self.url.lower():
            return self.Invalid('[twitch] Directory is unsupported: {}'.format(self.url))
            
        if self.url.count('/') == 3:
            if 'www.twitch.tv' in self.url or '//twitch.tv' in self.url:
                filter = 'videos'
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
        elif filter == 'clips':
            info = get_videos(self.url, cw=self.cw)
            video = self.process_playlist('[Clip] {}'.format(info['name']), info['videos'])
        else:
            raise NotImplementedError(filter)

        self.setIcon(video.thumb)
            

@try_n(2)
def get_videos(url, cw=None):
    print_ = get_print(cw)
    info = {}
    user_id = re.find(r'twitch.tv/([^/?]+)', url, err='no user_id')
    print(user_id)
    session = Session()
    r = session.get(url)
    s = cut_pair(re.find(r'headers *: *({.*)', r.text, err='no headers'))
    print(s)
    headers = json_loads(s)

    payload = [
        {
            'operationName': 'ClipsCards__User',
            'variables': {
                'login': user_id,
                'limit': 20,
                'criteria': {'filter': 'ALL_TIME'}},
            'extensions': {'persistedQuery': {'version': 1, 'sha256Hash': 'b73ad2bfaecfd30a9e6c28fada15bd97032c83ec77a0440766a56fe0bd632777'}},
            }
        ]
    videos = []
    cursor = None
    cursor_new = None
    while True:
        if cursor:
            payload[0]['variables']['cursor'] = cursor
        r = session.post('https://gql.twitch.tv/gql', json=payload, headers=headers)
        #print(r)
        data = r.json()
        for edge in data[0]['data']['user']['clips']['edges']:
            url_video = edge['node']['url']
            info['name'] = edge['node']['broadcaster']['displayName']
            video = Video(url_video, cw)
            video.id = int(edge['node']['id'])
            videos.append(video)
            cursor_new = edge['cursor']
        print_('videos: {} / cursor: {}'.format(len(videos), cursor))
        if cursor == cursor_new:
            print_('same cursor')
            break
        if cursor_new is None:
            break
        cursor = cursor_new
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
    

class Video(object):
    _url = None

    def __init__(self, url, cw):
        self.url = LazyUrl(url, self.get, self)
        self.cw = cw

    @try_n(4)
    def get(self, url):
        print_ = get_print(self.cw)
        if self._url:
            return self._url
        ydl = ytdl.YoutubeDL(cw=self.cw)
        try:
            info = ydl.extract_info(url)
        except Exception as e:
            ex = type(ytdl.get_extractor(url))(ydl)
            _download_info = getattr(ex, '_download_info', None)
            if _download_info is not None:
                vod_id = ex._match_id(url)
                info = _download_info(vod_id)
                print_(info)
            raise
        video_best = info['formats'][-1]
        video = video_best['url']
        
        ext = get_ext(video)
        self.title = info['title']
        id = info['display_id']

        if ext.lower() == '.m3u8':
            video = M3u8_stream(video, n_thread=4, alter=alter)
            ext = '.mp4'
        self.filename = format_filename(self.title, id, ext)
        self.url_thumb = info['thumbnail']
        self.thumb = BytesIO()
        downloader.download(self.url_thumb, buffer=self.thumb)
        self._url = video
        return self._url
