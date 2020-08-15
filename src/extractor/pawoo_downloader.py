#coding:utf8
import downloader
from utils import Soup, Downloader, lazy
import ree as re
from fucking_encoding import clean_title
from translator import tr_
from mastodon import get_imgs


@Downloader.register
class Downloader_pawoo(Downloader):
    type = 'pawoo'
    URLS = ['pawoo.net']
    
    def init(self):
        self.url = self.url.replace('pawoo_', '')
        self.url = u'https://pawoo.net/{}'.format(self.id)
        self.referer = self.url
        
    @property
    def id(self):
        return re.find('pawoo.net/([^/]+)', self.url.lower(), default=self.url)

    @lazy
    def soup(self):
        return Soup(downloader.read_html(self.url))

    @property
    def name(self):
        title = self.soup.find('h1', class_='name').span.text.strip()
        title = u'{} (pawoo_{})'.format(title, self.id)
        return clean_title(title)

    def read(self):
        self.title = tr_(u'읽는 중... {}').format(self.name)

        imgs = get_imgs('pawoo.net', self.id, self.name, cw=self.customWidget)

        for img in imgs:
            self.urls.append(img.url)
            self.filenames[img.url] = img.filename

        self.title = self.name


