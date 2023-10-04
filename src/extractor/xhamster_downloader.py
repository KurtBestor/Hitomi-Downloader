import downloader, ree as re
from utils import Downloader, Soup, Session, LazyUrl, get_print, get_ext, try_n, format_filename, clean_title, get_resolution
from translator import tr_
from io import BytesIO
import ytdl



class Downloader_xhamster(Downloader):
    type = 'xhamster'
    __name = r'([^/]*\.)?(xhamster|xhwebsite|xhofficial|xhlocal|xhopen|xhtotal|megaxh|xhwide|xhtab|xhtime)([0-9]*)' #3881, #4332, #4826, #5029, #5696, #5893
    URLS = [rf'regex:{__name}\.[a-z0-9]+/(videos|users|creators|photos/gallery)/']
    single = True
    display_name = 'xHamster'

    def init(self):
        if re.search(r'xhamsterlive[0-9]*\.', self.url):
            raise Exception('xHamsterLive')
        if not re.search(r'{}\.'.format(self.__name), self.url):
            self.url = 'https://xhamster.com/videos/{}'.format(self.url)
        self.session = Session('chrome')

    @classmethod
    def fix_url(cls, url):
        url = re.sub(r'(/users/[^/]+/videos)/[0-9]+', r'\1', url, 1) #5029
        return url

    @classmethod
    def key_id(cls, url):
        return re.sub(cls.__name+r'\.[^/]+', 'domain', url, 1).replace('http://', 'https://')

    def read(self):
        cw = self.cw
        self.enableSegment(1024*1024//2)
        thumb = BytesIO()

        if '/users/' in self.url or '/creators/' in self.url: #6257
            info = read_channel(self.url, self.session, cw)
            urls = info['urls']
            videos = [Video(url) for url in urls]
            video = self.process_playlist(info['title'], videos)
        elif '/photos/gallery/' in self.url:
            info = read_gallery(self.url, self.session, cw)
            for img in info['imgs']:
                self.urls.append(img.url)
            self.single = False
            self.title = clean_title(info['title'])
            self.url = info['url']
            self.disableSegment()
            return
        else:
            video = Video(self.url)
            video.url()
            self.urls.append(video.url)
            self.title = video.title

        downloader.download(video.info['thumbnail'], buffer=thumb)
        self.setIcon(thumb)


class Video:
    _url = None

    def __init__(self, url):
        #url = downloader.real_url(url)
        self.url = LazyUrl(url, self.get, self)

    @try_n(2)
    def get(self, url):
        if self._url is None:
            self.info = get_info(url)

            self.title = self.info['title']
            id = self.info['id']

            #4773
            fs = self.info['formats']
            res = max(get_resolution(), min(f['height'] for f in fs))
            fs = [f for f in fs if f['height'] <= res]

            video_best = fs[-1]
            self._url = video_best['url']
            ext = get_ext(self._url)
            self.filename = format_filename(self.title, id, ext)

            if isinstance(self._url, str) and 'referer=force' in self._url.lower():
                self._referer = self._url
            else:
                self._referer = url
        return self._url, self._referer


def get_info(url): #6318
    info = {}
    ydl = ytdl.YoutubeDL()
    d = ydl.extract_info(url)
    info['title'] = d['title']
    info['id'] = d['id']
    info['thumbnail'] = d['thumbnail']
    fs = []
    for f in d['formats']:
        if f['protocol'] != 'https':
            continue
        f = {'url': f['url'], 'height': f['height']}
        fs.append(f)
    fs = sorted(fs, key=lambda f: f['height'])
    info['formats'] = fs
    return info


def read_page(type_, username, p, session, cw):
    print_ = get_print(cw)
    if type_ == 'users':
        url = f'https://xhamster.com/users/{username}/videos/{p}'
    elif type_ == 'creators':
        url = f'https://xhamster.com/creators/{username}/exclusive/{p}'
    else:
        raise NotImplementedError(type_)
    print_(url)
    n = 4
    for try_ in range(n):
        try:
            soup = downloader.read_soup(url, session=session)
            items = soup.findAll('div', class_='thumb-list__item')
            if not items and try_ < n-1:
                continue
            break
        except Exception as e:
            e_ = e
            print(e)
    else:
        if p == 1:
            raise e_
        else:
            return []
    return items


def read_channel(url, session, cw=None):
    print_ =  get_print(cw)
    type_, username = re.find(r'/(users|creators)/([^/]+)', url, err='no username')

    info = {}
    soup = downloader.read_soup(url, session=session)
    title = (soup.find('div', class_='user-name') or soup.find('h1')).text.strip()
    info['title'] = '[Channel] {}'.format(title)

    urls = []
    urls_set = set()
    for p in range(1, 101):
        items = read_page(type_, username, p, session, cw)
        if not items:
            print('no items')
            break
        for item in items:
            if item.find('span', class_='thumb-image-container__status-text'): #2858
                continue
            url = item.a.attrs['href']
            if url in urls_set:
                print('duplicate:', url)
                continue
            urls_set.add(url)
            urls.append(url)
        s = '{} {} - {}'.format(tr_('읽는 중...'), info['title'], len(urls))
        if cw:
            cw.setTitle(s)
        else:
            print(s)

    info['urls'] = urls

    return info


class Image:
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


def read_gallery(url, session, cw=None):
    print_ = get_print(cw)

    info = {}

    soup = downloader.read_soup(url, session=session)

    h1 = soup.find('h1')
    if h1.find('a'):
        url = h1.find('a')['href']
        return read_gallery(url, sesseion, cw)
    info['title'] = h1.text.strip()
    info['url'] = setPage(url, 1)

    imgs = []
    ids = set()
    for p in range(1, 101):
        print_('p: {}'.format(p))
        url = setPage(url, p)
        soup = downloader.read_soup(url, session=session)

        view = soup.find('div', id='photo-slider')
        photos = view.findAll('a', id=lambda id: id and id.startswith('photo-'))

        if not photos:
            print_('no photos')
            break

        for photo in photos:
            img = photo['href']
            id = photo['id'].split('photo-')[1]
            referer = url
            if id in ids:
                print('duplicate:', id)
                continue
            ids.add(id)
            img = Image(img, id, referer)
            imgs.append(img)

    info['imgs'] = imgs

    return info
