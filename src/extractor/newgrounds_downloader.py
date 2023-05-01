# coding:utf8
from datetime import datetime
import downloader
import errors
from functools import reduce
import os
import ree as re
from timee import sleep
from translator import tr_
from utils import Downloader, clean_title, Session, get_print, Soup, try_n, check_alive


class Downloader_newgrounds(Downloader):
    type = 'newgrounds'
    URLS = ['newgrounds.com']
    ACCEPT_COOKIES = [r'(.*\.)?newgrounds\.com']

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        user = re.find(r'(?:http(?:s)?://)?([^\.]+).newgrounds.com', url.lower())
        if not user or user == 'www':
            user = re.find(r'newgrounds.com/art/view/([^/?#]+)', url, err='no user id')
        return 'https://{}.newgrounds.com/art'.format(user)

    def read(self):
        user = re.find('(?:http(?:s)?://)?([^\.]+).newgrounds.com', self.url.lower())
        title = clean_title(user)

        for img in get_imgs(user, title, self.session, self.cw):
            self.urls.append(img.url)
            self.filenames[img.url] = img.filename

        self.title = title


class Image:
    def __init__(self, url, filename=None):
        self.url = url
        if filename is None:
            filename = os.path.basename(url)
        self.filename = filename


@try_n(10, sleep=20)
def get_posts(url, params, session, print_):
    posts, data, items = [], None, None
    try:
        data = session.get(url, params=params).json()
        items = data.get('items')
        if items:
            for item in reduce(lambda x, y: x + y, items.values()):
                posts.append(re.find('(?<=href=")([^"]+)', item))
    except Exception as e:
        print_('failed to get posts')
        print_('no. posts: {}'.format(len(posts)))
        print_('data: {}'.format(data))
        print_('items: {}'.format(items))
        raise e

    return posts


@try_n(10, sleep=20)
def get_html(post, session):
    return downloader.read_html(post, session=session)


def get_img(post, session, print_):
    html, url, name, ext, _datetime = None, None, None, None, None
    try:
        html = get_html(post, session)
        if 'You must be logged in, and at least 18 years of age to view this content!' in html:
            raise errors.LoginRequired()
        url = re.find('(?<="full_image_text":"<img src=\\\\")([^"]+)', html).replace('\\', '')
        name = re.find('(?<=alt=\\\\")([^\\\\]+)', html)
        ext = os.path.splitext(url)[1].split('?')[0]
        _datetime = datetime.strptime(re.find('(?<="datePublished" content=")([^"]+)', html), '%Y-%m-%dT%H:%M:%S%z')
    except Exception as e:
        print_('failed to get images')
        print_('post: {}'.format(post))
        print_('url: {}'.format(url))
        print_('name: {}'.format(name))
        print_('ext: {}'.format(ext))
        print_('_datetime: {}'.format(_datetime))
        raise e

    return Image(url=url, filename='[{}] {}{}'.format(_datetime.strftime("%Y-%m-%d"), name, ext))


def get_imgs(user, title, session, cw=None):
    print_ = get_print(cw)

    imgs = []
    url = 'https://{}.newgrounds.com/art'.format(user)
    params = {'page': 1, 'isAjaxRequest': 1}
    while check_alive(cw):
        posts = get_posts(url, params, session, print_)

        if not posts:
            break

        for post in posts:
            sleep(0.75)
            imgs.append(get_img(post, session, print_))
        s = '{} {}  -  {}'.format(tr_('읽는 중...'), title, len(imgs))
        if cw:
            cw.setTitle(s)
        print_('processed: {}'.format(len(imgs)))
        print_('page: {}'.format(params['page']))
        params['page'] += 1

    return imgs
