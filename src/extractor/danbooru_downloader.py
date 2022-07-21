#coding: utf-8
import downloader
import ree as re
from utils import Downloader, get_max_range, clean_title, get_print, try_n, urljoin, check_alive, LazyUrl, get_ext
from translator import tr_
from urllib.parse import quote
from urllib.parse import urlparse, parse_qs
from ratelimit import limits, sleep_and_retry



class Downloader_danbooru(Downloader):
    type='danbooru'
    URLS = ['danbooru.donmai.us']
    MAX_CORE = 8
    _name = None

    @classmethod
    def fix_url(cls, url):
        if 'donmai.us' in url:
            url = url.replace('http://', 'https://')
        else:
            url = url.replace(' ', '+')
            while '++' in url:
                url = url.replace('++', '+')
            url = 'https://danbooru.donmai.us/?tags={}'.format(quote(url))
        return url.strip('+')

    @property
    def name(self):
        if self._name is None:
            parsed_url = urlparse(self.url)
            qs = parse_qs(parsed_url.query)
            if 'donmai.us/favorites' in self.url:
                id = qs.get('user_id', [''])[0]
                print('len(id) =', len(id), '"{}"'.format(id))
                if not id:
                    raise AssertionError('[Fav] User id is not specified')
                id = 'fav_{}'.format(id)
            elif 'donmai.us/explore/posts/popular' in self.url: #4160
                soup = read_soup(self.url, self.cw)
                id = soup.find('h1').text
            else:
                tags = qs.get('tags', [])
                tags.sort()
                id = ' '.join(tags)
            if not id:
                id = 'N/A'
            self._name = id
        return clean_title(self._name)

    def read(self):
        self.title = self.name

        imgs = get_imgs(self.url, self.name, cw=self.cw)

        for img in imgs:
            self.urls.append(img.url)

        self.title = self.name


class Image(object):
    def __init__(self, id, url, cw):
        self._cw = cw
        self.id = id
        self.url = LazyUrl(url, self.get, self)

    def get(self, url):
        soup = read_soup(url, self._cw)
        ori = soup.find('li', id='post-option-view-original')
        if ori:
            img = ori.find('a')['href']
        else:
            img = soup.find('li', id='post-info-size').find('a')['href']

        if get_ext(img) == '.zip': #4635
            img = soup.find('section', id='content').find('video')['src']

        img = urljoin(url, img)
        ext = get_ext(img)

        self.filename = '{}{}'.format(self.id, ext)
        return img



@sleep_and_retry
@limits(2, 1)
def wait(cw):
    check_alive(cw)


def setPage(url, page):
    # Always use HTTPS
    url = url.replace('http://', 'https://')

    # Main page
    if re.findall(r'https://[\w]*[.]?donmai.us/?$', url):
        url = 'https://{}donmai.us/posts?page=1'.format('danbooru.' if 'danbooru.' in url else '')

    # Change the page
    if 'page=' in url:
        url = re.sub('page=[0-9]*', 'page={}'.format(page), url)
    else:
        url += '&page={}'.format(page)

    return url


@try_n(4) #4103
def read_soup(url, cw):
    check_alive(cw)
    wait(cw)
    return downloader.read_soup(url)


def get_imgs(url, title=None, range_=None, cw=None):
    if 'donmai.us/artists' in url:
        raise NotImplementedError('Not Implemented')
    if 'donmai.us/posts/' in url:
        raise NotImplementedError('Not Implemented')

    print_ = get_print(cw)

    # Range
    max_pid = get_max_range(cw)

    if range_ is None:
        range_ = range(1, 1001)
    print(range_)
    imgs = []
    i = 0
    empty_count = 0
    empty_count_global = 0
    url_imgs = set()
    while i < len(range_):
        check_alive(cw)
        p = range_[i]
        url = setPage(url, p)
        print_(url)
        soup = read_soup(url, cw)
        articles = soup.findAll('article')
        if articles:
            empty_count_global = 0
        else:
            empty_count += 1
            if empty_count < 4:
                s = 'empty page; retry... {}'.format(p)
                print_(s)
                continue
            else:
                empty_count = 0
                empty_count_global += 1

        if empty_count_global >= 6:
            break

        for article in articles:
            id = article.attrs['data-id']

            #url_img = article.attrs['data-file-url'].strip()
            url_img = urljoin(url, article.find('a', class_='post-preview-link')['href']) #4160

            #print(url_img)
            if url_img not in url_imgs:
                url_imgs.add(url_img)
                img = Image(id, url_img, cw)
                imgs.append(img)

        if len(imgs) >= max_pid:
            break

        if cw is not None:
            cw.setTitle('{}  {} - {}'.format(tr_('읽는 중...'), title, len(imgs)))
        i += 1

    return imgs[:max_pid]
