#coding:utf8
import downloader
from utils import Soup, urljoin, Session, LazyUrl, Downloader, try_n, clean_title, check_alive
import ree as re
import os
from translator import tr_
URL_ENTER = 'https://www.hentai-foundry.com/site/index?enterAgree=1&size=1550'
URL_FILTER = 'https://www.hentai-foundry.com/site/filters'


class Image:
    def __init__(self, url, session):
        @try_n(4)
        def f(_):
            html = downloader.read_html(url, session=session)
            soup = Soup(html)

            box = soup.find('section', id='picBox')
            img = box.find('img')
            if img is None:
                raise Exception('No img')

            onclick = img.attrs.get('onclick', '')
            if onclick and '.src' in onclick:
                print('onclick', onclick)
                img = re.find('''.src *= *['"](.+?)['"]''', onclick)
            else:
                img = img.attrs['src']
            img = urljoin(url, img)

            filename = clean_title(os.path.basename(img.split('?')[0]))
            name, ext = os.path.splitext(filename)

            # https://www.hentai-foundry.com/pictures/user/DrGraevling/74069/Eversong-Interrogation-pg.-13
            if ext.lower() not in ['.bmp', '.png', '.gif', '.jpg', '.jpeg', '.webp', '.webm', '.avi', '.mp4', '.mkv', '.wmv']:
                filename = '{}.jpg'.format(name)

            self.filename = filename
            return img
        self.url = LazyUrl(url, f, self)


def get_username(url):
    if 'user/' in url:
        username = url.split('user/')[1].split('?')[0].split('/')[0]
    return username



class Downloader_hf(Downloader):
    type = 'hf'
    URLS = ['hentai-foundry.com']
    MAX_CORE = 16
    display_name = 'Hentai Foundry'
    ACCEPT_COOKIES = [r'(.*\.)?hentai-foundry\.com']

    def init(self):
        self.session = enter()

    @classmethod
    def fix_url(cls, url):
        username = get_username(url)
        return 'https://www.hentai-foundry.com/user/{}'.format(username)

    def read(self):
        username = get_username(self.url)
        self.title = username

        imgs = get_imgs(username, self.title, self.session, cw=self.cw)

        for img in imgs:
            self.urls.append(img.url)

        self.title = username


@try_n(2)
def enter():
    print('enter')
    session = Session()

    r = session.get(URL_ENTER)

    # 862
    html = r.text
    soup = Soup(html)
    box = soup.find('aside', id='FilterBox')
    data = {}
    for select in box.findAll('select'):
        name = select.attrs['name']
        value = select.findAll('option')[-1].attrs['value']
        print(name, value)
        data[name] = value
    for input in box.findAll('input'):
        name = input.attrs['name']
        value = input.attrs['value']
        if name.startswith('rating_') or 'CSRF_TOKEN' in name:
            print(name, value)
            data[name] = value
    data.update({
        'filter_media': 'A',
        'filter_order': 'date_new',
        'filter_type': '0',
        })
    r = session.post(URL_FILTER, data=data, headers={'Referer': r.url})
    print(r)

    return session


def get_imgs(username, title, session, cw=None):
    url = 'https://www.hentai-foundry.com/pictures/user/{}'.format(username)

    #downloader.read_html(url_enter, session=session)

    hrefs = []
    for p in range(100):
        check_alive(cw)
        print(url)
        html = downloader.read_html(url, session=session)
        soup = Soup(html)

        if soup.find('div', id='entryButtonContainer'):
            session = enter()
            continue

        tab = soup.find('a', class_='active')
        n = re.find(r'\(([0-9]+)', tab.text)

        view = soup.find('div', class_='galleryViewTable')
        for a in view.findAll('a', class_='thumbLink'):
            href = urljoin(url, a.attrs['href'])
            if href in hrefs:
                print('dup')
                continue
            hrefs.append(href)

        next = soup.find(lambda tag: tag.name == 'li' and tag.get('class') == ['next'])
        if next is None:
            break
        url = urljoin(url, next.a.attrs['href'])

        s = '{}  {}  ({} / {})'.format(tr_('읽는 중...'), title, len(hrefs), n)
        if cw:
            cw.setTitle(s)
        else:
            print(s)

    imgs = []
    for href in hrefs:
        img = Image(href, session)
        imgs.append(img)

    return imgs
