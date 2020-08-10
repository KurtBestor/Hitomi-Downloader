import downloader
from utils import Session, Downloader, get_outdir, try_n, Soup, compatstr
import ree as re, json
from io import BytesIO as IO
from fucking_encoding import clean_title
import os
from timee import time
import m3u8, ffmpeg
from m3u8_tools import M3u8_stream
from random import randrange
key = b'0123456701234567'


class Video(object):

    def __init__(self, info, stream, format):
        self.info = info
        self.id = info['id']
        self.title = clean_title(info['name'])
        self.brand = info['brand']
        self.url = stream['url']
        self.url_thumb = info['poster_url']
        self.thumb = IO()
        downloader.download(self.url_thumb, buffer=self.thumb)
        format = format.replace('title', '###title').replace('id', '###id')
        title = format.replace('###title', self.title).replace('###id', (u'{}').format(self.id))
        ext = os.path.splitext(self.url.split('?')[0].split('#')[0])[1]
        if ext.lower() == '.m3u8':
            print('read m3u8:', self.url)
            ext = '.mp4'
            self.url = M3u8_stream(self.url, deco=decrypt, n_thread=4)
        else:
            size = downloader.get_size(self.url)
            if size <= 0:
                raise Exception('Size is 0')
        self.filename = clean_title(u'[{}] {}{}'.format(self.brand, title, ext))

    def __repr__(self):
        return ('Video({})').format(self.id)


@Downloader.register
class Downloader_hanime(Downloader):
    type = 'hanime'
    URLS = ['hanime.tv/hentai-videos/', 'hanime.tv/videos/']
    single = True

    def init(self):
        if self.url.startswith('hanime_'):
            self.url = self.url.replace('hanime_', '', 1)

    @property
    def id(self):
        return self.url

    def read(self):
        cw = self.customWidget
        ui_setting = self.ui_setting
        format = compatstr(ui_setting.youtubeFormat.currentText()).lower().strip()
        video, session = get_video(self.url, format)
        self.video = video
        
        self.urls.append(video.url)
        self.filenames[video.url] = video.filename

        self.setIcon(video.thumb)
        self.title = u'[{}] {}'.format(video.brand, video.title)


@try_n(8)
def get_video(url, format='title', session=None):
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
        streams_good.append(stream)

    if not streams_good:
        raise Exception('No video available')
    print('len(streams_good):', len(streams_good))
    for stream in streams_good:
        print(stream['extension'], stream['width'], stream['filesize_mbs'], stream['url'])

    stream = streams_good[0]
    return Video(info, stream, format), session


from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
backend = default_backend()
def decrypt(s):
    iv = key
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=backend)
    r = -len(s) % 16
    if r:
        s += b'\x00' * r
    dec = cipher.decryptor()
    s_dec = dec.update(s) + dec.finalize()
    if r:
        s_dec = s_dec[:-r]
    return s_dec

