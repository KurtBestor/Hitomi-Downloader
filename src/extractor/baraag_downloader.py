#coding:utf8
from utils import Downloader, clean_title, Session
from mastodon import get_info
import ree as re



def get_id(url):
    return re.find('baraag.net/([^/]+)', url.lower())



class Downloader_baraag(Downloader):
    type = 'baraag'
    URLS = ['baraag.net']
    display_name = 'baraag.net'
    ACCEPT_COOKIES = [r'(.*\.)?baraag\.net']

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        id_ = get_id(url) or url
        return f'https://baraag.net/{id_}'

    def read(self):
        id_ = get_id(self.url)
        info = get_info('baraag.net', id_, f'baraag_{id_}', self.session, self.cw)

        self.urls += info['files']

        self.title = clean_title('{} (baraag_{})'.format(info['title'], id_))
