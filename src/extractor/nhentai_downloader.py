#coding:utf8
import downloader
import ree as re
from utils import urljoin, File, Downloader, try_n, join, get_ext, json
import utils
import clf2


def get_id(url):
    try:
        return int(url)
    except:
        return int(re.find('/g/([0-9]+)', url))


class File_nhentai(File):
    type = 'nhentai'
    format = 'page:04;'


class Downloader_nhentai(Downloader):
    type = 'nhentai'
    URLS = ['nhentai.net']
    MAX_CORE = 16
    display_name = 'nhentai'
    ACCEPT_COOKIES = [r'(.*\.)?nhentai\.net']

    def init(self):
        self.session = clf2.solve(self.url, cw=self.cw)['session'] #4541

    @classmethod
    def fix_url(cls, url):
        return f'https://nhentai.net/g/{get_id(url)}/'

    def read(self):
        info, imgs = get_imgs(get_id(self.url), self.session)

        # 1225
        artist = join(info.artists)
        self.artist = artist if info.artists else None
        group = join(info.groups)
        lang = info.lang or 'N／A'
        series = info.seriess[0] if info.seriess else 'N／A'
        title = self.format_title(info.type, info.id, info.title, artist, group, series, lang)

        self.urls += imgs

        self.title = title


class Info:
    def __init__(self, host, id, id_media, title, p, artists, groups, seriess, lang, type, formats):
        self.host = host
        self.id = id
        self.id_media = id_media
        self.title = title
        self.p = p
        self.artists = artists
        self.groups = groups
        self.seriess = seriess
        self.lang = lang
        self.type = type
        self.formats = formats


@try_n(4)
def get_info(id, session):
    url = f'https://nhentai.net/g/{id}/1/'
    referer = f'https://nhentai.net/g/{id}/'
    html = downloader.read_html(url, referer, session=session)

    data = html.split('JSON.parse(')[1].split(');')[0]
    gal = json.loads(json.loads(data))
    host = 'https://i.nhentai.net'#re.find('''media_url: *['"]([^'"]+)''', html, err='no host')

    id = int(gal['id'])
    id_media = int(gal['media_id'])
    title = gal['title']['english']
    p = len(gal['images']['pages'])
    artists = []
    groups = []
    seriess = []
    for tag in gal['tags']:
        type = tag['type']
        if type == 'artist':
            artists.append(tag['name'])
        elif type == 'group':
            groups.append(tag['name'])
        elif type == 'parody' and tag['name'] != 'original':
            seriess.append(tag['name'])
        elif type == 'language':
            lang = tag['name']
        elif type == 'category':
            type_ = tag['name']
    formats = []
    for img in gal['images']['pages']:
        type = img['t']
        format = {'j':'jpg', 'p':'png', 'g':'gif'}[type]
        formats.append(format)
    info = Info(host, id, id_media, title, p, artists, groups, seriess, lang, type_, formats)
    return info


def get_imgs(id, session):
    info = get_info(id, session)

    imgs = []
    for p in range(1, info.p+1):
        name = f'/galleries/{info.id_media}/{p}.{info.formats[p-1]}'
        url_page = f'https://nhentai.net/g/{id}/{p}/'
        url_img = urljoin(info.host, name)
        ext = get_ext(url_img)
        d = {
            'page': p,
            }
        img = File_nhentai({'url': url_img, 'referer': url_page, 'name': utils.format('nhentai', d, ext)})
        imgs.append(img)

    return info, imgs
