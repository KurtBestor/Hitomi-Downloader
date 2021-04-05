from __future__ import division, print_function, unicode_literals
import downloader
from utils import Soup, urljoin, Downloader, LazyUrl, get_print, clean_url, clean_title
import ree as re
import json
import os
from timee import sleep
from io import BytesIO



class File(object):
    thumb = None

    def __init__(self, type, url, title, referer, p=0):
        self.type = type
        self.url = LazyUrl(referer, lambda _: url, self)
        ext = os.path.splitext(url.split('?')[0])[1]
        if ext.lower() == '.php':
            ext = '.mp4'
        if type == 'video':
            self.filename = clean_title('{}{}'.format(title, ext))
        else:
            self.filename = '{}{}'.format(p, ext)
        self.title = title


class LazyVideo(object):
    type = 'video'
    _url = None
    
    def __init__(self, url):
        self.url = LazyUrl(url, self.get, self)

    def get(self, url):
        if self._url:
            return self._url
        file = get_files(url)[0]
        self.title = file.title
        self.thumb = file.thumb
        self.filename = file.filename
        self._url = file.url()
        return self._url
        

@Downloader.register
class Downloader_iwara(Downloader):
    type = 'iwara'
    URLS = ['iwara.tv']
    MAX_CORE = 16#
    single = True
    display_name = 'Iwara'

    def init(self):
        self.url = clean_url(self.url)

    @classmethod
    def fix_url(cls, url):
        return url.split('?')[0]

    def read(self):
        if '/users/' in self.url:
            type_ = 'videos'
            try:
                if self.url.split('/users/')[1].split('/')[1] == 'images':
                    type_ = 'images'
            except:
                pass
            info = read_channel(self.url, type_, self.cw)
            urls = info['urls']
            if type_ == 'videos':
                files = [LazyVideo(url) for url in urls]
                file = self.process_playlist('[Channel] [{}] {}'.format(type_.capitalize(), info['title']), files)
            else:
                raise NotImplementedError('channel images')
        else:
            files = get_files(self.url, self.cw)
            for file in files:
                self.urls.append(file.url)
            file = files[0]

            if file.type == 'youtube':
                return self.Invalid('[iwara] Youtube: {}'.format(self.url))
            
            if file.type == 'img':
                self.single = False
            self.title = clean_title(file.title)
            
        if file.thumb is not None:
            self.setIcon(file.thumb)
        


def read_channel(url, type_, cw=None):
    print_ = get_print(cw)
    html = downloader.read_html(url)
    soup = Soup(html)
    if soup.find('div', id='block-mainblocks-user-connect'):
        username = re.find(r'''/messages/new\?user=(.+)['"]''', html, err='no username')
    else:
        username = re.find(r'/users/([^/]+)', url, err='no username')
    print_('username: {}'.format(username))
    info = {}
    urls = []
    urls_set = set()
    for p in range(50):
        url = 'https://ecchi.iwara.tv/users/{}/{}?page={}'.format(username, type_, p)
        print_(url)
        html = downloader.read_html(url)
        soup = Soup(html)
        if p == 0:
            title = soup.find('h1', class_='page-title').text
            info['title'] = title.replace("'s videos", '').strip()
            
        view = soup.find('div', class_='view-content')
        if view is None:
            break
        
        urls_new = []
        for div in view.findAll('div', class_='views-column'):
            href = div.find('a')['href']
            url_video = urljoin(url, href)
            if url_video in urls_set:
                continue
            urls_set.add(url_video)
            urls_new.append(url_video)
        if not urls_new:
            break
        urls += urls_new
    info['urls'] = urls
    return info


def get_files(url, cw=None):
    print_ = get_print(cw)
    html = downloader.read_html(url)
    soup = Soup(html)
    h = soup.find('h1', class_='title')
    content = h.parent.parent.parent
    title = h.text.strip()
    youtube = content.find('div', class_='embedded-video')
    video = content.find('video')
    if youtube:
        type = 'youtube'
    elif video:
        type = 'video'
    else:
        type = 'img'
    print_(('type: {}').format(type))
    files = []
    if type == 'img':
        urls = set()
        for img in content.findAll('img'):
            img = urljoin(url, img.parent.attrs['href'])
            if '/files/' not in img:
                continue
            if img in urls:
                print('duplicate')
                continue
            urls.add(img)
            file = File(type, img, title, url, len(files))
            files.append(file)

    elif type == 'youtube':
        src = urljoin(url, youtube.find('iframe').attrs['src'])
        file = File(type, src, title, url)
        files.append(file)
    elif type == 'video':
        url_thumb = urljoin(url, video.attrs['poster'])
        print('url_thumb:', url_thumb)
        id = re.find('videos/([0-9a-zA-Z_-]+)', url, err='no video id')
        url_data = urljoin(url, '/api/video/{}'.format(id))
        s_json = downloader.read_html(url_data, url)
        data = json.loads(s_json)
        video = data[0]
        url_video = urljoin(url, video['uri'])
        file = File(type, url_video, title, url)
        file.url_thumb = url_thumb
        file.thumb = BytesIO()
        downloader.download(url_thumb, buffer=file.thumb, referer=url)
        files.append(file)
    else:
        raise Exception(('type "{}" is not supported').format(type))
    return files


