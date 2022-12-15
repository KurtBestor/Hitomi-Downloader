#coding:utf8
from utils import Downloader, clean_title, Session
from mastodon import get_info
import ree as re



def get_id(url):
    return re.find('pawoo.net/([^/]+)', url.lower())



class Downloader_pawoo(Downloader):
    type = 'pawoo'
    URLS = ['pawoo.net']
    ACCEPT_COOKIES = [r'(.*\.)?pawoo\.net']

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        id_ = get_id(url) or url
        return f'https://pawoo.net/{id_}'

    def read(self):
        id_ = get_id(self.url)
        info = get_info('pawoo.net', id_, f'pawoo_{id_}', self.session, self.cw)

        for img in info['imgs']:
            self.urls.append(img.url)

        self.title = clean_title('{} (pawoo{})'.format(info['title'], id_))
