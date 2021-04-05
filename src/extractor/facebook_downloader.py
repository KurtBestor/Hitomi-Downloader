#coding:utf8
import downloader
from utils import Session, urljoin, Soup, LazyUrl, try_n, Downloader, get_outdir, clean_title
import ree as re
import json
import os
from translator import tr_
from timee import sleep
from downloader import getsize
import errors
PATTERN_CURSOR = '".+?&cursor=([0-9]+)'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36'


class Image(object):
    def __init__(self, url):
        if 'fbid=' in url:
            id = int(re.findall('fbid=([0-9]+)', url)[0])
        elif 'photos/' in url:
            id = int(url.split('photos/')[1].split('/')[1])
        else:
            id = int(url)
        self.id = id
        def f(_):
            img = get_img(url)
            ext = os.path.splitext(img.split('?')[0])[1]
            self.filename = u'{}{}'.format(id, ext)
            return img
        self.url = LazyUrl(url, f, self)

        
@try_n(4)
def get_img(url):
    #print('get_img', url)
    html = read_html(url)
    soup = Soup(html)

    for div in soup.findAll('div'):
        href = div.attrs.get('data-full-size-href')
        if href:
            img = href
            break
    else:
        img = None

    if img is None:

        # 1869
        for code in soup.findAll('code'):
            code = code.string
            hidden = Soup(code)
            soup.append(hidden)
            
        for a in soup.findAll('a'):
            target = a.attrs.get('target')
            if target == '_blank':
                img = a.attrs['href']
                break
        else:
            raise Exception('No img')

    return img


def suitable(url):
    if 'facebook.com' not in url.lower():
        return False
    if '/videos/' in url or 'video.php?' in url:
        return False
    return True


@Downloader.register
class Downloader_facebook(Downloader):
    type = 'facebook'
    URLS = [suitable]
    _soup = None
    MAX_CORE = 8

    @classmethod
    def fix_url(cls, url):
        if 'facebook.com/' not in url:
            url = 'https://facebook.com/{}'.format(url)
        url = url.replace('m.facebook.', 'facebook.')
        if 'www.facebook.com/' not in url:
            url = url.replace('facebook.com/', 'www.facebook.com/', 1)
        if '/profile.php?' not in url:
            url = url.split('?')[0]
        return url.split('#')[0].strip('/')

    @property
    def username(self):
        username = get_username(self.url)
        return username

    @property
    def soup(self):
        if self._soup is None:
            html = read_html(self.url)
            self._soup = Soup(html)
        return self._soup

    @property
    def name(self):
        title = get_title(self.soup)
        id_ = 'facebook_{}'.format(self.username)
        title = u'{} ({})'.format(title, id_)
        return clean_title(title)

    @property
    def album(self):
        if 'album_id=' in self.url:
            album = re.findall('album_id=([0-9]+)', self.url)[0]
        else:
            album = None
        return album

    def read(self):
        self.print_(self.name)
        self.title = tr_(u'읽는 중... {}').format(self.name)

        imgs = get_imgs(self.username, self.name, cw=self.cw)

        for img in imgs:
            if isinstance(img, Image):
                self.urls.append(img.url)
            else:
                self.urls.append(img)

        self.title = self.name


def read_html(url):
    return downloader.read_html(url, user_agent=UA)


def get_title(soup):
    html = str(soup)
    name = re.find(r'"__isProfile":"Page","name":(".*?")', html) or re.find(r'"name":(".*?")', html)
    if not name:
        gc = soup.find('div', id='globalContainer')
        if gc and gc.find('form', id='login_form'):
            raise errors.LoginRequired()
        raise Exception('no name')
    title = json.loads(name)
    return title


def get_imgs(username, title, cw=None):
    urls = [
        'https://m.facebook.com/{}/photos'.format(username),
        'https://m.facebook.com/profile.php?id={}&sk=photos'.format(username), # no custom URL
        ]
    
    for url in urls:
        print('get_imgs url:', url)
        try:
            html = read_html(url)
        except:
            continue
        soup = Soup(html)
        if soup.find('a', id='signup-button'):
            raise errors.LoginRequired()

        photo = soup.find('div', class_='_5v64')
        if photo is not None:
            break
    else:
        raise Exception('No photo div')
    
    cursor = photo.a.attrs['href'].split('/photos/')[1].split('/')[1]
    print('first cursor:', cursor)

    href = re.find(r'(/photos/pandora/\?album_token=.+?)"', html)
    href = urljoin(url, href)
    href = re.sub('&cursor=[0-9]+', '&cursor={}'.format(cursor), href)

    cursors = set([cursor])

    imgs = []

    dups = {}
    dir = os.path.join(get_outdir('facebook'), title)
    try:
        filenames = os.listdir(dir)
    except:
        filenames = []
    for filename in filenames:
        name, ext = os.path.splitext(filename)
        if name.isdigit():
            dups[int(name)] = os.path.join(dir, filename)

    pages = set()

    while True:
        print(href)
        html = read_html(href)
        data_raw = html.replace('for (;;);', '')
        data = json.loads(data_raw)
        actions = data['payload']['actions']
        for action in actions:
            if action['target'] == 'm_more_photos':
                break
        else:
            print('No more photos')
            break
        html = action['html']
        soup = Soup(html)
        photos = soup.findAll('div' ,class_='_5v64')
        for photo in photos:
            for a in photo.findAll('a'):
                page = a.attrs['href']
                page = urljoin(href, page)

                # remove duplicate pages
                if page in pages:
                    continue
                pages.add(page)
                
                img = Image(page)
                id = img.id
                if id in dups and getsize(dups[id]) > 0:
                    print('skip', id)
                    imgs.append(dups[id])
                else:
                    imgs.append(img)

        s = u'{} {} - {}'.format(tr_(u'읽는 중...'), title, len(imgs))
        if cw is not None:
            cw.setTitle(s)
            if not cw.alive:
                return []
        else:
            print(s)

        cursor = re.find(PATTERN_CURSOR, data_raw)
        #print(cursor)
        if cursor is None:
            print('no cursor')
            break
        if cursor in cursors:
            print('same cursor')
            break
        cursors.add(cursor)

        href = re.sub('&cursor=[0-9]+', '&cursor={}'.format(cursor), href)

    return imgs



def get_username(url):
    if '/profile.php?' in url:
        id = re.find(r'/profile\.php[\?&]id=([0-9]+)', url)
        return id
    else:
        url = url.replace('facebook.com/pg/', 'facebook.com/')
        return url.split('?')[0].split('facebook.com/')[1].split('/')[0]

    
