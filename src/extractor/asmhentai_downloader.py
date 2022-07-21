#coding: utf8
import downloader
import ree as re
from utils import Soup, urljoin, Downloader, join, LazyUrl, Session, get_print
import os
from timee import sleep
from translator import tr_



def get_id(url):
    try:
        return int(url)
    except:
        if '/gallery/' in url:
            return int(re.find('/gallery/[0-9]+/([0-9]+)', url))
        else:
            return int(re.find('/g/([0-9]+)', url))



class Downloader_asmhentai(Downloader):
    type = 'asmhentai'
    URLS = ['asmhentai.com']
    MAX_CORE = 8
    display_name = 'AsmHentai'

    @classmethod
    def fix_url(cls, url):
        id_ = get_id(url)
        return 'https://asmhentai.com/g/{}/'.format(id_)

    def read(self):
        self.session = Session()
        info = get_info(self.url, self.session, self.cw)

        # 1225
        artist = join(info['artists'])
        self.artist = artist
        group = join(info['groups']) if info['groups'] else u'N／A'
        lang = info['language'][0] if info['language'] else u'N／A'
        series = info['parodies'][0] if info['parodies'] else u'N／A'
        title = self.format_title(info['category'][0], info['id'], info['title'], artist, group, series, lang)

        self.urls += [img.url for img in info['imgs']]

        self.title = title


class Image:
    def __init__(self, url, referer):
        self.url = LazyUrl(referer, lambda _:url, self)
        self.filename = os.path.basename(url)


def get_info(url, session, cw):
    print_ = get_print(cw)
    html = downloader.read_html(url, session=session)
    soup = Soup(html)

    info = {}

    info['id'] = get_id(url)

    title = soup.find('h1').text.strip()
    info['title'] = title

    for tag in soup.findAll('span', class_='tag'):
        href = tag.parent.attrs['href']
        href = urljoin(url, href).strip('/')

        key = href.split('/')[3]
        value = href.split('/')[-1]

        if key == 'language' and value == 'translated':
            continue

        if key in info:
            info[key].append(value)
        else:
            info[key] = [value]

    for key in ['artists', 'groups', 'parodies', 'tags', 'characters']:
        if key not in info:
            info[key] = []

    info['imgs'] = []
    def read_imgs(soup):
        c = 0
        for img in soup.findAll('div', class_='preview_thumb'):
            img = img.find('img').attrs.get('data-src') or img.find('img').attrs.get('src')
            img = urljoin(url, img).replace('t.jpg', '.jpg')
            img = Image(img, url)
            info['imgs'].append(img)
            c += 1
        if not c:
            raise Exception('no imgs')

    read_imgs(soup)

    csrf = soup.find('meta', {'name':'csrf-token'})['content']
    print_(f'csrf: {csrf}')
    t_pages = int(soup.find('input', type='hidden', id='t_pages')['value'])
    print_(f't_pages: {t_pages}')

    while len(info['imgs']) < t_pages: #4971
        print_('imgs: {}'.format(len(info['imgs'])))
        sleep(1, cw)
        cw.setTitle('{} {} - {} / {}'.format(tr_('읽는 중...'), info['title'], len(info['imgs']), t_pages))
        data = {
        '_token': csrf,
        'id': str(info['id']),
        'dir': soup.find('input', type='hidden', id='dir')['value'],
        'v_pages': len(info['imgs']),
        't_pages': str(t_pages),
        'type': '1',
        }
        r = session.post('https://asmhentai.com/load_thumbs', data=data)
        soup_more = Soup(r.text)
        read_imgs(soup_more)

    return info
