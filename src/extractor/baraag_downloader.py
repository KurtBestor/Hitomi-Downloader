#coding:utf8
import downloader
from utils import Soup, Downloader, lazy
import ree as re
from fucking_encoding import clean_title
from translator import tr_
from mastodon import get_imgs


@Downloader.register
class Downloader_baraag(Downloader):
    type = 'baraag'
    URLS = ['baraag.net']
    
    def init(self):
        self.url = self.url.replace('baraag_', '')
        self.url = u'https://baraag.net/{}'.format(self.id)
        self.referer = self.url
        
    @property
    def id(self):
        return re.find('baraag.net/([^/]+)', self.url.lower(), default=self.url)

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

        imgs = get_imgs('baraag.net', self.id, self.name, cw=self.customWidget)

        for img in imgs:
            self.urls.append(img.url)
            self.filenames[img.url] = img.filename

        self.title = self.name



