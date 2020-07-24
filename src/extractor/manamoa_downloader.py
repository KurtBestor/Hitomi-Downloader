#coding:utf8
# uncompyle6 version 3.5.0
# Python bytecode 2.7 (62211)
# Decompiled from: Python 2.7.16 (v2.7.16:413a49145e, Mar  4 2019, 01:30:55) [MSC v.1500 32 bit (Intel)]
# Embedded file name: manamoa_downloader.pyo
# Compiled at: 2019-10-14 21:33:40
import downloader
import ree as re
from utils import urljoin, Downloader, Soup, LazyUrl, try_n, size_folder, get_outdir, clean_url, get_print, html_unescape, fix_title, query_url, update_url_query, Session, cut_pair, uuid
import json
from fucking_encoding import clean_title
from timee import sleep, clock
import os
from translator import tr_
import page_selector, constants, math
from error_printer import print_error
from capture import capture, Empty
from io import BytesIO
from random import Random
import clf2
SKIP = True


class Url_alter(object):
    c = 0
    c_s3 = 0
    
    def __init__(self, img, img1):
        self.img = img
        self.img1 = img1

    def __call__(self):
        imgs = []
        if self.img:
            imgs.append(self.img)
        if self.img1:
            imgs.append(self.img1)
        
        img = imgs[self.c % len(imgs)]
        
        # https://manamoa18.net/js/viewer.b.js?v=70
        if img == self.img:
            if self.c_s3 % 2:
                if 'img.' in img:
                    img = img.replace('img.', 's3.')
                else:
                    img = img.replace('://', '://s3.')
            self.c_s3 += 1
                
        self.c += 1

        if self.c == downloader.MAX_TRY_ALTER: # 1649
            img = img.replace('//', '/').replace(':/', '://')
        
        return img

                
class Image(object):

    def __init__(self, url, page, p, img1=None):
        ext = os.path.splitext(url.split('?')[0])[1]
        if ext.lower()[1:] not in ('jpg', 'jpeg', 'bmp', 'png', 'gif', 'webm', 'webp'):
            ext = '.jpg'
        self.filename = (u'{}/{:04}{}').format(clean_title(page.title), p, ext)

        # img1, img, img1, s3, img1, img, img1, s3
        #self._url = img1 or url
        #url_alter = Url_alter(url, img1)

        # img, s3, img1, img, img1, s3, img1, img_without_//
        self._url = url or img1
        url_alter = Url_alter(url, img1)
        url_alter.c_s3 += 1

        if not self._url:
            raise Exception('no url')
        
        self.url = LazyUrl(page.url, lambda _: self._url, self, url_alter=url_alter)


class Page(object):

    def __init__(self, title, url):
        if title.startswith('NEW'):
            title = title.replace('NEW', '', 1).strip()
        title = fix_title_page(title)
        self.title = clean_title(title)
        self.url = url
        self.id = int(re.findall('wr_id=([0-9]+)', url)[0])


def fix_title_page(title):
    title = title.replace('\t', ' ')
    while '  ' in title:
        title = title.replace('  ', ' ')

    return title


def get_title_page(soup):
    text = soup.find('div', class_='toon-title')
    for span in text.findAll('span'):
        span.decompose()

    text = text.text.strip()
    text = fix_title_page(text)
    
    return text


def solve_protection(url, session, cw=None):
    print_ = get_print(cw)
    print_('Solve protection')
    r = clf2.solve(url, session=session, cw=cw)
    html = r['html'] # 1566
    '''
    session = clf2.Session(session)
    r = session.get(url)
    html = r.text
    '''
    if constants.admin:
        with open('test_manamoa.html', 'w') as f:
            f.write(html.encode('utf8'))
    #html = read_html(page.url, session=session)
    return html


