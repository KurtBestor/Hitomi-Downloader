# uncompyle6 version 3.5.0
# Python bytecode 2.7 (62211)
# Decompiled from: Python 2.7.16 (v2.7.16:413a49145e, Mar  4 2019, 01:30:55) [MSC v.1500 32 bit (Intel)]
# Embedded file name: file_downloader.pyo
# Compiled at: 2019-10-02 14:06:58
import downloader, json, os
from constants import try_n
from utils import Downloader, query_url, clean_title, get_ext
from timee import sleep


@Downloader.register
class Downloader_file(Downloader):
    type = 'file'
    single = True
    URLS = []

    def init(self):
        if not self.url.startswith('http'):
            if self.url[:1] == '/':
                self.url = self.url[1:]
            self.url = 'https://' + self.url

    def read(self):
        qs = query_url(self.url)
        for key in qs:
            if key.lower() in ('file', 'filename'):
                name = qs[key][(-1)]
                break
        else:
            name = os.path.basename(self.url)
            for esc in ['?', '#']:
                name = name.split(esc)[0]

        if not get_ext(name):
            name += downloader.get_ext(self.url)

        self.urls.append(self.url)
        self.filenames[self.url] = clean_title(name)
        
        self.title = name
