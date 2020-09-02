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
from utils import Downloader, LazyUrl, urljoin, query_url, get_max_range, get_print, Soup, lazy, Session, clean_title
from translator import tr_
import urllib
import sys
from timee import sleep
import constants
from sankaku_login import login
from error_printer import print_error
from constants import clean_url


@Downloader.register
class Downloader_sankaku(Downloader):
    type = 'sankaku'
    URLS = ['chan.sankakucomplex.com', 'idol.sankakucomplex.com', 'www.sankakucomplex.com']
    MAX_CORE = 2
    
    def init(self):
        self.url = self.url.replace('sankaku_', '')
        if '/post/' in self.url:
            return self.Invalid('Single post is not supported')
        
        if 'sankakucomplex.com' in self.url:
            self.url = self.url.replace('http://', 'https://')
            type = self.url.split('sankakucomplex.com')[0].split('//')[-1].strip('.').split('.')[-1]
            if type == '':
                type = 'www'
            if type not in ['chan', 'idol', 'www']:
                raise Exception('Not supported subdomain')
        else:
            url = self.url
            url = url.replace(' ', '+')
            while '++' in url:
                url = url.replace('++', '+')
            url = urllib.quote(url)
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
            self.url = u'https://{}.sankakucomplex.com/?tags={}'.format(type, url)
        self.type_sankaku = type
        self.url = self.url.replace('&commit=Search', '')
        self.url = clean_url(self.url)
        self.session = Session()

        if self.type_sankaku != 'www':
            login(type, self.session, self.customWidget)

        if self.type_sankaku == 'www':
            html = downloader.read_html(self.url, session=self.session)
            self.soup = Soup(html)

    @lazy
    def id(self):
        if self.type_sankaku == 'www':
            id = u'[www] ' + self.soup.find('h1', class_='entry-title').text.strip()
        else:
            qs = query_url(self.url)
            tags = qs.get('tags', [])
            tags.sort()
            id = u' '.join(tags)
            if not id:
                id = u'N/A'
            id = '[{}] '.format(self.type_sankaku) + id
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
            imgs = get_imgs(self.url, self.name, customWidget=self.customWidget, d=self, types=types, session=self.session)

        for img in imgs:
            if isinstance(img, str):
                self.urls.append(img)
            else:
                self.urls.append(img.url)

        self.title = self.name


def get_imgs_www(url, soup):
    imgs = []
    view = soup.find('div', class_="entry-content")
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


class Image(object):
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
        
        sleep(4)
        for try_ in range(4):
            html = ''
            try:
                html = downloader.read_html(url, referer=self.referer, session=self.session)
                #url = 'https:' + re.findall('[Oo]riginal:? ?<a href="(//[0-9a-zA-Z_-]{2,2}.sankakucomplex.com/data/.{0,320}?)"', html)[0]
                soup = Soup(html)
                url = 'https:' + soup.find(id="highres").get('href')
                break
            except Exception as e:
                if '429 Too many requests'.lower() in html.lower():
                    t_sleep = 120 * min(try_ + 1, 2)
                    e = '429 Too many requests... wait {} secs'.format(t_sleep)
                else:
                    t_sleep = 10
                s = u'[Sankaku] failed to read image (id:{}): {}'.format(self.id, e)
                print_(s)
                for i in range(t_sleep):
                    sleep(1)
                    if cw is not None and not cw.alive:
                        raise Exception('customwidget is dead')
                
        else:
            raise Exception('can not find image (id:{})'.format(self.id))
        soup = Soup(u'<p>{}</p>'.format(url))
        url = soup.string
        ext = os.path.splitext(url)[1].split('?')[0]
        self.filename = u'{}{}'.format(self.id, ext)
        return url


def setPage(url, page):
    # Always use HTTPS
    url = url.replace('http://', 'https://')

    # Change the page
    if 'page=' in url:
        url = re.sub('page=[0-9]*', 'page={}'.format(page), url)
    else:
        url += '&page={}'.format(page)
        
    return url


def get_imgs(url, title=None, customWidget=None, d=None, types=['img', 'gif', 'video'], session=None):
    if False:#
        raise NotImplementedError('Not Implemented')
    print_ = get_print(customWidget)
    print_(u'types: {}'.format(', '.join(types)))
    
    # Range
    max_pid = get_max_range(customWidget, 2000)

    local_ids = {}
    if customWidget is not None:
        dir = customWidget.downloader.dir
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
    if 'chan.sankakucomplex' in url:
        type = 'chan'
    elif 'idol.sankakucomplex' in url:
        type = 'idol'
    else:
        raise Exception('Not supported subdomain')
    url_old = 'https://{}.sankakucomplex.com'.format(type)
    if customWidget is not None:
        customWidget.exec_queue.put((customWidget, u"customWidget.setTitle(u'{}  {}')".format(tr_(u'읽는 중...'), title)))
    while len(imgs) < max_pid:
        #if page > 25: # Anonymous users can only view 25 pages of results
        #    break
        sleep(1)#
        #url = setPage(url, page)
        print_(url)
        html = downloader.read_html(url, referer=url_old, session=session)
        if '429 Too many requests'.lower() in html.lower():
            print_('429 Too many requests... wait 120 secs')
            for i in range(120):
                sleep(1)
                if customWidget and not customWidget.alive:
                    return []
            continue
        page += 1
        url_old = url
        soup = Soup(html)
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
            id = re.findall('show/([0-9]+)', url_img)[0]
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
                img = Image(type, id, url_img, url, local=local, cw=customWidget, d=d)
                imgs.append(img)
                if len(imgs) >= max_pid:
                    break
        if customWidget and not customWidget.alive:
            break

        try:
            # For page > 50
            pagination = soup.find('div', class_='pagination')
            url = urljoin('https://{}.sankakucomplex.com'.format(type), pagination.attrs['next-page-url'])
        except Exception as e:
            print_(print_error(e)[-1])
            #url = setPage(url, page)
            break
        
        if customWidget is not None:
            customWidget.setTitle(u'{}  {} - {}'.format(tr_(u'읽는 중...'), title, len(imgs)))
        else:
            print(len(imgs), 'imgs')

    if not imgs:
        raise Exception('no images')
    
    return imgs

