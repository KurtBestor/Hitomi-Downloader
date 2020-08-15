#coding:utf8
# uncompyle6 version 3.5.0
# Python bytecode 2.7 (62211)
# Decompiled from: Python 2.7.16 (v2.7.16:413a49145e, Mar  4 2019, 01:30:55) [MSC v.1500 32 bit (Intel)]
# Embedded file name: twitch_downloader.pyo
# Compiled at: 2019-10-07 03:52:59
import youtube_dl, downloader, re
from utils import Downloader, get_outdir, Soup, LazyUrl, try_n, compatstr
from fucking_encoding import clean_title
from timee import sleep
from error_printer import print_error
import os
from translator import tr_
import shutil, ffmpeg, json
from io import BytesIO
from m3u8_tools import M3u8_stream


@Downloader.register
class Downloader_twitch(Downloader):
    type = 'twitch'
    URLS = ['twitch.tv']
    #lock = True
    #detect_removed = False
    single = True

    def init(self):
        url = self.url
        customWidget = self.customWidget
        if 'twitch.tv' in url:
            if not url.startswith('http://') and not url.startswith('https://'):
                url = u'https://' + url
            self.url = url
        else:
            url = (u'https://www.twitch.tv/videos/{}').format(url.replace('twitch_', ''))
            self.url = url

    @property
    def id(self):
        return self.url

    def read(self):
        cw = self.customWidget
        format = compatstr(self.ui_setting.youtubeFormat.currentText()).lower().strip()
        info, video = get_video(self.url, format)
        title = info['title']
        self.urls.append(video.url)

        thumb = BytesIO()
        downloader.download(info['thumbnail'], buffer=thumb)
        self.setIcon(thumb)
        self.title = title


class Video(object):

    def __init__(self, video, url, filename):
        self.url = LazyUrl(url, lambda _: video, self)
        self.filename = filename


@try_n(4)
def get_video(url, format='title'):
    options = {}
    ydl = youtube_dl.YoutubeDL(options)
    info = ydl.extract_info(url)
    video_best = info['formats'][(-1)]
    video = video_best['url']
    print(video)
    ext = os.path.splitext(video.split('?')[0])[1].lower()[1:]
    title = info['title']
    id = info['display_id']
    format = format.replace('title', '###title*').replace('id', '###id*')
    title = format.replace('###title*', title).replace('###id*', (u'{}').format(id))
    title = clean_title(title, allow_dot=True)

    if ext == 'm3u8':
        video = M3u8_stream(video, n_thread=4)
        video = Video(video, url, u'{}.{}'.format(title, 'mp4'))
    else:
        video = Video(video, url, u'{}.{}'.format(title, ext))
    return info, video
