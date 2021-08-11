import downloader
from utils import Soup, try_n, Downloader, urljoin, get_print, Session, clean_url, clean_title, LazyUrl, get_ext, fix_title, lazy, get_imgs_already
from translator import tr_
import page_selector
import utils
from time import sleep
import clf2
import ree as re
from ratelimit import limits, sleep_and_retry


class Image(object):
    def __init__(self, url, page, p):
        ext = get_ext(url)
        if ext.lower()[1:] not in ['jpg', 'jpeg', 'bmp', 'png', 'gif', 'webm', 'webp']:
            ext = '.jpg'
        self.filename = '{}/{:04}{}'.format(page.title, p, ext)
        self.url = LazyUrl(page.url, lambda _: url, self)


class Page(object):
    def __init__(self, title, url):
        self.title = clean_title(title)
        self.url = url
        self.id = int(re.find('/(comic|webtoon)/([0-9]+)', url, err='no id')[1])


@Downloader.register
class Downloader_manatoki(Downloader):
    type = 'manatoki'
    URLS = [r'regex:(mana|new)toki[0-9]*\.(com|net)']
    MAX_CORE = 4

    @try_n(2)
    def init(self):
        self.session, self.soup, url = get_soup(self.url)
        self.url = self.fix_url(url)

        # 2377
        list = self.soup.find(attrs={'data-original-title': '목록'})
        if list:
            url = urljoin(self.url, list.parent['href'])
            nav = self.soup.find('div', class_='toon-nav')
            select = nav.find('select', {'name': 'wr_id'})
            for i, op in enumerate(select.findAll('option')[::-1]):
                if 'selected' in op.attrs:
                    break
            else:
                raise Exception('no selected option')
            self.session, self.soup, url = get_soup(url)
            url_page = self.fix_url(url)
            
            for i, page in enumerate(get_pages(url_page, self.soup)):
                if page.id == int(op['value']):
                    break
            else:
                raise Exception('can not find page')
            self.cw.range_p = [i]
            self.url = url_page

        self.name

    @classmethod
    def fix_url(cls, url):
        # 2377
        m = re.find(r'/board.php\?bo_table=([0-9a-zA-Z_]+)&wr_id=([0-9]+)', url)
        if m:
            return urljoin(url, '/{}/{}'.format(*m))
        return url.split('?')[0]

    @classmethod
    def key_id(cls, url):
        return '/'.join(url.split('/')[3:5])

    @lazy
    def name(self):
        artist = get_artist(self.soup)
        title = self.soup.find('meta', {'name':'subject'})['content'].strip()
        return fix_title(self, title, artist)

    def read(self):
        self.title = tr_('읽는 중... {}').format(self.name)
        self.artist = get_artist(self.soup)

        imgs = get_imgs(self.url, self.name, self.soup, self.session, self.cw)
        
        for img in imgs:
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = self.name



def get_artist(soup):
    view = soup.find('div', class_='view-title')
    text = view.text.replace('\n', '#')
    artist = re.find('작가[ #]*:[ #]*(.+?)#', text, default='N/A').strip()
    return artist


@sleep_and_retry
@limits(1, 10)
def get_soup(url, session=None):
    if session is None:
        session = Session()
    res = clf2.solve(url, session=session)
    soup = Soup(res['html'], apply_css=True)
    
    return session, soup, res['url']


def get_pages(url, soup):
    list = soup.find('ul', class_='list-body')
    pages = []
    for item in list.findAll('div', 'wr-subject'):
        for span in item.a.findAll('span'):
            span.decompose()
        title = item.a.text.strip()
        href = item.a['href']
        href = urljoin(url, href)
        page = Page(title, href)
        pages.append(page)
    if not pages:
        raise Exception('no pages')
    return pages[::-1]


@page_selector.register('manatoki')
def f(url):
    session, soup, url = get_soup(url)
    list = soup.find('ul', class_='list-body')
    if list is None:
        raise Exception(tr_('목록 주소를 입력해주세요'))
    pages = get_pages(url, soup)
    return pages


def get_imgs(url, title, soup=None, session=None, cw=None):
    print_ = get_print(cw)
    
    if soup is None or session is None:
        session, soup, url = get_soup(url, session)

    pages = get_pages(url, soup)
    pages = page_selector.filter(pages, cw)

    imgs = []
    for i, page in enumerate(pages):
        imgs_already = get_imgs_already('manatoki', title, page, cw)
        if imgs_already:
            imgs += imgs_already
            continue
        
        imgs_ = get_imgs_page(page, title, url, session, cw)
        imgs += imgs_

        s = '{} {} / {}  ({} / {})'.format(tr_('읽는 중...'), title, page.title, i+1, len(pages))
        print_('{} {}'.format(page.title, len(imgs_)))
        if cw is not None:
            if not cw.alive:
                return
            cw.setTitle(s)
        else:
            print('read page... {}    ({})'.format(page.url, len(imgs)))

    return imgs


@try_n(4)
def get_imgs_page(page, title, referer, session, cw):
    print_ = get_print(cw)
    #sleep(2)
    #html = downloader.read_html(page.url, referer, session=session)
    #soup = Soup(html)

    # 2183
    session, soup, page.url = get_soup(page.url, session)

    title_page = clean_title(soup.find('span', class_='page-desc').text.strip())
    if page.title != title_page:
        print_('{} -> {}'.format(page.title, title_page))
        page.title = title_page
    
    views = soup.findAll('div', class_='view-content')\
            + soup.findAll('div', class_='view-padding')
    if not views:
        raise Exception('no views')

    hash = re.find(r'''data_attribute *: *['"](.+?)['"]''', soup.html)
    print_('hash: {}'.format(hash))
    if hash is None:
        raise Exception('no hash')
    
    imgs = []
    for view in views:
        if view is None:
            continue
        for img in view.findAll('img'):
            if not isVisible(img):
                continue
            src = img.get('data-{}'.format(hash))
            src = src or img.get('content') # https://manatoki77.net/comic/5266935
            if not src:
                continue
            img = urljoin(page.url, src)
            if '/img/cang' in img:
                continue
            if '/img/blank.gif' in img:
                continue
            img = Image(img, page, len(imgs))   
            imgs.append(img)

##    if not imgs:
##        raise Exception('no imgs')

    return imgs


def isVisible(tag):
    while tag:
        if re.search('display: *none', tag.get('style', ''), re.IGNORECASE):
            return False
        tag = tag.parent
    return True
