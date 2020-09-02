#coding:utf8
import downloader
from utils import Downloader, lazy, clean_title
import ree as re
from translator import tr_
from mastodon import get_imgs
import json


@Downloader.register
class Downloader_pawoo(Downloader):
    type = 'pawoo'
    URLS = ['pawoo.net']
    
    def init(self):
        self.url = self.url.replace('pawoo_', '')
        self.url = 'https://pawoo.net/{}'.format(self.id_)
        self.referer = self.url
        
    @property
    def id_(self):
        return re.find('pawoo.net/([^/]+)', self.url.lower(), default=self.url)

    @lazy
    def soup(self):
        return downloader.read_soup(self.url)

    @property
    def name(self):
        name_raw = re.find(r'''['"]name['"] *: *['"](.+?)['"]''', str(self.soup), err='no name')
        name = json.loads('"{}"'.format(name_raw))
        title = '{} (pawoo_{})'.format(name, self.id_)
        return clean_title(title)

    def read(self):
        self.title = tr_('읽는 중... {}').format(self.name)

        imgs = get_imgs('pawoo.net', self.id_, self.name, cw=self.customWidget)

        for img in imgs:
            self.urls.append(img.url)
            self.filenames[img.url] = img.filename

        self.title = self.name


