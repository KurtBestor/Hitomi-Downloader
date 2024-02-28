#coding: utf8
import downloader
from utils import Downloader, Session, Soup, LazyUrl, urljoin, get_ext, clean_title, try_n, limits
import utils
import ree as re
from translator import tr_
import clf2
from m3u8_tools import M3u8_stream
from timee import sleep
import os



class Image:
    def __init__(self, url, referer, p, session):
        self._url = url
        self._referer = referer
        self._p = p
        self.url = LazyUrl(url, self.get, self)
        self.session = session

    @try_n(3, 5)
    @limits(1)
    def get(self, _=None):
        soup = downloader.read_soup(self._url, self._referer, session=self.session)
        div = soup.find('div', id='display_image_detail') or soup.find('ul', id='detail_list')
        parent = div.find('img').parent
        while not parent.get('href'):
            parent = parent.parent
        url = urljoin(self._url, parent['href'])
        ext = get_ext(url)
        self.filename = '{:04}{}'.format(self._p, ext)
        return url, self._url


class Video:

    def __init__(self, src, referer, title, session):
        ext = get_ext(src)
        if ext == '.m3u8':
            _src = src
            src = M3u8_stream(_src, referer=referer, session=session)
            ext = '.mp4'
        self.url = LazyUrl(referer, lambda _: src, self)
        self.filename = '{}{}'.format(clean_title(title), ext)



class Downloader_hentaicosplay(Downloader):
    type = 'hentaicosplay'
    URLS = ['hentai-cosplays.com', 'porn-images-xxx.com', 'hentai-img.com']
    icon = None
    display_name = 'Hentai Cosplay'
    MAX_PARALLEL = 1 # must be 1
    MAX_CORE = 4
    ACCEPT_COOKIES = [rf'(.*\.)?{domain}' for domain in URLS]

    @classmethod
    def fix_url(cls, url):
        url = re.sub(r'/page/[0-9]+', '', url)
        url = re.sub(r'/attachment/[0-9]+', '', url)
        url = re.sub(r'([a-zA-Z]+\.)hentai-cosplays\.com', 'hentai-cosplays.com', url)
        url = re.sub(r'.com/story/', '.com/image/', url)
        return url

    def init(self):
        self.session = Session()

    @try_n(2)
    def read(self):
        #4961
        ua = downloader.random_ua()
        self.print_(f'read start ua: {ua}')
        downloader.REPLACE_UA[r'hentai-cosplays\.com'] = ua
        downloader.REPLACE_UA[r'porn-images-xxx\.com'] = ua

        if '/video/' in self.url:
            res = clf2.solve(self.url, session=self.session, cw=self.cw)
            soup = Soup(res['html'])
            title = (soup.find('h1', id='post_title') or soup.find('div', id='page').find('h2')).text.strip()
            self.title = title
            view = soup.find('div', id='post') or soup.find('div', class_='video-container')
            video = view.find('video')
            src = video.find('source')['src']
            src = urljoin(self.url, src)
            video = Video(src, self.url, title, self.session)
            self.urls.append(video.url)
            self.single = True
            return

        if '/image/' not in self.url:
            raise NotImplementedError('Not a post')

        res = clf2.solve(self.url, session=self.session, cw=self.cw)
        soup = Soup(res['html'])
        title = (soup.find('h2') or soup.find('h3')).text
        paginator = soup.find('div', id='paginator') or soup.find('div', class_='paginator_area')
        pages = [self.url]
        for a in paginator.findAll('a'):
            href = a.get('href')
            if not href:
                continue
            href = urljoin(self.url, href)
            if href not in pages:
                pages.append(href)
        self.print_(f'pages: {len(pages)}')

        imgs = []
        for i, page in enumerate(pages):
            sleep(2, self.cw)
            if page == self.url:
                soup_page =  soup
            else:
                soup_page = try_n(3, 5)(downloader.read_soup)(page, session=self.session)
            view = soup_page.find('div', id='post') or soup_page.find('ul', id='detail_list')
            for img in view.findAll('img'):
                href = img.parent.get('href') or img.parent.parent.get('href')
                if not href:
                    continue
                href = urljoin(page, href)
                img = Image(href, page, len(imgs), self.session)
                imgs.append(img)
            self.print_(f'imgs: {len(imgs)}')
            self.cw.setTitle('{} {} ({} / {})'.format(tr_('읽는 중...'), title, i+1, len(pages)))

        names = {}
        dirname = utils.dir(self.type, clean_title(title), self.cw)
        try:
            files = os.listdir(dirname)
        except:
            files = []
        for file in files:
            name, ext = os.path.splitext(file)
            names[name] = ext

        for p, img in enumerate(imgs):
            name = '{:04}'.format(p)
            ext = names.get(name)
            if ext:
                self.urls.append(os.path.join(dirname, '{}{}'.format(name, ext)))
            else:
                self.urls.append(img.url)

        self.title = clean_title(title)
