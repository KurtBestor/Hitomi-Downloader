#coding: utf-8
#https://chan.sankakucomplex.com/
#https://idol.sankakucomplex.com/
#https://beta.sankakucomplex.com/
#https://sankaku.app/
#http://white.sankakucomplex.com/
#https://www.sankakucomplex.com/
import downloader
import ree as re
import os
from utils import Downloader, LazyUrl, urljoin, query_url, get_max_range, get_print, Soup, lazy, Session, clean_title, check_alive
from translator import tr_
import urllib
import sys
from timee import sleep
import constants
from error_printer import print_error
from constants import clean_url
from ratelimit import limits, sleep_and_retry
from urllib.parse import quote
import errors



class Downloader_sankaku(Downloader):
    type = 'sankaku'
    URLS = ['chan.sankakucomplex.com', 'idol.sankakucomplex.com', 'www.sankakucomplex.com']
    MAX_CORE = 4
    display_name = 'Sankaku Complex'
    ACCEPT_COOKIES = [r'(.*\.)?(sankakucomplex\.com|sankaku\.app)']

    def init(self):
        type = self.url.split('sankakucomplex.com')[0].split('//')[-1].strip('.').split('.')[-1]
        if type == '':
            type = 'www'
        if type not in ['chan', 'idol', 'www']:
            raise Exception('Not supported subdomain')
        self.type_sankaku = type
        self.url = self.url.replace('&commit=Search', '')
        self.url = clean_url(self.url)
        self.session = Session()

    @lazy
    def soup(self):
        html = downloader.read_html(self.url, session=self.session)
        return Soup(html)

    @classmethod
    def fix_url(cls, url):
        if 'sankakucomplex.com' not in url:
            url = url.replace(' ', '+')
            while '++' in url:
                url = url.replace('++', '+')
            url = quote(url)
            url = url.replace('%2B', '+')
            url = url.replace('%20', '+')#
            if url.startswith('[chan]'):
                type = 'chan'
                url = url.replace('[chan]', '', 1).strip()
            elif url.startswith('[idol]'):
                type = 'idol'
                url = url.replace('[idol]', '', 1).strip()
            elif url.startswith('[www]'):
                type = 'www'
                url = url.replace('[www]', '', 1).strip()
            else:
                raise Exception('Not supported subdomain')
            url = 'https://{}.sankakucomplex.com/?tags={}'.format(type, url)
        return url.replace('http://', 'https://')

    @lazy
    def id(self):
        if self.type_sankaku == 'www':
            id = '[www] ' + self.soup.find('h1', class_='entry-title').text.strip()
        else:
            if '/post/show/' in self.url:
                id = get_id(self.url, self.soup)
            else:
                qs = query_url(self.url)
                tags = qs.get('tags', [])
                tags.sort()
                id = ' '.join(tags)
                if not id:
                    id = 'N/A'
            id = '[{}] {}'.format(self.type_sankaku, id)
        return clean_title(id)

    @property
    def name(self):
        return self.id

    def read(self):
        ui_setting = self.ui_setting
        self.title = self.name

        types = ['img', 'gif', 'video']
        if ui_setting.exFile.isChecked():
            if ui_setting.exFileImg.isChecked():
                types.remove('img')
            if ui_setting.exFileGif.isChecked():
                types.remove('gif')
            if ui_setting.exFileVideo.isChecked():
                types.remove('video')

        if self.type_sankaku == 'www':
            imgs = get_imgs_www(self.url, self.soup)
        else:
            info = get_imgs(self.url, self.name, cw=self.cw, d=self, types=types, session=self.session)
            self.single = info['single']
            imgs = info['imgs']

        for img in imgs:
            if isinstance(img, str):
                self.urls.append(img)
            else:
                self.urls.append(img.url)

        self.title = self.name


def get_imgs_www(url, soup):
    imgs = []
    view = soup.find('div', class_='entry-content')
    for img in view.findAll('img'):
        img = img.attrs.get('data-lazy-src')
        if not img: # no script
            continue
        img = urljoin(url, img)
        if img in imgs:
            print('duplicate', img)
            continue
        imgs.append(img)
    return imgs


@LazyUrl.register
class LazyUrl_sankaku(LazyUrl):
    type = 'sankaku'
    def dump(self):
        return {
            'type': self.image.type,
            'id': self.image.id,
            'url': self._url,
            'referer': self.image.referer,
            'cw': self.CW,
            'd': self.DOWNLOADER,
            'local': self.image.local,
            'session': self.SESSION,
            }
    @classmethod
    def load(cls, data):
        img = Image(data['type'], data['id'], data['url'], data['referer'], data['local'], data['cw'], data['d'], data['session'])
        return img.url


