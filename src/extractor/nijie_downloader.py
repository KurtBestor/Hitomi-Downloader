#coding: utf-8
import downloader
from utils import Downloader, urljoin, get_max_range, query_url, Soup, Session, LazyUrl, get_print, clean_title, try_n, get_ext, check_alive
from translator import tr_
from constants import clean_url
import ree as re
from errors import LoginRequired


def get_id(url):
    return re.find('id=([0-9]+)', url)


def get_name(soup):
    return soup.find('p', class_='user_icon').find('a', class_='name').text.strip()


def isLogin(soup):
    if soup.find('ul', id="sub-menu"):
        return True
    return False



class Downloader_nijie(Downloader):
    type = 'nijie'
    URLS = ['nijie.info']
    MAX_CORE = 4
    display_name = 'ニジエ'

    def init(self):
        if 'members.php' not in self.url and 'members_illust.php' not in self.url:
            raise NotImplementedError()
        id = get_id(self.url)
        html = downloader.read_html('https://nijie.info/members.php?id={}'.format(id))
        self.soup = Soup(html)

        if not isLogin(self.soup):
            raise LoginRequired()

    @classmethod
    def fix_url(cls, url):
        if 'nijie.info' not in url.lower():
            url = 'https://nijie.info/members.php?id={}'.format(url)
        return url.replace('http://', 'https://')

    @property
    def name(self):
        name = '{} (nijie_{})'.format(get_name(self.soup), get_id(self.url))
        return clean_title(name)

    def read(self):
        self.title = self.name

        imgs = get_imgs(self.url, self.name, cw=self.cw)

        for img in imgs:
            self.urls.append(img.url)

        self.title = self.name



class Image:
    def __init__(self, id, url, p, lazy=True, img=None):
        self.id = id
        self.p = p
        if lazy:
            self.url = LazyUrl(url, self.get_single, self)
        else:
            self.url = LazyUrl(url, lambda _:img, self)
            ext = get_ext(img)
            self.filename = '{}_p{}{}'.format(id, p, ext)

    def get_single(self, url): # single
        img = get_imgs_post(self.id, url)[0].url()
        ext = get_ext(img)
        self.filename = '{}_p{}{}'.format(self.id, self.p, ext)
        return img


@try_n(8, sleep=10)
def get_imgs_post(id, url):
    #print('get_imgs_post', id, url)
    html = downloader.read_html(url)
    soup = Soup(html)
    view = soup.find('div', id='gallery')
    imgs = []
    for img in view.findAll(class_='mozamoza'):
        url_img = urljoin(url, img['src'])
        url_img = re.sub('__rs_l[0-9]+x[0-9]+/', '', url_img)
        img = Image(id, url, len(imgs), False, url_img)
        imgs.append(img)
    return imgs


def setPage(url, page):
    # Always use HTTPS
    url = url.replace('http://', 'https://')

    # Change the page
    if 'p=' in url:
        url = re.sub('p=[0-9]*', 'p={}'.format(page), url)
    else:
        url += '&p={}'.format(page)

    return url


def get_imgs(url, title=None, cw=None):
    print_ = get_print(cw)
    url = clean_url(url)

    id = get_id(url)
    url = 'https://nijie.info/members_illust.php?id={}'.format(id)

    # Range
    max_pid = get_max_range(cw)

    imgs = []
    url_imgs = set()
    for p in range(1, 1+100):
        url = setPage(url, p)
        print_(url)
        html = downloader.read_html(url)

        soup = Soup(html)
        posts = soup.findAll('div', class_='nijie')
        if not posts:
            print('no posts')
            break
        c = 0
        for post in posts:
            check_alive(cw)
            url_img = urljoin(url, post.a.attrs['href'])
            if url_img in url_imgs:
                print('duplicate:', url_img)
                continue
            url_imgs.add(url_img)
            id = int(re.find('[?&]id=([0-9]+)', url_img))
            multi = post.find('div', class_='thumbnail-icon')
            if multi:
                imgs_ = get_imgs_post(id, url_img)#
            else:
                imgs_ = [Image(id, url_img, 0)]

            imgs += imgs_
            c += 1

            if len(imgs) >= max_pid:
                break

            msg = '{}  {} - {}'.format(tr_('읽는 중...'), title, len(imgs))
            if cw:
                cw.setTitle(msg)
            else:
                print(msg)

        if len(imgs) >= max_pid or c == 0:
            break
    return imgs
