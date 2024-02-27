#coding: utf-8
import downloader
import ree as re
from utils import Downloader, urljoin, query_url, get_max_range, get_print, get_ext, clean_title, Session, check_alive, File, clean_url
from translator import tr_
from urllib.parse import quote
import utils


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

    def init(self):
        self.session = Session()

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

        self.urls += get_imgs(self.url, self.session, self.name, cw=self.cw)

        self.title = self.name


class File_gelbooru(File):
    type = 'gelbooru'
    format = 'id'

    def get(self):
        soup = downloader.read_soup(self['referer'], session=self.session)
        for li in soup.findAll('li'):
            if li.text.strip() == 'Original image':
                break
        else:
            raise Exception('no Original image')
        url = li.find('a')['href']
        d = {
            'id': self['id'],
            }
        return {'url': url, 'name': utils.format('gelbooru', d, get_ext(url))}

    def alter(self):
        return self.get()['url']


def setPage(url, page):
    if 'pid=' in url:
        url = re.sub('pid=[0-9]*', f'pid={page}', url)
    else:
        url += f'&pid={page}'

    if page == 0:
        url = url.replace('&pid=0', '')

    return url


def get_imgs(url, session, title=None, cw=None):
    print_ = get_print(cw)
    url = clean_url(url)
    if 's=view' in url and 'page=favorites' not in url:
        raise NotImplementedError('Not Implemented')

    tags = get_tags(url)
    tags = quote(tags, safe='/')
    tags = tags.replace('%20', '+')
    url = f'https://gelbooru.com/index.php?page=post&s=list&tags={tags}'

    # 2566
    user_id = session.cookies.get('user_id', domain='gelbooru.com')
    if not user_id:
        cookies = {'fringeBenefits': 'yup'}
        session.cookies.update(cookies)
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
        soup = downloader.read_soup(url, session=session)
        posts = soup.findAll(class_='thumbnail-preview')
        imgs_new = []
        for post in posts:
            id_ = int(re.find('[0-9]+', post.find('a')['id'], err='no id'))
            if id_ in ids:
                print('duplicate:', id_)
                continue
            ids.add(id_)
            url_img = urljoin(url, post.find('a')['href'])
            img = File_gelbooru({'id': id_, 'referer': url_img, 'name_hint': f'{id_}{{ext}}'})
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
