from __future__ import division, print_function, unicode_literals
import downloader
from utils import Soup, urljoin, Downloader, LazyUrl, get_print, clean_url, clean_title, check_alive, Session, try_n
import ree as re
import json
import os
from timee import sleep
from io import BytesIO
import errors
TIMEOUT = 300



class File(object):
    thumb = None

    def __init__(self, type, url, title, referer, p=0, multi_post=False):
        self.type = type
        self.url = LazyUrl(referer, lambda _: url, self)
        ext = os.path.splitext(url.split('?')[0])[1]
        if ext.lower() == '.php':
            ext = '.mp4'
        if type == 'video':
            self.filename = clean_title('{}{}'.format(title, ext))
        elif type == 'image':
            name = '{}_p{}'.format(clean_title(title), p) if multi_post else p
            self.filename = '{}{}'.format(name, ext)
        else:
            raise NotImplementedError(type)
        self.title = title


class LazyFile(object):
    _url = None
    thumb = None
    
    def __init__(self, url, type_, session):
        self.url = LazyUrl(url, self.get, self)
        self.type = {'videos': 'video', 'images': 'image'}.get(type_) or type_
        self.session = session

    def get(self, url):
        if self._url:
            return self._url
        file = get_files(url, self.session, multi_post=True)[0]
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

    @classmethod
    def fix_url(cls, url):
        url = clean_url(url)
        return url.split('?')[0]

    def init(self):
        self.session = Session()
        self.session.cookies.update({'show_adult': '1', 'has_js': '1'})
        self.setTimeout(TIMEOUT)

    def read(self):
        file = None
        files = None
        title = None
        if '/users/' in self.url or '/user/' in self.url:
            type_ = 'videos'
            try:
                if self.url.split('/users/')[1].split('/')[1] == 'images':
                    type_ = 'images'
            except:
                pass
            info = read_channel(self.url, type_, self.session, self.cw)
            title = info['title']
            urls = info['urls']
            if type_ == 'videos':
                files = [LazyFile(url, type_, self.session) for url in urls]
                file = self.process_playlist('[Channel] [{}] {}'.format(type_.capitalize(), title), files)
            elif type_ == 'images':
                files = [LazyFile(url, type_, self.session) for url in urls]
                title = '[Channel] [{}] {}'.format(type_.capitalize(), title)
            else:
                raise NotImplementedError(type_)

        if file is None:
            if files is None:
                files = get_files(self.url, self.session, cw=self.cw)
            for file in files:
                self.urls.append(file.url)
            file = files[0]

            if file.type == 'youtube':
                raise errors.Invalid('[iwara] Youtube: {}'.format(self.url))
            
            if file.type == 'image':
                self.single = False
            self.title = clean_title(title or file.title)
            
        if file.thumb is not None:
            self.setIcon(file.thumb)


@try_n(4)
def read_html(*args, **kwargs):
    kwargs['timeout'] = TIMEOUT
    return downloader.read_html(*args, **kwargs)


def read_channel(url, type_, session, cw=None):
    print_ = get_print(cw)
    html = read_html(url, session=session)
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
        check_alive(cw)
        url = 'https://ecchi.iwara.tv/users/{}/{}?page={}'.format(username, type_, p)
        print_(url)
        html = read_html(url, session=session)
        soup = Soup(html)
        if p == 0:
            title = soup.find('h1', class_='page-title').text
            info['title'] = title.replace("'s videos", '').replace("'s images", '').strip()
            
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


def get_files(url, session, multi_post=False, cw=None):
    print_ = get_print(cw)
    html = read_html(url, session=session)
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
        type = 'image'
    print_(('type: {}').format(type))
    files = []
    if type == 'image':
        urls = set()
        for img in content.findAll('img'):
            img = urljoin(url, img.parent.attrs['href'])
            if '/files/' not in img:
                continue
            if img in urls:
                print('duplicate')
                continue
            urls.add(img)
            file = File(type, img, title, url, len(files), multi_post=multi_post)
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
        s_json = read_html(url_data, url, session=session)
        data = json.loads(s_json)
        video = data[0]
        url_video = urljoin(url, video['uri'])
        file = File(type, url_video, title, url)
        file.url_thumb = url_thumb
        file.thumb = BytesIO()
        downloader.download(url_thumb, buffer=file.thumb, referer=url)
        files.append(file)
    else:
        raise NotImplementedError(type)
    return files