@Downloader.register
class Downloader_manamoa(Downloader):
    type = 'manamoa'
    URLS = ['regex:manamoa[0-9]*\\.net']
    MAX_CORE = 16
    _soup = None
    _session = None
    pages = None

    def init(self):
        self.url = url = self.url.replace('manamoa_', '')
        self.url = fix_url(self.url, cw=self.customWidget)
        if 'board.php' in self.url:
            data = get_soup(self.url, cw=self.customWidget)
            soup, session = data['soup'], data['session']
            self.url = data['url']
            html = str(soup)
            text = get_title_page(soup)
            url = find_url(html, self.url)
            if self.customWidget.range_p is None:
                self.pages = [
                 Page(text, self.url)]
            self.customWidget.print_(u'redirect: {}'.format(url))
            self.url = url
        self.url = self.url.replace('http://', 'https://')

    @property
    def id(self):
        return self.url

    @property
    def soup(self):
        if self._soup is None:
            data = get_soup(self.url, cw=self.customWidget)
            self._soup, self._session = data['soup'], data['session']
            self.url = data['url']
        return self._soup

    @property
    def session(self):
        soup = self.soup
        return self._session

    @session.setter
    def session(self, value):
        self._session = value

    @property
    def name(self):
        soup = self.soup
        title = soup.find(class_='manga-subject').div.text.strip()
        if not title:
            raise Exception('No title')
        artist = get_artist(soup)
        if artist:
            self.customWidget.artist = artist
        else:
            artist = 'N/A'
        title = fix_title(self, title, artist)
        return title

    def read(self):
        name = self.name
        self.fix_dirname(name)
        self.imgs = get_imgs(self.url, name, self.soup, self.session, cw=self.customWidget, pages=self.pages)
        for img in self.imgs:
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = name


def real_url(url, session=None, cw=None):
    print_ = get_print(cw)
    if session is None:
        session = Session()
    data = clf2.solve(url, session=session, cw=cw)
    url_new = data['url']
    print('url_new:', url_new)
    if url_new != url:
        url_new = urljoin(url_new, '/'+u'/'.join(url.split('/')[3:]))#
        print_(u'[redirect domain] {} -> {}'.format(url, url_new))
    return url_new


@try_n(4, sleep=30)
def get_soup(url, cw=None, session=None):
    print_ = get_print(cw)
    if session is None:
        session = Session()
    list = 'page.php?' in url
    url_new = real_url(url, session=session, cw=cw)
    html = read_html(url_new, session)
    soup = Soup(html)
    if isProtected(html):
        html = solve_protection(url_new, session, cw)
        soup = Soup(html)
    body = soup.find('body')
    if not body or not body.text:
        print_('No body')
        raise Exception('No body')
    if list and soup.find(class_='manga-subject') is None:
        print_('No subject')
        raise Exception('No subject')
    data = {}
    data['soup'] = soup
    data['session'] = session
    data['url'] = url_new
    data['html'] = html
    return data


def get_pages(soup, url, cw=None, skip=False):
    print_ = get_print(cw)
    lists = soup.findAll('div', class_='chapter-list')[-1:]
    items = []
    for list in lists:
        items += list.findAll('div', class_='slot')

    if not skip:
        items = items[::-1]

    titles = {}
    pages = []
    for item in items:
        title = item.find('div', class_='title')
        for span in title.findAll('span'):
            span.decompose()

        text = title.text.strip()
        href = item.a.attrs['href']
        href = urljoin(url, href)
        if text in titles:
            if skip:
                print_(u'skip: {} {}'.format(text, href))
                continue
            else:
                print_(u'duplicate: {} {}'.format(text, href))
                titles[text] += 1
                c = titles[text]
                text += u' ({})'.format(c)
        else:
            titles[text] = 1
        page = Page(text, href)
        pages.append(page)

    if not pages:
        raise Exception('no pages')
    if skip:
        pages = pages[::-1]
    return pages


