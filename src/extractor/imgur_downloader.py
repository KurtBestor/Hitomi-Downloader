# uncompyle6 version 3.5.0
# Python bytecode 2.7 (62211)
# Decompiled from: Python 2.7.16 (v2.7.16:413a49145e, Mar  4 2019, 01:30:55) [MSC v.1500 32 bit (Intel)]
# Embedded file name: imgur_downloader.pyo
# Compiled at: 2019-10-07 05:58:14
import downloader
from utils import Downloader, Soup, try_n, urljoin, get_max_range, clean_title, cut_pair
import ree as re, json, os
from timee import sleep
from translator import tr_

@Downloader.register
class Downloader_imgur(Downloader):
    type = 'imgur'
    URLS = ['imgur.com']
    MAX_CORE = 16

    def init(self):
        self.info = get_info(self.url)

    @property
    def id_(self):
        return re.find('imgur.com/.+?/([0-9a-zA-Z]+)', self.url)

    @property
    def name(self):
        title = self.info['title'] or 'N/A'
        return clean_title(title, n=100)

    def read(self):
        imgs = get_imgs(self.url, self.info, self.cw)
        for img in imgs:
            ext = os.path.splitext(img.split('?')[0])[1]
            if len(imgs) > 1:
                self.filenames[img] = (u'{:04}{}').format(len(self.urls), ext)
            else:
                self.filenames[img] = clean_title(self.name, n=-len(ext)) + ext
            self.urls.append(img)

        self.single = len(imgs) == 1
        self.referer = self.url
        self.title = u'{} (imgur_{})'.format(self.name, self.id_)


@try_n(4)
def get_info(url):
    url = url.replace('/gallery/', '/a/')
    if '/r/' in url and url.split('/r/')[1].strip('/').count('/') == 0:
        title = re.find(r'/r/([^/]+)', url)
        info = {}
        info['title'] = title
        info['type'] = 'r'
    else:
        try: # legacy
            html = downloader.read_html(url, cookies={'over18':'1'})
            s = re.find('image *: *({.+)', html)
            info_raw = cut_pair(s)
        except Exception as e: # new
            print(e)
            id_ = re.find(r'/a/([0-9a-zA-Z_]+)', url) or re.find(r'/r/[0-9a-zA-Z_]+/([0-9a-zA-Z_]+)', url, err='no id')
            url_api = 'https://api.imgur.com/post/v1/albums/{}?client_id=546c25a59c58ad7&include=media%2Cadconfig%2Caccount'.format(id_)
            info_raw = downloader.read_html(url_api, cookies={'over18':'1'})
        info = json.loads(info_raw)
        info['type'] = 'a'
    return info


def get_imgs(url, info=None, cw=None):
    print('get_imgs', url)
    if info is None:
        info = get_info(url)
    imgs = []

    # Range
    max_pid = get_max_range(cw)

    if info['type'] == 'a':
        if 'album_images' in info: # legacy
            imgs_ = info['album_images']['images']
        elif 'media' in info: # new
            imgs_ = info['media']
        else: # legacy
            imgs_ = [info]
        
        for img in imgs_:
            img_url = img.get('url') # new
            if not img_url: # legacy
                hash = img['hash']
                ext = img['ext']
                img_url = 'https://i.imgur.com/{}{}'.format(hash, ext)
            if img_url in imgs:
                continue
            imgs.append(img_url)
            
    elif info['type'] == 'r':
        urls = set()
        for p in range(100):
            url_api = 'https://imgur.com/r/{}/new/page/{}/hit?scrolled'.format(info['title'], p)
            print(url_api)
            html = downloader.read_html(url_api, referer=url)
            soup = Soup(html)
            
            c = 0
            for post in soup.findAll('div', class_='post'):
                a = post.find('a', class_='image-list-link')
                url_post = urljoin(url, a.attrs['href'])
                if url_post in urls:
                    continue
                urls.add(url_post)
                c += 1

                try: # for r18 images
                    imgs += get_imgs(url_post)
                except Exception as e:
                    print(e)

                s = (u'{} {}  ({})').format(tr_(u'\uc77d\ub294 \uc911...'), info['title'], len(imgs))
                if cw is not None:
                    if cw.alive:
                        cw.setTitle(s)
                    else:
                        return []
                else:
                    print(s)
                
            if c == 0:
                print('same; break')
                break

    return imgs
    
