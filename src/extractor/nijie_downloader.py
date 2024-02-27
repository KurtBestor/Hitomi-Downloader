#coding: utf-8
import downloader
from utils import Downloader, Session, urljoin, get_max_range, get_print, clean_title, try_n, get_ext, check_alive, File, limits, clean_url
from translator import tr_
import ree as re
from errors import LoginRequired
import utils


def get_id(url):
    return re.find('id=([0-9]+)', url)


def isLogin(soup):
    if soup.find('ul', id="sub-menu"):
        return True
    return False



class Downloader_nijie(Downloader):
    type = 'nijie'
    URLS = ['nijie.info']
    MAX_CORE = 4
    display_name = 'ニジエ'
    ACCEPT_COOKIES = [r'(.*\.)?nijie\.info']

    def init(self):
        if 'members.php' not in self.url and 'members_illust.php' not in self.url:
            raise NotImplementedError()
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        if 'nijie.info' not in url.lower():
            url = f'https://nijie.info/members.php?id={url}'
        return url.replace('http://', 'https://')

    @property
    def name(self):
        name = self.soup.find('p', class_='user_icon').find('a', class_='name').text.strip()
        name = f'{name} (nijie_{get_id(self.url)})'
        return clean_title(name)

    def read(self):
        id = get_id(self.url)
        self.soup = read_soup(f'https://nijie.info/members.php?id={id}', session=self.session)

        if not isLogin(self.soup):
            raise LoginRequired(method='browser', url='https://nijie.info/login.php')

        self.title = self.name

        self.urls += get_imgs(self.url, self.name, self.session, self.cw)

        self.title = self.name



class Image(File):
    type = 'nijie'

    def get(self):
        url = self['referer']
        if '://' not in url:
            return {'url': url}
        id = int(re.find('[?&]id=([0-9]+)', url))
        url = url.replace('view.php', 'view_popup.php') #6726
        soup = read_soup(url, self['rereferer'], session=self.session)
        view = soup.find('div', id='img_window')
        imgs = []
        p = 0
        for img in view.findAll('img'):
            url_img = urljoin(url, img['src'])
            url_img = re.sub('__rs_l[0-9]+x[0-9]+/', '', url_img)
            if '/filter/' in url_img:
                continue
            ext = get_ext(url_img)
            name = f'{id}_p{p}{ext}'
            imgs.append({'url': url_img, 'name': name})
            p += 1
        return imgs


@try_n(12, sleep=lambda try_: 10+try_*10)
@limits(5)
def read_soup(*args, **kwargs):
    return downloader.read_soup(*args, **kwargs)


def setPage(url, page):
    if 'p=' in url:
        url = re.sub('p=[0-9]*', f'p={page}', url)
    else:
        url += f'&p={page}'

    return url


def get_imgs(url, title=None, session=None, cw=None):
    print_ = get_print(cw)
    url = clean_url(url)

    id = get_id(url)
    url = f'https://nijie.info/members_illust.php?id={id}'

    olds = utils.process_olds(Image, title, r'([0-9]+)_p', cw)
    ids = olds['ids']
    imgs_old = olds['imgs']

    # Range
    max_pid = get_max_range(cw)

    imgs = []
    for p in range(1, 101):
        url = setPage(url, p)
        print_(url)
        soup = read_soup(url, session=session)

        posts = soup.findAll('div', class_='nijie')
        if not posts:
            print_('no posts')
            break

        c = 0
        for post in posts:
            check_alive(cw)
            url_img = urljoin(url, post.a.attrs['href'])
            id_ = int(re.find(r'[&\?]id=([0-9]+)', url_img, err='no id'))
            if id_ in ids:
                continue
            ids.add(id_)
            img = Image({'referer': url_img, 'rereferer': url})

            imgs.append(img)
            c += 1
        print_(f'c: {c}')

        msg = f'{tr_("읽는 중...")}  {title} - {len(imgs)}'
        if cw:
            cw.setTitle(msg)
        else:
            print(msg)

        if len(imgs) >= max_pid or c == 0:
            break
    return imgs + imgs_old
