import downloader, ree as re
from utils import Downloader, get_outdir, Soup, get_p2f, LazyUrl, get_print, cut_pair, get_ext, compatstr, try_n
from fucking_encoding import clean_title
from timee import sleep
from error_printer import print_error
import os
from translator import tr_
import shutil, ffmpeg, json
from io import BytesIO


@Downloader.register
class Downloader_xhamster(Downloader):
    type = 'xhamster'
    URLS = [
     'regex:xhamster[0-9]*\\.[a-z0-9]+/videos/',
     'regex:xhamster[0-9]*\\.[a-z0-9]+/users/',
     'regex:xhamster[0-9]*\\.[a-z0-9]+/photos/gallery/',
     ]
    single = True

    def init(self):
        self.url = self.url.replace('xhamster_', '')
        if not re.search('xhamster[0-9]*\\.', self.url):
            self.url = (u'https://xhamster.com/videos/{}').format(self.url)

    @property
    def id(self):
        return self.url

    @classmethod
    def fix_url(cls, url):
        m = re.search('xhamster(?P<number>[0-9]*)\\.(?P<top>[a-z0-9]+)/', url)
        number, top = m.groups()
        return url.replace((u'xhamster{}.{}/').format(number, top), u'xhamster.com/')

    def read(self):
        cw = self.customWidget
        ui_setting = self.ui_setting
        format = compatstr(ui_setting.youtubeFormat.currentText()).lower().strip()
        cw.enableSegment(1024*1024//2)
        thumb = BytesIO()
        
        if '/users/' in self.url:
            info = read_channel(self.url, cw)
            urls = info['urls']
            p2f = get_p2f(cw)
            if p2f:
                self.single = False
                self.title = clean_title(info['title'])
                videos = [Video(url, format) for url in info['urls']]
                self.urls = [video.url for video in videos]
                video = videos[0]
                video.url()
                downloader.download(video.info['thumbnail'], buffer=thumb)
                self.setIcon(thumb)
                return
            else:
                cw.gal_num = self.url = urls.pop(0)
                if urls and cw.alive:
                    s = u', '.join(urls)
                    self.exec_queue.put((s, 'downButton(customWidget)'))
        elif '/photos/gallery/' in self.url:
            info = read_gallery(self.url, cw)
            for img in info['imgs']:
                self.urls.append(img.url)
            self.single = False
            self.title = clean_title(info['title'])
            self.url = info['url']
            cw.disableSegment()
            return
        else:
            urls = []
        video = Video(self.url, format)
        video.url()
        self.urls.append(video.url)

        downloader.download(video.info['thumbnail'], buffer=thumb)
        self.setIcon(thumb)
        self.title = video.title


class Video(object):
    _url = None

    def __init__(self, url, format):
        url = downloader.real_url(url)
        self.url = LazyUrl(url, self.get, self)
        self.format = format

    @try_n(2)
    def get(self, url):
        if self._url:
            return self._url
        self.info = get_info(url)

        title = self.info['title']
        id = self.info['id']
        
        format = self.format.replace('title', '###title*').replace('id', '###id*')
        self.title = format.replace('###title*', title).replace('###id*', (u'{}').format(id))
        video_best = self.info['formats'][(-1)]
        self._url = video_best['url']
        ext = os.path.splitext(self._url.split('?')[0])[1]
        self.filename = u'{}{}'.format(clean_title(self.title, n=-len(ext)), ext)
        return self._url


def get_data(html):
    data_raw = cut_pair(re.find('window.initials *= *(.+)', html))
    return json.loads(data_raw)


def get_info(url):
    info = {}
    html = downloader.read_html(url)
    soup = Soup(html)

    err = soup.find('div', class_="error404-title")
    if err:
        raise Exception(err.text.strip())

    data = get_data(html)
    
    info['title'] = data['videoModel']['title']
    info['id'] = data['videoModel']['id']
    info['thumbnail'] = data['videoModel']['thumbURL']
    
    fs = []
    for res, url_video in data['videoModel']['sources']['mp4'].items():
        height = int(re.find('(\d+)p', res))
        f = {'url': url_video, 'height': height}
        fs.append(f)
    fs = sorted(fs, key=lambda f: f['height'])

    info['formats'] = fs
    return info


def read_channel(url, cw=None):
    print_ =  get_print(cw)
    username = url.split('/users/')[1].split('/')[0]

    info = {}
    html = downloader.read_html(url)
    soup = Soup(html)
    title = soup.find('div', class_='user-name').text.strip()
    info['title'] = u'[Channel] {}'.format(title)
    
    items = []
    for p in range(1, 21):
        url = 'https://xhamster.com/users/{}/videos/{}'.format(username, p)
        print_(url)
        html = downloader.read_html(url)
        soup = Soup(html)
        items_ = soup.findAll('div', class_='thumb-list__item')
        if not items_:
            print('no items')
            break
        for item in items_:
            items.append(item)

    urls = []
    for item in items:
        url = item.a.attrs['href']
        if url in urls:
            print('duplicate:', url)
            continue
        urls.append(url)

    info['urls'] = urls

    return info


class Image(object):
    def __init__(self, url, id, referer):
        self.id = id
        self._url = url
        self.url = LazyUrl(referer, self.get, self)

    def get(self, referer):
        url = self._url
        ext = get_ext(url)
        self.filename = '{}{}'.format(self.id, ext)
        return url


def setPage(url, p):
    url = url.strip('/')
    c = url.split('/photos/gallery/')[1].count('/')
    if c:
        url = '/'.join(url.split('/')[:-1])
    if p > 1:
        url += '/{}'.format(p)
    return url

        
def read_gallery(url, cw=None):
    print_ = get_print(cw)

    info = {}

    html = downloader.read_html(url)
    soup = Soup(html)

    h1 = soup.find('h1')
    if h1.find('a'):
        url = h1.find('a')['href']
        return read_gallery(url, cw)
    info['title'] = h1.text.strip()
    info['url'] = setPage(url, 1)

    imgs = []
    ids = set()
    for p in range(1, 101):
        print_('p: {}'.format(p))
        url = setPage(url, p)
        html = downloader.read_html(url)
        
        data = get_data(html)

        photos = data['photosGalleryModel']['photos']
        if not photos:
            print('no photos')
            break
        
        for photo in photos:
            img = photo['imageURL']
            id = photo['id']
            referer = photo['pageURL']
            if id in ids:
                print('duplicate:', id)
                continue
            ids.add(id)
            img = Image(img, id, referer)
            imgs.append(img)
    
    info['imgs'] = imgs

    return info
