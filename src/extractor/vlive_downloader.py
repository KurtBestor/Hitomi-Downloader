import downloader
import ytdl
from utils import Downloader, try_n, LazyUrl, get_ext, format_filename, clean_title, pp_subtitle
from io import BytesIO
import ree as re
from m3u8_tools import M3u8_stream
import os



class Downloader_vlive(Downloader):
    type = 'vlive'
    URLS = ['vlive.tv']
    single = True
    display_name = 'V LIVE'

    def init(self):
        if 'channels.vlive.tv' in self.url:
            raise NotImplementedError('channel')

    def read(self):
        cw = self.cw
        video = get_video(self.url, cw=cw)

        self.urls.append(video.url)

        self.setIcon(video.thumb)
        self.enableSegment()

        self.title = clean_title(video.title)


@try_n(4)
def get_video(url, cw=None):
    options = {
        'noplaylist': True,
        }

    ydl = ytdl.YoutubeDL(options, cw=cw)
    info = ydl.extract_info(url)

    fs = []
    for f in info['formats']:
        if f['ext'] != 'mp4':
            continue
        f['quality'] = f.get('vbr') or re.find('([0-9]+)p', f['format'], re.IGNORECASE)
        print(f['format'], f['quality'])
        fs.append(f)

    if not fs:
        raise Exception('No videos')

    f = sorted(fs, key=lambda f:f['quality'])[-1]
    video = Video(f, info, cw)

    return video


class Video(object):
    def __init__(self, f, info, cw=None):
        self.title = title = info['title']
        self.id = info['id']
        self.url = f['url']
        self.subs = ytdl.get_subtitles(info)
        self.cw = cw

        self.thumb = BytesIO()
        downloader.download(info['thumbnail'], buffer=self.thumb)

        ext = get_ext(self.url)
        if ext.lower() == '.m3u8':
            raise NotImplementedError('stream')#
            url = M3u8_stream(self.url, n_thread=4)
        else:
            url = self.url
        self.url = LazyUrl(self.url, lambda x: url, self, pp=self.pp)
        self.filename = format_filename(title, self.id, ext)

    def pp(self, filename):
        pp_subtitle(self, filename, self.cw)
        return filename
