import downloader
import downloader_v3
from utils import Downloader, get_print, format_filename, clean_title, get_resolution, try_n, Session, uuid, File, get_max_range, query_url
import os
from io import BytesIO
import ffmpeg
import math
import ree as re
import ytdl
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


class File_bili(File):
    type = 'bili'
    thread_audio = None

    @try_n(4)
    def get(self):
        session = self.session
        cw = self.cw
        print_ = get_print(cw)

        options = {
                #'noplaylist': True, #5562
                #'extract_flat': True,
                'playlistend': 1,
                }
        ydl = ytdl.YoutubeDL(options, cw=cw)
        info = ydl.extract_info(self['referer'])

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

        title = info['title']
        url_thumb = info['thumbnail']
        ext = info['ext']

        session.headers.update(info.get('http_headers', {}))

        mobj = re.match(_VALID_URL, self['referer'])
        video_id = mobj.group('id')

        info = {
            'url': f_video['url'],
            'url_thumb': url_thumb,
            'name': format_filename(title, video_id, ext),
            }

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

        return info

    def pp(self, filename):
        if self.thread_audio:
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
    soup = downloader.read_soup(url, methods={'requests'})
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
    URLS = [r'regex:'+_VALID_URL, 'space.bilibili.com/']
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

    @classmethod
    def key_id(cls, url):
        mobj = re.match(_VALID_URL, url)
        video_id = mobj.group('id')
        qs = query_url(url)
        p = qs.get('p', ['1'])[0] #6580
        return f'{video_id or url} {p}'

    @property
    def id_(self):
        mobj = re.match(_VALID_URL, self.url)
        video_id = mobj.group('id')
        #anime_id = mobj.group('anime_id')
        return video_id

    def read(self):
        sd = self.session.cookies.get('SESSDATA', domain='.bilibili.com')
        self.print_('sd: {}'.format(sd))
        if not sd: #5647
            self.cw.showCookie()
            self.cw.showLogin('https://passport.bilibili.com/login', 1030, None)

        sid = re.find(r'/channel/collectiondetail?sid=([0-9]+)', self.url)
        mid = re.find(r'space.bilibili.com/([0-9]+)', self.url)
        if sid or mid:
            if not sd:
                raise errors.LoginRequired()
            if sid:
                url_api = f'https://api.bilibili.com/x/polymer/web-space/seasons_archives_list?mid={mid}&season_id={sid}'
                j = downloader.read_json(url_api, self.url)
                title = clean_title(j['data']['meta']['name'])
            elif mid:
                url_api = f'https://api.bilibili.com/x/space/wbi/acc/info?mid={mid}'
                j = downloader.read_json(url_api, self.url)
                title = clean_title(j['data']['name'])
            else:
                raise NotImplementedError()
            self.single = False
            options = {
                'extract_flat': True,
                'playlistend': get_max_range(self.cw),
                }
            ydl = ytdl.YoutubeDL(options, cw=self.cw)
            info = ydl.extract_info(self.url)
            files = []
            for e in info['entries']:
                files.append(File_bili({'referer': e['url']}))
            self.print_(f'urls: {len(files)}')
            file = self.process_playlist(title, files)
            self.title = title
        else:
            file = File_bili({'referer': self.url})
            file.ready(self.cw)
            self.urls.append(file)
            self.title = os.path.splitext(file['name'])[0]

        thumb = BytesIO()
        downloader.download(file['url_thumb'], buffer=thumb)
        self.setIcon(thumb)
        n = int(math.ceil(8.0 / len(self.urls)))
        self.print_(f'n_threads: {n}')
        self.enableSegment(n_threads=n, overwrite=True)
