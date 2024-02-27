#coding: utf8
import downloader
import ree as re
from utils import Soup, urljoin, Downloader, join, Session, File, clean_title, limits
import os
import utils



def get_id(url):
    try:
        return int(url)
    except:
        return int(re.find('/(g|gallery)/([0-9]+)', url)[1])


class File_asmhentai(File):
    type = 'asmhentai'
    format = 'name'

    @limits(.25)
    def get(self):
        soup = downloader.read_soup(self['referer'], self['rereferer'], session=self.session)
        img = soup.find('img', id='fimg')
        url = img['data-src']
        name, ext = os.path.splitext(os.path.basename(url).split('?')[0])
        d = {
            'name': clean_title(name),
            }
        return {'url': url, 'name': utils.format('asmhentai', d, ext)}



class Downloader_asmhentai(Downloader):
    type = 'asmhentai'
    URLS = ['asmhentai.com']
    MAX_CORE = 8
    display_name = 'AsmHentai'
    ACCEPT_COOKIES = [r'(.*\.)?asmhentai\.com']

    def init(self):
        self.session = Session()

    @classmethod
    def fix_url(cls, url):
        id_ = get_id(url)
        return f'https://asmhentai.com/g/{id_}/'

    def read(self):
        info = get_info(self.url, self.session, self.cw)
        self.print_(info)

        # 1225
        artist = join(info['artist'])
        self.artist = artist
        group = join(info['group']) if info['group'] else 'N／A'
        lang = info['language'][0] if info['language'] else 'N／A'
        series = info['parody'][0] if info['parody'] else 'N／A'
        title = self.format_title(info['category'][0], info['id'], info['title'], artist, group, series, lang)

        for i in range(info['n']):
            url = f'https://asmhentai.com/gallery/{info["id"]}/{i+1}/'
            file = File_asmhentai({'referer':url, 'rereferer': self.url})
            self.urls.append(file)

        self.title = title


def get_info(url, session, cw):
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

    for key in ['artist', 'group', 'parody', 'tag', 'character']:
        if key not in info:
            info[key] = []

    info['n'] = int(soup.find('input', id='t_pages')['value'])

    return info
