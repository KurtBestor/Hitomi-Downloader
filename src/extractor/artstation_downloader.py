#coding:utf8
import downloader
from error_printer import print_error
from translator import tr_
from utils import Downloader, Soup, get_print, lazy, Session, try_n, File, clean_title, check_alive, get_ext, get_max_range
import dateutil.parser
import utils


class File_artstation(File):
    type = 'artstation'
    format = '[date] name_ppage'
    c_alter = 0

    def alter(self): #6401
        self.c_alter += 1
        if self.c_alter % 2 == 0:
            url = self['url']
        else:
            url = self['url'].replace('/4k/', '/large/')
        return url



class Downloader_artstation(Downloader):
    type = 'artstation'
    URLS = ['artstation.com']
    display_name = 'ArtStation'
    ACCEPT_COOKIES = [r'(.*\.)?artstation\.(com|co)']
    url_main = None

    @try_n(8)
    def init(self):
        # 3849
        self.session = Session()

        import clf2
        clf2.solve(self.url, self.session, self.cw)

        _ = self._id.replace('artstation_', '', 1)
        self.url_main = f'https://www.artstation.com/{_}'

        if '/artwork/' in self.url or '/projects/' in self.url:
            pass
        else:
            self.url = self.url_main
        self.print_(self.url)

    @classmethod
    def fix_url(cls, url): #6516
        if '.artstation.com' in url:
            sub = url.split('.artstation.com')[0].split('/')[-1]
            if sub != 'www':
                url = f'https://www.artstation.com/{sub}'
        return url

    @lazy
    def _id(self):
        _id = get_id(self.url, self.cw)
        return f'artstation_{_id}'

    @lazy
    @try_n(2)
    def name(self):
        soup = downloader.read_soup(self.url_main, session=self.session)
        name = soup.find('meta', {'property': 'og:title'}).attrs['content']
        return clean_title(f'{name} ({self._id})')

    def read(self):
        self.title = self.name
        id_ = self._id.replace('artstation_', '', 1)
        if '/' in id_:
            id_ = id_.split('/')[0]

        if '/artwork/' in self.url or '/projects/' in self.url:
            id_art = get_id_art(self.url)
            imgs = get_imgs_page(id_art, self.session, cw=self.cw)
        else:
            imgs = get_imgs(id_, self.title, self.session, cw=self.cw)

        for img in imgs:
            self.urls.append(img)

        self.title = self.name


@try_n(2)
def get_imgs(id_, title, session, cw=None):
    print_ = get_print(cw)
    referer = f'https://www.artstation.com/{id_}'
    downloader.read_html(referer, session=session)
    #print(session.cookies.keys())

    url = f'https://www.artstation.com/users/{id_}/quick.json'
    j = downloader.read_json(url, referer, session=session)
    uid = j['id']

    datas = []
    ids = set()
    for p in range(1, 1000):
        check_alive(cw)
        url = f'https://www.artstation.com/users/{id_}/projects.json??user_id={uid}&page={p}' #6516
        j = try_n(4)(downloader.read_json)(url, referer, session=session)

        data = j['data']
        if not data:
            break
        for d in data:
            if d['id'] not in ids:
                ids.add(d['id'])
                datas.append(d)
        if cw:
            cw.setTitle(f'{tr_("페이지 읽는 중...")}  {title} - {len(datas)}')
        else:
            print(len(datas))

    datas = sorted(datas, key=lambda data: int(data['id']), reverse=True)

    imgs = []
    i = 0
    names = set()
    while i < len(datas):
        check_alive(cw)
        data = datas[i]
        date = data['created_at']
        post_url = data['permalink']
        #print('post_url', post_url)
        id_art = get_id_art(post_url)
        imgs += get_imgs_page(id_art, session, date=date, cw=cw, names=names)
        if len(imgs) >= get_max_range(cw):
            break
        if cw:
            cw.setTitle(f'{tr_("이미지 읽는 중...")}  {title} - {i+1} / {len(datas)}  ({len(imgs)})')
        else:
            print(len(imgs))
        i += 1

    return imgs


def get_id_art(post_url):
    return post_url.split('/artwork/')[-1].split('/projects/')[-1].split('/')[0].split('?')[0].split('#')[0]


def get_id(url, cw=None):
    print_ = get_print(cw)

    url = url.split('?')[0].split('#')[0]

    if '/artwork/' in url:
        id_art = get_id_art(url)
        imgs = get_imgs_page(id_art, session=Session(), cw=cw)
        return imgs[0].data['user']['username']

    if '.artstation.' in url and 'www.artstation.' not in url:
        id_ = url.split('.artstation')[0].split('//')[-1]
        type_ = None
    elif 'artstation.com' in url:
        paths = url.split('artstation.com/')[1].split('/')
        id_ = paths[0]
        type_ = paths[1] if len(paths) > 1 else None
    else:
        id_ = url.replace('artstation_', '').replace('／', '/')
        type_ = None

    if type_ not in [None, 'likes']:
        type_ = None

    print_(f'type: {type_}, id: {id_}')

    if type_:
        return f'{id_}/{type_}'
    return id_


def get_imgs_page(id_art, session, date=None, cw=None, names=None):
    print_ = get_print(cw)
    url_json = f'https://www.artstation.com/projects/{id_art}.json'
    post_url = f'https://www.artstation.com/artwork/{id_art}'

    name = post_url.strip('/').split('/')[-1]
    if names is not None:
        while name.lower() in names:
            name += '_'
        names.add(name.lower())

    try:
        data = downloader.read_json(url_json, session=session, referer=post_url)
        imgs_ = data['assets']
    except Exception as e:
        print_(print_error(e))
        return []

    if date is None:
        date = data['created_at']
    date = dateutil.parser.parse(date)

    imgs = []
    for page, img in enumerate(imgs_):
        if not img['has_image']:
            print('no img')
            continue
        url = None
        embed = img.get('player_embedded')
        if embed:
            soup = Soup(embed)
            url_embed = soup.find('iframe').attrs['src']
            print_(f'embed: {url_embed}')
            try:
                soup = downloader.read_soup(url_embed, post_url, session=session)
                v = soup.find('video')
                if v:
                    url = v.find('source').attrs['src']
            except Exception as e:
                print_(print_error(e))
            if not url:
                try:
                    url = soup.find('link', {'rel': 'canonical'}).attrs['href']
                    print_(f'YouTube: {url}')
                    raise Exception('YouTube')
                except Exception as e:
                    print(e)
                    url = None
        if not url:
            url = img['image_url']

        d = {
            'date': date,
            'name': clean_title(name),
            'page': page,
            }
        filename = utils.format('artstation', d, get_ext(url))
        img = File_artstation({'referer':post_url, 'url':url.replace('/large/', '/4k/'), 'name': filename})
        img.data = data

        imgs.append(img)

    return imgs