@page_selector.register('manamoa')
@try_n(4)
def f(url):
    if 'board.php' in url:
        raise Exception(tr_(u'\ubaa9\ub85d \uc8fc\uc18c\ub97c \uc785\ub825\ud574\uc8fc\uc138\uc694'))
    data = get_soup(url)
    soup, session = data['soup'], data['session']
    pages = get_pages(soup, url)
    return pages


def isDoneFolder(dir, page, cw=None):
    if size_folder(dir) <= 0:
        return False
    return True


def get_imgs(url, title, soup=None, session=None, cw=None, pages=None):
    if soup is None or session is None:
        data = get_soup(url, cw=cw)
        soup, session = data['soup'], data['session']
    if pages is None:
        pages = get_pages(soup, url, cw)
        pages = page_selector.filter(pages, cw)
    imgs = []
    for i, page in enumerate(pages):
        dir = os.path.join(get_outdir('manamoa'), title, page.title)
        print('test dir:', dir)
        if SKIP and isDoneFolder(dir, page, cw=cw):
            cw.print_((u'Skip: {}').format(page.title))
            for p, img in enumerate(sorted(os.listdir(dir))):
                img = os.path.join(dir, img)
                imgs.append(img)

            continue
        if cw is not None:
            if not cw.alive:
                return
            cw.setTitle((u'{} {} / {}  ({} / {})').format(tr_(u'\uc77d\ub294 \uc911...'), title, page.title, i + 1, len(pages)))
        imgs += get_imgs_page(page, session, cw)

    return imgs


class SeedError(Exception):
    pass


@try_n(8, sleep=20)
def get_imgs_page(page, session, cw=None, try_=1):
    print('##### get_imgs_page', try_)
    print_ = get_print(cw)
    if cw is not None and not cw.alive:
        return
    
    if True:
        try:
            imgs = get_imgs_page_legacy(page, session, cw)
            if imgs == 'seed':
                raise SeedError()
            return imgs
        except Exception as e:
            if not isinstance(e, SeedError):
                raise

    jpgs = capture(page, session, cw, ignore_error=try_>1)
    imgs = []
    rand = Random()
    rand.seed((u'{}{}').format(page.title, clock()))
    hash = uuid()
    DIR = get_outdir('manamoa')
    for p, jpg in enumerate(jpgs):
        if isinstance(jpg, Empty):
            img = Image(jpg.url, page, p)
            imgs.append(img)
            continue
        
        img_tmp = os.path.join(DIR, ('tmp{}_{:04}.jpg').format(hash, p))
        if cw is not None:
            cw.trash_can.append(img_tmp)
        if not os.path.isdir(DIR):
            try:
                os.makedirs(DIR)
            except:
                pass

        with open(img_tmp, 'wb') as (f):
            f.write(jpg)
        img = Image(u'tmp://' + img_tmp, page, p)
        imgs.append(img)

    return imgs


def isProtected(html):
    soup = Soup(html)
    if soup.find('div', class_='cf-browser-verification') or 'grecaptcha.execute(' in html or 'DDoS protection by DDoS-GUARD' in html: # 1566
        return True
    return False



