#coding: utf-8
import downloader
from bs4 import BeautifulSoup
import re
import os
from utils import Downloader, LazyUrl, urljoin, parse_range
from urlparse import urlparse, parse_qs
from fucking_encoding import clean_title
from translator import tr_
import urllib
import sys
from time import sleep


class Downloader_gelbooru(Downloader):
    def init(self):
        self._id = None
        self.type = 'gelbooru'
        self.customWidget.anime = False
        self.url = self.url.replace('gelbooru_', '')
        if 'gelbooru.com' in self.url:
            self.url = self.url.replace('http://', 'https://')
        else:
            url = self.url
            url = url.replace(' ', '+')
            while '++' in url:
                url = url.replace('++', '+')
            url = urllib.quote(url)
            url = url.replace('%2B', '+')
            self.url = u'https://gelbooru.com/index.php?page=post&s=list&tags={}'.format(url)

    @property
    def id(self):
        if self._id is None:
            parsed_url = urlparse(self.url)
            qs = parse_qs(parsed_url.query)
            if 'page=favorites' in self.url:
                id = qs.get('id', ['N/A'])[0]
                id = u'fav_{}'.format(id)
            else:
                tags = qs.get('tags', [])
                tags.sort()
                id = u' '.join(tags)
            if not id:
                id = u'N/A'
            self._id = id
        return clean_title(self._id)

    @property
    def name(self):
        return self.id

    def read(self):
        self.title = self.name

        imgs = get_imgs(self.url, self.name, customWidget=self.customWidget)

        for img in imgs:
            self.urls.append(img.url)

        sleep(.1)
        self.title = self.name
    

class Image(object):
    def __init__(self, id, url):
        self.id = id
        self.filename = None
            
        def f(url):
            html = downloader.read_html(url)
            url = re.findall('".{0,20}gelbooru.com//images/.*?"', html)[0][1:-1]
            ext = os.path.splitext(url)[1]
            self.filename = u'{}{}'.format(id, ext)
            return url
        self.url = LazyUrl(url, f, self)


def setPage(url, page):
    # Always use HTTPS
    url = url.replace('http://', 'https://')

    # Change the page
    if 'pid=' in url:
        url = re.sub('pid=[0-9]*', 'pid={}'.format(page), url)
    else:
        url += '&pid={}'.format(page)
        
    return url


def get_imgs(url, title=None, customWidget=None):
    if 's=view' in url and 'page=favorites' not in url:
        raise NotImplementedError('Not Implemented')

    if customWidget is not None:
        print_ = customWidget.print_
    else:
        def print_(*values):
            sys.stdout.writelines(values + ('\n',))
    
    # Range
    if customWidget is not None:
        range_pid = customWidget.range
    else:
        range_pid = None
    if range_pid is not None:
        max_pid = max(parse_range(range_pid, max=100000))
    else:
        max_pid = 2000
        
    imgs = []
    pid = 0
    url_imgs = set()
    while pid < max_pid:
        url = setPage(url, pid)
        print_(url)
        html = downloader.read_html(url)
        soup = BeautifulSoup(html, 'html.parser')
        articles = soup.findAll('div', {'class': 'thumbnail-preview'}) + soup.findAll('span', {'class': 'thumb'})
        
        if not articles:
            break
            
        for article in articles:
            try:
                url_img = article.span.a.attrs['href']
            except:
                url_img = article.a.attrs['href']
            if not url_img.startswith('http'):
                url_img = urljoin('https://gelbooru.com', url_img)
            parsed_url = urlparse(url_img)
            qs = parse_qs(parsed_url.query)
            id = qs['id'][0]
            print url_img
            if url_img not in url_imgs:
                url_imgs.add(url_img)
                img = Image(id, url_img)
                imgs.append(img)
                pid += 1
                if pid >= max_pid:
                    break
        if customWidget is not None and not customWidget.alive:
            break

        pids = [int(pid_.replace('pid=', '')) for pid_ in re.findall('pid=[0-9]+', html)]
        pids_larger = [pid_ for pid_ in pids if pid_ >= pid]
        if pids_larger:
            pid = min(pids_larger)
        else:
            break
        
        if customWidget is not None:
            customWidget.exec_queue.put((customWidget, u"customWidget.setTitle(u'{}  {} - {}')".format(tr_(u'읽는 중...'), title, pid)))
    return imgs
