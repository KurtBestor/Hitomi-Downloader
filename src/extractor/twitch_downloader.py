#coding:utf8
# uncompyle6 version 3.5.0
# Python bytecode 2.7 (62211)
# Decompiled from: Python 2.7.16 (v2.7.16:413a49145e, Mar  4 2019, 01:30:55) [MSC v.1500 32 bit (Intel)]
# Embedded file name: twitch_downloader.pyo
# Compiled at: 2019-10-07 03:52:59
import youtube_dl, downloader, re
from utils import Downloader, get_outdir, Soup, LazyUrl, try_n, compatstr, format_filename, get_ext, clean_title
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

    @classmethod
    def fix_url(cls, url):
        return url.split('?')[0]

    def read(self):
        cw = self.customWidget
        video = Video(self.url)
        video.url()
        self.urls.append(video.url)

        self.setIcon(video.thumb)
        self.title = video.title


class Video(object):
    _url = None

    def __init__(self, url):
        self.url = LazyUrl(url, self.get, self)

    @try_n(4)
    def get(self, url):
        if self._url:
            return self._url
        options = {}
        ydl = youtube_dl.YoutubeDL(options)
        info = ydl.extract_info(url)
        video_best = info['formats'][(-1)]
        video = video_best['url']
        print(video)
        ext = get_ext(video)
        self.title = info['title']
        id = info['display_id']

        if ext.lower() == '.m3u8':
            video = M3u8_stream(video, n_thread=4)
            ext = '.mp4'
        self.filename = format_filename(self.title, id, ext)
        self.url_thumb = info['thumbnail']
        self.thumb = BytesIO()
        downloader.download(self.url_thumb, buffer=self.thumb)
        self._url = video
        return self._url