def get_imgs_page_legacy(page, session, cw=None, depth=0):
    if cw is not None and not cw.alive:
        return
    print_ = get_print(cw)

    try:
        html = read_html(page.url, session)
    except Exception as e:
        print_('get_imgs_page_legacy error: {}'.format(e))
        if e.args and e.args[0] == 502:
            return []
        raise
    
    if isProtected(html):
        data = get_soup(page.url, cw=cw, session=session)
        page.url = data['url']
        html = data['html']

    soup = Soup(html, 'html5lib') # 1653

    # skip empty pages
    if not html:
        print_(u'empty page: {}'.format(page.title))
        return []

    # skip invalid pages
    err = soup.find('span', class_='cf-error-code')
    if err:
        print_(u'cf-error-code: {} ({})'.format(err.text.strip(), page.title))
        if depth > 0:
            return []
        else:
            return get_imgs_page_legacy(page, session, cw, depth+1)
    
    #page.title = get_title_page(soup)
    matches = re.findall('var img_list *= *(.+?]);', html.replace('\n', ''))
    matches1 = re.findall('var img_list1 *= *(.+?]);', html.replace('\n', ''))
    img_list = json.loads(matches[0]) if matches else []
    img_list1 = json.loads(matches1[0]) if matches1 else []

    # 1780
    img_list = [img for img in img_list if img]
    img_list1 = [img for img in img_list1 if img]
    
    # 1589
    '''
    if not img_list and not img_list1:
        print_((u'no imgs; retry... {}').format(page.title))
        raise Exception('No images')
    '''
        
    for script in soup.findAll('script'):
        script = script.text
        if 'var img_list =' in script:
            break
    else:
        raise Exception('No script')

    seed = int(re.find('view_cnt *= *([0-9]+)', script))
    chapter = int(re.find('var +chapter *= *([0-9]+)', script))
    try:
        cdn_domains = cut_pair(re.find('var +cdn_domains *= *(.+)', script), '[]')
        cdn_domains = json.loads(cdn_domains)
    except Exception as e:
        print(e)
        cdn_domains = []

    n = max(len(img_list), len(img_list1))
    img_list += [''] * (n - len(img_list))
    img_list1 += [''] * (n - len(img_list1))

    print_(u'{}    chapter:{}    seed:{}    domains:{}'.format(page.title, chapter, seed, len(cdn_domains)))
    if seed != 0:
        return 'seed'
    imgs = []
    for p, (img, img1) in enumerate(zip(img_list, img_list1)):

        # fix img url
        img = fix_img_url(img, cdn_domains, chapter, p)
        img1 = fix_img_url(img1, cdn_domains, chapter, p)
        
        img = urljoin(page.url, img) if img else ''
        img1 = urljoin(page.url, img1) if img1 else '' # most likely googledrive
        if img.strip('/').count('/') == 2: #1425
            continue
        img = Image(img, page, p, img1)
        imgs.append(img)

    return imgs


#1647
# https://manamoa26.net/js/viewer.b.js?v=90
def fix_img_url(img, cdn_domains, chapter, e):
    t = cdn_domains[(chapter + 4 * e) % len(cdn_domains)]
    img = img.replace('cdntigermask.xyz', t).replace('cdnmadmax.xyz', t).replace('filecdn.xyz', t)
    if t in img:
        img += '?quick'
    return img
    

def get_artist(soup):
    thumb = soup.find('div', class_='manga-thumbnail')
    if thumb is None:
        return
    else:
        a = thumb.find('a', class_='author')
        if a is None:
            return
        artist = a.string.strip()
        if artist == '.':
            return
        return artist


def find_url(html, url):
    href = re.findall('[\'"]([^\'"]+page.php[^\'"]+manga_detail[^\'"]+)[\'"]', html)[0]
    href = html_unescape(href)
    return urljoin(url, href)


def read_html(url, session):
    html = downloader.read_html(url, session=session)
    return html


def fix_url(url, session=None, cw=None):
    print_ = get_print(cw)
    if '&manga_name=' not in url:
        return url
    print_('fix url')
    qs = query_url(url)
    name = qs['manga_name'][0].replace('+', ' ')
    url_search = urljoin(url, '/bbs/search.php')
    url_search = update_url_query(url_search, {'stx': [name]})
    print(url_search)
    html = read_html(url_search, session=session)
    soup = Soup(html)
    posts = soup.findAll('div', class_='post-row')
    print_(('posts:').format(len(posts)))
    if len(posts) != 1:
        return url
    for a in posts[0].findAll('a'):
        href = urljoin(url, a.attrs['href'])
        if 'manga_detail' in href:
            break
    else:
        raise Exception('Failed to find link')

    if cw is not None:
        cw.gal_num = href
    return href
