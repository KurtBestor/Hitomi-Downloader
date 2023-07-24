#coding:utf8
from utils import Downloader, clean_title, Session
from mastodon import get_info
import ree as re



def get_id(url):
    return re.find('mastodon.social/([^/]+)', url.lower())



class Downloader_mastodon(Downloader):
    type = 'mastodon'
    URLS = ['mastodon.social']
    ACCEPT_COOKIES = [r'(.*\.)?mastodon\.social']

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        id_ = get_id(url) or url
        return f'https://mastodon.social/{id_}'

    def read(self):
        id_ = get_id(self.url)
        info = get_info('mastodon.social', id_, f'mastodon_{id_}', self.session, self.cw)

        self.urls += info['files']

        self.title = clean_title('{} (mastodon_{})'.format(info['title'], id_))
