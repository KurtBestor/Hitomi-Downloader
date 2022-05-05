#coding: utf8
import downloader
from utils import Downloader, Session, Soup, LazyUrl, urljoin, get_ext, clean_title
import ree as re
from translator import tr_
import clf2
from ratelimit import limits, sleep_and_retry
from m3u8_tools import M3u8_stream



class Image:

    def __init__(self, url, referer, p, session):
        self._url = url
        self._p = p
        self.url = LazyUrl(referer, self.get, self)
        self.session = session

    @sleep_and_retry
    @limits(2, 1)
    def get(self, referer):
        soup = downloader.read_soup(self._url, referer, session=self.session)
        div = soup.find('div', id='display_image_detail')
        url = urljoin(self._url, div.find('img').parent['href'])
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

        
@Downloader.register
class Downloader_hentaicosplay(Downloader):
    type = 'hentaicosplay'
    URLS = ['hentai-cosplays.com', 'porn-images-xxx.com']
    icon = None
    display_name = 'Hentai Cosplay'
    MAX_CORE = 4

    @classmethod
    def fix_url(cls, url):
        url = re.sub(r'/page/[0-9]+', '', url)
        url = re.sub(r'/attachment/[0-9]+', '', url)
        url = re.sub(r'([a-zA-Z]+\.)hentai-cosplays\.com', 'hentai-cosplays.com', url)
        url = re.sub(r'.com/story/', '.com/image/', url)
        return url

    def init(self):
        self.session = Session()

    def read(self):
        if '/video/' in self.url:
            res = clf2.solve(self.url, session=self.session, cw=self.cw)
            soup = Soup(res['html'])
            title = soup.find('h1', id='post_title').text.strip()
            self.title = title
            view = soup.find('div', id='post')
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
        title = soup.find('h2').text
        paginator = soup.find('div', id='paginator')
        pages = [self.url]
        for a in paginator.findAll('a'):
            href = a.get('href')
            if not href:
                continue
            href = urljoin(self.url, href)
            if href not in pages:
                pages.append(href)

        imgs = []
        for i, page in enumerate(pages):
            if page == self.url:
                soup_page =  soup
            else:
                soup_page = downloader.read_soup(page, session=self.session)
            view = soup_page.find('div', id='post')
            for img in view.findAll('img'):
                href = img.parent['href']
                href = urljoin(page, href)
                img = Image(href, page, len(imgs), self.session)
                imgs.append(img)
            self.cw.setTitle('{} {} ({} / {})'.format(tr_('읽는 중...'), title, i+1, len(pages)))

        for img in imgs:
            self.urls.append(img.url)

        self.title = clean_title(title)

