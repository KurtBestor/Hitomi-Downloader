import downloader
from utils import Session, Downloader, get_outdir, try_n, Soup, format_filename, clean_title, get_print, get_resolution
import ree as re, json
from io import BytesIO
import os
from timee import time
from m3u8_tools import M3u8_stream
from random import randrange


class Video(object):

    def __init__(self, info, stream):
        self.info = info
        self.id = info['id']
        self.title = info['name']
        self.brand = info['brand']
        self.url = stream['url']
        self.url_thumb = info['poster_url']
        self.thumb = BytesIO()
        downloader.download(self.url_thumb, buffer=self.thumb)
        ext = os.path.splitext(self.url.split('?')[0].split('#')[0])[1]
        if ext.lower() == '.m3u8':
            print('read m3u8:', self.url)
            ext = '.mp4'
            self.url = M3u8_stream(self.url, n_thread=4)
        else:
            size = downloader.get_size(self.url)
            if size <= 0:
                raise Exception('Size is 0')
        self.filename = format_filename('[{}] {}'.format(self.brand, self.title), self.id, ext)

    def __repr__(self):
        return ('Video({})').format(self.id)



class Downloader_hanime(Downloader):
    type = 'hanime'
    URLS = ['hanime.tv/hentai-videos/', 'hanime.tv/videos/']
    single = True
    display_name = 'hanime.tv'

    def read(self):
        video, session = get_video(self.url, cw=self.cw)
        self.video = video

        self.urls.append(video.url)
        self.filenames[video.url] = video.filename

        self.setIcon(video.thumb)
        self.title = u'[{}] {}'.format(video.brand, video.title)


@try_n(8)
def get_video(url, session=None, cw=None):
    print_ = get_print(cw)
    if session is None:
        session = Session()
        session.headers['User-Agent'] = downloader.hdr['User-Agent']
    session.headers['X-Directive'] = 'api'
    html = downloader.read_html(url, session=session)
    soup = Soup(html)
    for script in soup.findAll('script'):
        script = script.text or script.string or ''
        data = re.find('window.__NUXT__=(.+)', script)
        if data is not None:
            data = data.strip()
            if data.endswith(';'):
                data = data[:-1]
            data = json.loads(data)
            break
    else:
        raise Exception('No __NUXT__')

    info = data['state']['data']['video']['hentai_video']
    query = info['slug']
    #url_api = 'https://members.hanime.tv/api/v3/videos_manifests/{}?'.format(query) # old
    url_api = 'https://hanime.tv/rapi/v7/videos_manifests/{}?'.format(query) # new
    print(url_api)
    hdr = {
        'x-signature': ''.join('{:x}'.format(randrange(16)) for i in range(32)),
        'x-signature-version': 'web2',
        'x-time': str(int(time())),
        }
    r = session.get(url_api, headers=hdr)
    print(r)
    data = json.loads(r.text)
    streams = []
    for server in data['videos_manifest']['servers']:
        streams += server['streams']

    streams_good = []
    for stream in streams:
        url_video = stream['url']
        if not url_video or 'deprecated.' in url_video:
            continue
        stream['height'] = int(stream['height'])
        streams_good.append(stream)

    if not streams_good:
        raise Exception('No video available')
    print('len(streams_good):', len(streams_good))
    res = get_resolution()

    def print_stream(stream):
        print_([stream['extension'], stream['height'], stream['filesize_mbs'], stream['url']])

    steams_filtered = []
    for stream in streams_good:
        print_stream(stream)
        if stream['height'] <= res: #3712
            steams_filtered.append(stream)

    if steams_filtered:
        stream = sorted(steams_filtered, key=lambda _: _['height'])[-1]
    else:
        stream = sorted(streams_good, key=lambda _: _['height'])[0]

    print_('Final stream:')
    print_stream(stream)
    return Video(info, stream), session
