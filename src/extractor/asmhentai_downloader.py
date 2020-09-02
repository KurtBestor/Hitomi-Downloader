#coding: utf8
import downloader
import ree as re
from utils import Soup, urljoin, Downloader, join
import os



def get_id(url):
    try:
        return int(url)
    except:
        if '/gallery/' in url:
            return int(re.find('/gallery/[0-9]+/([0-9]+)', url))
        else:
            return int(re.find('/g/([0-9]+)', url))


@Downloader.register
class Downloader_asmhentai(Downloader):
    type = 'asmhentai'
    URLS = ['asmhentai.com']
    MAX_CORE = 8
    
    def init(self):
        pass

    @classmethod
    def fix_url(cls, url):
        url = url.replace('asmhentai_', '')
        id_ = get_id(url)
        return 'https://asmhentai.com/g/{}/'.format(id_)

    def read(self):
        info, imgs = get_imgs(self.url)

        # 1225
        artist = join(info['artists'])
        self.artist = artist
        group = join(info['groups']) if info['groups'] else u'N／A'
        lang = info['language'][0] if info['language'] else u'N／A'
        series = info['parodies'][0] if info['parodies'] else u'N／A'
        title = self.format_title(info['category'][0], info['id'], info['title'], artist, group, series, lang)

        self.urls += imgs

        self.title = title



def get_imgs(url):
    html = downloader.read_html(url)
    soup = Soup(html)

    info = get_info(url, soup)

    view = soup.find('div', class_='gallery')

    imgs = []
    for img in view.findAll('div', class_='preview_thumb'):
        img = img.find('img').attrs.get('data-src') or img.find('img').attrs.get('src')
        img = urljoin(url, img).replace('t.jpg', '.jpg')
        imgs.append(img)

    return info, imgs


def get_info(url, soup=None):
    if soup is None:
        html = downloader.read_html(url)
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
    
    return info
        
