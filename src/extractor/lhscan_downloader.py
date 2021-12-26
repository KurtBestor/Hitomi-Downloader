#coding:utf8
import downloader
from utils import Soup, urljoin, LazyUrl, Downloader, try_n, Session, clean_title, get_print
import os
from translator import tr_
import page_selector
import clf2
import utils
import base64
import ree as re
import errors
##from image_reader import QPixmap


class Image(object):
    def __init__(self, url, page, p):
        self._url = url
        self.url = LazyUrl(page.url, self.get, self)#, pp=self.pp)
        ext = os.path.splitext(url)[1]
        if ext.lower()[1:] not in ['jpg', 'jpeg', 'bmp', 'png', 'gif', 'webm', 'webp']:
            ext = '.jpg'
        self.filename = u'{}/{:04}{}'.format(page.title, p, ext)

    def get(self, _):
        return self._url

##    def pp(self, filename):
##        pixmap = QPixmap(filename)
##        pixmap.save(filename)
##        return filename


class Page(object):
    def __init__(self, title, url):
        self.title = clean_title(title)
        self.url = url


def get_soup_session(url, cw=None):
    print_ = get_print(cw)
    session = Session()
    res = clf2.solve(url, session=session, cw=cw)
    print_('{} -> {}'.format(url, res['url']))
    if res['url'].rstrip('/') == 'https://welovemanga.net':
        raise errors.LoginRequired()
    return Soup(res['html']), session


@Downloader.register
class Downloader_lhscan(Downloader):
    type = 'lhscan'
    URLS = [
        #'lhscan.net', 'loveheaven.net',
        'lovehug.net', 'welovemanga.net',
        ]
    MAX_CORE = 16
    display_name = 'LHScan'
    _soup = None

    def init(self):
        self._soup, self.session = get_soup_session(self.url, self.cw)
        if not self.soup.find('ul', class_='manga-info'):
            raise errors.Invalid(u'{}: {}'.format(tr_(u'목록 주소를 입력해주세요'), self.url))

    @classmethod
    def fix_url(cls, url):
        url = url.replace('lovehug.net', 'welovemanga.net')
        return url

    @property
    def soup(self):
        if self._soup is None:
            for try_ in range(8):
                try:
                    html = downloader.read_html(self.url, session=self.session)
                    break
                except Exception as e:
                    e_ = e
                    print(e)
            else:
                raise e_
            self._soup = Soup(html)
        return self._soup

    @property
    def name(self):
        title = self.soup.find('ul', class_='manga-info').find('h3').text
        return clean_title(title)

    def read(self):
        self.title = tr_(u'읽는 중... {}').format(self.name)

        imgs = get_imgs(self.url, self.name, self.session, self.soup, self.cw)

        for img in imgs:
            self.urls.append(img.url)

        self.title = self.name


@try_n(8)
def get_imgs_page(page, referer, session, cw=None):
    print_ = get_print(cw)
    print_(page.title)
    
    html = downloader.read_html(page.url, referer, session=session)
    if clf2._is_captcha(Soup(html)): #4124
        html = clf2.solve(page.url, session, cw)['html']
    if not html:
        raise Exception('empty html')
    html = html.replace('{}='.format(re.find(r"\$\(this\)\.attr\('(.+?)'", html, err='no cn')), 'data-src=')
    soup = Soup(html)

    view = soup.find('div', class_='chapter-content')

    if not view:
        raise Exception('no chapter-content')

    imgs = []
    for img in soup.findAll('img', class_='chapter-img'):
        src = img.get('data-pagespeed-lazy-src') or img.get('data-src') or img.get('data-srcset') or img.get('data-aload') or img['src']
        try:
            src = base64.b64decode(src).strip().decode('utf8')
        except:
            pass
        src0 = src
        src = src.replace('welovemanga.net', '1')#
        src = urljoin(page.url, src).strip()
        if 'Credit_LHScan_' in src or '5e1ad960d67b2_5e1ad962338c7' in src:
            continue
        if 'fe132b3d32acc39f5adcea9075bedad4LoveHeaven' in src:
            continue
        if 'LoveHug_600cfd96e98ff.jpg' in src:
            continue
        if 'image_5f0ecf23aed2e.png' in src:
            continue
        if '/uploads/lazy_loading.gif' in src:
            continue
        if not imgs:
            print_(src0)
        img = Image(src, page, len(imgs))
        imgs.append(img)

    return imgs


def get_pages(url, session, soup=None, cw=None):
    if soup is None:
        html = downloader.read_html(url, session=session)
        soup = Soup(html)
        
    tab = soup.find('ul', class_='list-chapters')

    pages = []
    for li in tab.findAll('li'):
        text = li.find('div', class_='chapter-name').text.strip()
        href = li.parent['href']
        href = urljoin(url, href)
        page = Page(text, href)
        pages.append(page)

    if not pages:
        raise Exception('no pages')

    return pages[::-1]


@page_selector.register('lhscan')
@try_n(4)
def f(url):
    soup, session = get_soup_session(url)
    pages = get_pages(url, session, soup=soup)
    return pages


@try_n(2)
def get_imgs(url, title, session, soup=None, cw=None):
    if soup is None:
        html = downloader.read_html(url, session=session)
        soup = Soup(html)

    pages = get_pages(url, session, soup, cw)
    pages = page_selector.filter(pages, cw)

    imgs = []
    for i, page in enumerate(pages):
        imgs += get_imgs_page(page, url, session, cw)
        s = u'{} {} / {}  ({} / {})'.format(tr_(u'읽는 중...'), title, page.title, i+1, len(pages))
        if cw is not None:
            if not cw.alive:
                return
            cw.setTitle(s)
        else:
            print(s)

    return imgs
