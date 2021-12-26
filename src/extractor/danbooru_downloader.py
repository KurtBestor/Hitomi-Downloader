#coding: utf-8
import downloader
import ree as re
import os
from utils import Downloader, get_max_range, Soup, clean_title, get_print, try_n
from translator import tr_
try: # python2
    from urllib import quote
    from urlparse import urlparse, parse_qs
except: # python3
    from urllib.parse import quote
    from urllib.parse import urlparse, parse_qs
import sys


@Downloader.register
class Downloader_danbooru(Downloader):
    type='danbooru'
    URLS = ['danbooru.donmai.us']
    _name = None

    @classmethod
    def fix_url(cls, url):
        if 'donmai.us' in url:
            url = url.replace('http://', 'https://')
        else:
            url = url.replace(' ', '+')
            while '++' in url:
                url = url.replace('++', '+')
            url = u'https://danbooru.donmai.us/?tags={}'.format(quote(url))
        return url.strip('+')

    @property
    def name(self):
        if self._name is None:
            parsed_url = urlparse(self.url)
            qs = parse_qs(parsed_url.query)
            if 'donmai.us/favorites' in self.url:
                id = qs.get('user_id', [''])[0]
                print('len(id) =', len(id), u'"{}"'.format(id))
                assert len(id) > 0, '[Fav] User id is not specified'
                id = u'fav_{}'.format(id)
            else:
                tags = qs.get('tags', [])
                tags.sort()
                id = u' '.join(tags)
            if not id:
                id = u'N/A'
            self._name = id
        return clean_title(self._name)

    def read(self):
        self.title = self.name

        imgs = get_imgs(self.url, self.name, cw=self.cw)

        for img in imgs:
            self.urls.append(img.url)
            self.filenames[img.url] = img.filename
            
        self.title = self.name
    

class Image(object):
    def __init__(self, id, url):
        self.id = id
        self.url = url
        ext = os.path.splitext(url)[1]
        self.filename = u'{}{}'.format(id, ext)


def setPage(url, page):
    # Always use HTTPS
    url = url.replace('http://', 'https://')

    # Main page
    if re.findall(r'https://[\w]*[.]?donmai.us/?$', url):
        url = 'https://{}donmai.us/posts?page=1'.format('danbooru.' if 'danbooru.' in url else '')

    # Change the page
    if 'page=' in url:
        url = re.sub('page=[0-9]*', 'page={}'.format(page), url)
    else:
        url += '&page={}'.format(page)
        
    return url


def get_imgs(url, title=None, range_=None, cw=None):
    if 'donmai.us/artists' in url:
        raise NotImplementedError('Not Implemented')
    if 'donmai.us/posts/' in url:
        raise NotImplementedError('Not Implemented')

    print_ = get_print(cw)

    # Range
    max_pid = get_max_range(cw)
    
    if range_ is None:
        range_ = range(1, 1001)
    print(range_)
    imgs = []
    i = 0
    empty_count = 0
    empty_count_global = 0
    url_imgs = set()
    while i < len(range_):
        p = range_[i]
        url = setPage(url, p)
        print_(url)
        html = try_n(4)(downloader.read_html)(url) #4103
        soup = Soup(html)
        articles = soup.findAll('article')
        if articles:
            empty_count_global = 0
        else:
            empty_count += 1
            if empty_count < 4:
                s = u'empty page; retry... {}'.format(p)
                print_(s)
                continue
            else:
                empty_count = 0
                empty_count_global += 1

        if empty_count_global >= 6:
            break
            
        for article in articles:
            id = article.attrs['data-id']
            url_img = article.attrs['data-file-url'].strip()
            if url_img.startswith('http://') or url_img.startswith('https://'):
                pass
            else:
                url_img = 'https://{}donmai.us'.format('danbooru.' if 'danbooru.' in url else '') + url_img
            #print(url_img)
            if url_img not in url_imgs:
                url_imgs.add(url_img)
                img = Image(id, url_img)
                imgs.append(img)

        if len(imgs) >= max_pid:
            break
                
        if cw is not None:
            if not cw.alive:
                break
            cw.setTitle(u'{}  {} - {}'.format(tr_(u'읽는 중...'), title, len(imgs)))
        i += 1
        
    return imgs[:max_pid]

