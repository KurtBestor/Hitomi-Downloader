#coding: utf-8
import downloader
import ree as re
from utils import Downloader, urljoin, query_url, Soup, get_max_range, get_print, LazyUrl, get_ext, clean_title, Session, check_alive
from translator import tr_
try:
    from urllib import quote # python2
except:
    from urllib.parse import quote # python3
from constants import clean_url


def get_tags(url):
    url = clean_url(url)
    qs = query_url(url)
    if 'page=favorites' in url:
        id = qs.get('id', ['N/A'])[0]
        id = 'fav_{}'.format(id)
    else:
        tags = qs.get('tags', [])
        tags.sort()
        id = ' '.join(tags)
    if not id:
        id = 'N/A'
    return id



class Downloader_gelbooru(Downloader):
    type = 'gelbooru'
    URLS = ['gelbooru.com']
    MAX_CORE = 8
    _name = None
    ACCEPT_COOKIES = [r'(.*\.)?gelbooru\.com']

    @classmethod
    def fix_url(cls, url):
        if 'gelbooru.com' in url.lower():
            url = url.replace('http://', 'https://')
        else:
            url = url.replace(' ', '+')
            while '++' in url:
                url = url.replace('++', '+')
            url = quote(url)
            url = url.replace('%2B', '+')
            url = 'https://gelbooru.com/index.php?page=post&s=list&tags={}'.format(url)
        return url

    @property
    def name(self):
        if self._name is None:
            tags = get_tags(self.url)
            self._name = tags
        return clean_title(self._name)

    def read(self):
        self.title = self.name

        imgs = get_imgs(self.url, self.name, cw=self.cw)

        for img in imgs:
            self.urls.append(img.url)

        self.title = self.name


@LazyUrl.register
class LazyUrl_gelbooru(LazyUrl):
    type = 'gelbooru'
    def dump(self):
        return {
            'id': self.image.id_,
            'url': self.image._url,
            }
    @classmethod
    def load(cls, data):
        img = Image(data['id'], data['url'])
        return img.url


class Image:
    def __init__(self, id_, url):
        self.id_ = id_
        self._url = url
        self.url = LazyUrl_gelbooru(url, self.get, self)

    def get(self, url):
        html = downloader.read_html(url)
        soup = Soup(html)
        for li in soup.findAll('li'):
            if li.text.strip() == 'Original image':
                break
        else:
            raise Exception('no Original image')
        url = li.find('a')['href']
        ext = get_ext(url)
        self.filename = '{}{}'.format(self.id_, ext)
        return url


def setPage(url, page):
    # Always use HTTPS
    url = url.replace('http://', 'https://')

    # Change the page
    if 'pid=' in url:
        url = re.sub('pid=[0-9]*', 'pid={}'.format(page), url)
    else:
        url += '&pid={}'.format(page)

    if page == 0:
        url = url.replace('&pid=0', '')

    return url


def get_imgs(url, title=None, cw=None):
    print_ = get_print(cw)
    url = clean_url(url)
    if 's=view' in url and 'page=favorites' not in url:
        raise NotImplementedError('Not Implemented')

    tags = get_tags(url)
    tags = quote(tags, safe='/')
    tags = tags.replace('%20', '+')
    url = 'https://gelbooru.com/index.php?page=post&s=list&tags={}'.format(tags)

    # 2566
    user_id = Session().cookies.get('user_id', domain='gelbooru.com')
    if user_id:
        cookies = None
    else:
        cookies = {'fringeBenefits': 'yup'}
    print_('user_id: {}'.format(user_id))

    # Range
    max_pid = get_max_range(cw)

    imgs = []
    ids = set()
    count_no_imgs = 0
    for p in range(500): #1017
        check_alive(cw)
        url = setPage(url, len(ids))
        print_(url)
        html = downloader.read_html(url, cookies=cookies)

        soup = Soup(html)
        posts = soup.findAll(class_='thumbnail-preview')
        imgs_new = []
        for post in posts:
            id_ = int(re.find('[0-9]+', post.find('a')['id'], err='no id'))
            if id_ in ids:
                print('duplicate:', id_)
                continue
            ids.add(id_)
            url_img = urljoin(url, post.find('a')['href'])
            img = Image(id_, url_img)
            imgs_new.append(img)
        if imgs_new:
            imgs += imgs_new
            count_no_imgs = 0
        else:
            print('no imgs')
            count_no_imgs += 1
            if count_no_imgs > 1:
                print('break')
                break

        if len(imgs) >= max_pid:
            break

        if cw is not None:
            cw.setTitle('{}  {} - {}'.format(tr_('읽는 중...'), title, len(imgs)))

    return imgs[:max_pid]
