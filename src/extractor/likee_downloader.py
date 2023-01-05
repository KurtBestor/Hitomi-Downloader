import downloader
from utils import Session, Downloader, get_ext, LazyUrl, get_print, check_alive
import ree as re
import json
from io import BytesIO
from translator import tr_



class Downloader_likee(Downloader):
    type = 'likee'
    URLS = ['likee.video']
    single = True
    display_name = 'Likee'

    def init(self):
        self.session = Session()

    def read(self):
        info = get_info(self.url, self.session, self.cw)
        self.print_('type: {}'.format(info['type']))
        self.artist = info['artist']

        if info['type'] != 'single':
            video = self.process_playlist(info['title'], info['videos'])
        else:
            video = info['videos'][0]
            video.url()
            self.urls.append(video.url)
            self.title = info['title']

        thumb = BytesIO()
        downloader.download(video.url_thumb, referer=self.url, buffer=thumb)
        self.setIcon(thumb)


def get_info(url, session, cw=None):
    print_ = get_print(cw)

    info = {}
    info['videos'] = []

    if '/video/' in url:
        info['type'] = 'single'
        video = Video(url, session)
        video.url()
        info['videos'].append(video)
        info['title'] = video.id_
        info['artist'] = video.artist
        return info

    info['type'] = 'channel'
    html = downloader.read_html(url, session=session)
    data_raw = html.split('window.data = ')[1].split('};')[0]+'}'
    data = json.loads(data_raw)
    info['uid'] = data['userinfo']['uid']
    info['username'] = data['userinfo']['yyuid']
    info['artist'] = data['userinfo']['nick_name']
    info['title'] = '{} (likee_{})'.format(info['artist'], info['username'])

    lastPostId = ''
    urls = set()
    while True:
        check_alive(cw)
        url_api = 'https://likee.video/official_website/VideoApi/getUserVideo'
        r = session.post(url_api, data={'uid': info['uid'], 'count': '30', 'lastPostId': lastPostId})
        data = json.loads(r.text)

        videos = data['data']['videoList']
        if not videos:
            break

        for data in videos:
            url_post = 'https://likee.video/@{}/video/{}'.format(data['likeeId'], data['postId'])
            if url_post in urls:
                print_('duplicate: {}'.format(url_post))
                continue
            urls.add(url_post)
            video = Video(url_post, session, data)
            video.url()
            info['videos'].append(video)
            lastPostId = data['postId']

        msg = '{} {} - {}'.format(tr_('읽는 중...'), info['title'], len(info['videos']))
        if cw:
            cw.setTitle(msg)
        else:
            print(msg)

    return info


class Video:
    def __init__(self, url, session, data=None):
        self.id_ = re.find('/video/([0-9]+)', url, err='no id')
        self._session = session
        self._data = data
        self.url = LazyUrl(url, self.get, self)

    def get(self, url):
        if self._data:
            video = self._data
        else:
            url_api = 'https://likee.video/official_website/VideoApi/getVideoInfo'
            r = self._session.post(url_api, data={'postIds': str(self.id_)})

            data = json.loads(r.text)
            video = data['data']['videoList'][0]

        url_video = video['videoUrl']
        self.url_thumb = video['coverUrl']
        self.artist = video['nickname']
        ext = get_ext(url_video)
        self.title = self.id_
        self.filename = '{}{}'.format(self.id_, ext)

        return url_video
