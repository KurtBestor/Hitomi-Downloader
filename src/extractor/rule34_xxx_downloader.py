import downloader
import ree as re
import os
from utils import Downloader, urljoin, query_url, Soup, get_max_range, get_print, clean_title, try_n, check_alive
from translator import tr_
try:
    from urllib import quote # python2
except:
    from urllib.parse import quote # python3
import sys
from timee import sleep
from constants import clean_url
LIMIT = 100


def get_tags(url):
    url = clean_url(url)
    qs = query_url(url)
    if 'page=favorites' in url:
        id = qs.get('id', ['N/A'])[0]
        id = 'fav_{}'.format(id)
    else:
        tags = qs.get('tags', [])
        tags.sort()
        id = ' '.join(tags)
    if not id:
        id = 'N/A'
    return id



class Downloader_rule34_xxx(Downloader):
    type = 'rule34_xxx'
    URLS = ['rule34.xxx']
    MAX_CORE = 8
    display_name = 'Rule34.xxx'
    _name = None

    @classmethod
    def fix_url(cls, url):
        if 'rule34.xxx' in url.lower():
            url = url.replace('http://', 'https://')
        else:
            url = url.replace(' ', '+')
            while '++' in url:
                url = url.replace('++', '+')
            url = quote(url)
            url = url.replace('%2B', '+')
            url = 'https://rule34.xxx/index.php?page=post&s=list&tags={}'.format(url)
        return url

    @property
    def name(self):
        if self._name is None:
            tags = get_tags(self.url)
            self._name = tags
        return clean_title(self._name)

    def read(self):
        self.title = self.name

        imgs = get_imgs(self.url, self.name, cw=self.cw)

        for img in imgs:
            self.urls.append(img.url)
            self.filenames[img.url] = img.filename

        self.title = self.name


class Image:
    def __init__(self, id_, url):
        self.url = url
        ext = os.path.splitext(url)[1]
        self.filename = '{}{}'.format(id_, ext)


def setPage(url, page):
    # Always use HTTPS
    url = url.replace('http://', 'https://')

    # Change the page
    if 'pid=' in url:
        url = re.sub('pid=[0-9]*', 'pid={}'.format(page), url)
    else:
        url += '&pid={}'.format(page)

    return url


def get_imgs(url, title=None, cw=None):
    url = clean_url(url)
    if 's=view' in url and 'page=favorites' not in url:
        raise NotImplementedError('Not Implemented')

    if 'page=dapi' not in url.lower():
        tags = get_tags(url)
        tags = quote(tags, safe='/')
        tags = tags.replace('%20', '+')
        url = "https://rule34.xxx/index.php?page=dapi&s=post&q=index&tags={}&pid={}&limit={}".format(tags, 0, LIMIT)

    print_ = get_print(cw)

    # Range
    max_pid = get_max_range(cw)

    imgs = []
    ids = set()
    for p in range(500): #1017
        check_alive(cw)
        url = setPage(url, p)
        print_(url)
        html = try_n(4, sleep=30)(downloader.read_html)(url) #3340

        soup = Soup(html)
        posts = soup.findAll('post')
        if not posts:
            break
        for post in posts:
            id_ = post.attrs['id']
            if id_ in ids:
                print('duplicate:', id_)
                continue
            ids.add(id_)
            url_img = post.attrs['file_url']
            img = Image(id_, url_img)
            imgs.append(img)
        if len(imgs) >= max_pid:
            break

        if cw is not None:
            cw.setTitle('{}  {} - {}'.format(tr_('읽는 중...'), title, len(imgs)))
    return imgs