class Image:
    filename = None
    def __init__(self, type, id, url, referer, local=False, cw=None, d=None, session=None):
        self.type = type
        self.id = id
        self.referer = referer
        self.cw = cw
        self.d = d
        self.local = local
        self.session = session
        if local:
            self.url = url
            self.filename = os.path.basename(url)
        else:
            self.url = LazyUrl_sankaku(url, self.get, self)

    def get(self, url):
        cw = self.cw
        d = self.d
        print_ = get_print(cw)

        for try_ in range(4):
            wait(cw)
            html = ''
            try:
                html = downloader.read_html(url, referer=self.referer, session=self.session)
                #url = 'https:' + re.findall('[Oo]riginal:? ?<a href="(//[0-9a-zA-Z_-]{2,2}.sankakucomplex.com/data/.{0,320}?)"', html)[0]
                soup = Soup(html)
                highres = soup.find(id='highres')
                url = urljoin(url, highres['href'] if highres else soup.find(id='image')['src'])
                break
            except Exception as e:
                e_msg = print_error(e)
                if '429 Too many requests'.lower() in html.lower():
                    t_sleep = 120 * min(try_ + 1, 2)
                    e = '429 Too many requests... wait {} secs'.format(t_sleep)
                elif 'post-content-notification' in html: # sankaku plus
                    print_('Sankaku plus: {}'.format(self.id))
                    return ''
                else:
                    t_sleep = 5
                s = '[Sankaku] failed to read image (id:{}): {}'.format(self.id, e)
                print_(s)
                sleep(t_sleep, cw)
        else:
            raise Exception('can not find image (id:{})\n{}'.format(self.id, e_msg))
        soup = Soup('<p>{}</p>'.format(url))
        url = soup.string
        ext = os.path.splitext(url)[1].split('?')[0]
        self.filename = '{}{}'.format(self.id, ext)
        return url


def setPage(url, page):
    # Always use HTTPS
    url = url.replace('http://', 'https://')

    # Change the page
    if 'page=' in url:
        url = re.sub(r'page=[0-9]*', 'page={}'.format(page), url)
    else:
        url += '&page={}'.format(page)

    return url


@sleep_and_retry
@limits(1, 6)
def wait(cw):
    check_alive(cw)


def get_imgs(url, title=None, cw=None, d=None, types=['img', 'gif', 'video'], session=None):
    print_ = get_print(cw)
    print_('types: {}'.format(', '.join(types)))
    if 'chan.sankakucomplex' in url:
        type = 'chan'
    elif 'idol.sankakucomplex' in url:
        type = 'idol'
    else:
        raise Exception('Not supported subdomain')

    info = {}
    info['single'] = False

    if '/post/show/' in url:
        info['single'] = True
        id = get_id(url)
        info['imgs'] = [Image(type, id, url, None, cw=cw, d=d)]
        return info

    # Range
    max_pid = get_max_range(cw)

    local_ids = {}
    if cw is not None:
        dir = cw.downloader.dir
        try:
            names = os.listdir(dir)
        except Exception as e:
            print(e)
            names = []
        for name in names:
            id = os.path.splitext(name)[0]
            local_ids[id] = os.path.join(dir, name)

    imgs = []
    page = 1
    url_imgs = set()
    url_old = 'https://{}.sankakucomplex.com'.format(type)
    if cw is not None:
        cw.setTitle('{}  {}'.format(tr_('읽는 중...'), title))
    while len(imgs) < max_pid:
        #if page > 25: # Anonymous users can only view 25 pages of results
        #    break
        wait(cw)
        #url = setPage(url, page)
        print_(url)
        try:
            html = downloader.read_html(url, referer=url_old, session=session)
        except Exception as e: #3366
            print_(print_error(e))
            break
        if '429 Too many requests'.lower() in html.lower():
            print_('429 Too many requests... wait 120 secs')
            sleep(120, cw)
            continue
        page += 1
        url_old = url
        soup = Soup(html)
        banner = soup.find('div', class_='has-mail')
        if banner: #5861
            banner.decompose()
        banner = soup.find('div', class_='popular-previews')
        if banner: #6171
            banner.decompose()
        err = soup.find('div', class_='post-premium-browsing_error')
        if err and not imgs:
            raise errors.LoginRequired(err.text.strip())
        articles = soup.findAll('span', {'class': 'thumb'})

        if not articles:
            break

        for article in articles:
            # 1183
            tags = article.find('img', class_='preview').attrs['title'].split()
            if 'animated_gif' in tags:
                type_ = 'gif'
            elif 'animated' in tags or 'webm' in tags or 'video' in tags or 'mp4' in tags: # 1697
                type_ = 'video'
            else:
                type_ = 'img'
            if type_ not in types:
                continue

            url_img = article.a.attrs['href']
            if not url_img.startswith('http'):
                url_img = urljoin('https://{}.sankakucomplex.com'.format(type), url_img)
            if '/post/show/' not in url_img: # sankaku plus
                continue
            id = re.find(r'p([0-9]+)', article['id'], err='no id') #5892
            #print_(article)
            if id in local_ids:
                #print('skip', id)
                local = True
            else:
                local = False
            #print(url_img)
            if url_img not in url_imgs:
                url_imgs.add(url_img)
                if local:
                    url_img = local_ids[id]
                img = Image(type, id, url_img, url, local=local, cw=cw, d=d)
                imgs.append(img)
                if len(imgs) >= max_pid:
                    break

        try:
            # For page > 50
            pagination = soup.find('div', class_='pagination')
            url = urljoin('https://{}.sankakucomplex.com'.format(type), pagination.attrs['next-page-url'])
##            #3366
##            p = int(re.find(r'[?&]page=([0-9]+)', url, default=1))
##            if p > 100:
##                break
        except Exception as e:
            print_(print_error(e))
            #url = setPage(url, page)
            break

        if cw is not None:
            cw.setTitle('{}  {} - {}'.format(tr_('읽는 중...'), title, len(imgs)))
        else:
            print(len(imgs), 'imgs')

    if not imgs:
        raise Exception('no images')

    info['imgs'] = imgs

    return info


def get_id(url, soup=None):
    if soup is None:
        html = downloader.read_html(url)
        soup = Soup(html)
    return soup.find('input', id='post_id')['value']
