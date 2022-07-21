#coding:utf8
import downloader
from utils import Soup, Downloader, lazy, clean_title
import ree as re
from translator import tr_
from mastodon import get_imgs



def get_id(url):
    return re.find('baraag.net/([^/]+)', url.lower())



class Downloader_baraag(Downloader):
    type = 'baraag'
    URLS = ['baraag.net']
    display_name = 'baraag.net'

    def init(self):
        self.referer = self.url

    @classmethod
    def fix_url(cls, url):
        id_ = get_id(url) or url
        return 'https://baraag.net/{}'.format(id_)

    @lazy
    def id(self):
        return get_id(self.url)

    @lazy
    def soup(self):
        return Soup(downloader.read_html(self.url))

    @property
    def name(self):
        title = self.soup.find('h1').text.strip().split('\n')[0].strip()
        title = u'{} (baraag_{})'.format(title, self.id)
        return clean_title(title)

    def read(self):
        self.title = tr_(u'읽는 중... {}').format(self.name)

        imgs = get_imgs('baraag.net', self.id, self.name, cw=self.cw)

        for img in imgs:
            self.urls.append(img.url)
            self.filenames[img.url] = img.filename

        self.title = self.name
