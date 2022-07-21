#coding:utf8
import downloader
from utils import Soup, Downloader, LazyUrl, urljoin, try_n, get_outdir, clean_title, get_max_range
import ree as re
import os
from timee import sleep
from translator import tr_
from io import BytesIO
import json
import clf2
downloader.REPLACE_UA[r'\.luscious\.net'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'


class Image(object):
    def __init__(self, item, referer):
        self.item = item
        self.id = str(item['id'])
        self.referer = referer
        self.url = LazyUrl(referer, self.get, self)

    def get(self, url):
        img = urljoin(url, self.item['url_to_original'])
        ext = os.path.splitext(img.split('?')[0])[1]
        self.filename = u'{}{}'.format(self.id, ext)
        return img


class Video(object):
    def __init__(self, url, title, url_thumb):
        self.url = url
        self.title = title
        ext = os.path.splitext(url.split('?')[0])[1]
        self.filename = u'{}{}'.format(clean_title(title), ext)
        self.url_thumb = url_thumb
        self.thumb = BytesIO()
        downloader.download(self.url_thumb, buffer=self.thumb)



class Downloader_luscious(Downloader):
    type = 'luscious'
    URLS = ['luscious.net']
    MAX_CORE = 4

    @classmethod
    def fix_url(cls, url):
        url = url.replace('members.luscious.', 'www.luscious.')
        return url

    @classmethod
    def key_id(cls, url):
        return '/'.join(url.split('/')[3:])

    def read(self):
        def f(html, browser=None):
            soup = Soup(html)
            if soup.find('input', type='password'):
                browser.show()
                return False
            browser.hide()
            try:
                get_title(soup)
            except:
                return False
            return True
        res = clf2.solve(self.url, f=f, cw=self.cw, show=True)
        self.url = res['url']
        soup = Soup(res['html'])

        title = clean_title(get_title(soup))

        self.title = tr_(u'읽는 중... {}').format(title)

        if '/videos/' in self.url:
            video = get_video(self.url, soup)
            imgs = [video]
            self.setIcon(video.thumb)
        else:
            imgs = get_imgs(self.url, soup, self.cw)

        dir = os.path.join(get_outdir(self.type), title)
        names = {}
        try:
            for name in os.listdir(dir):
                id = os.path.splitext(name)[0]
                names[id] = name
        except:
            pass

        for img in imgs:
            if img.id in names:
                url = os.path.join(dir, names[img.id])
            else:
                url = img.url
            self.urls.append(url)

        self.title = title#


def update(cw, title, imgs):
    s = u'{} {} - {}'.format(tr_(u'읽는 중...'), title, len(imgs))
    if cw is not None:
        cw.setTitle(s)
    else:
        print(s)

def get_imgs(url, soup=None, cw=None):
    if soup is None:
        html = downloader.read_html(url)
        soup = Soup(html)
    title = get_title(soup)

    n = get_max_range(cw)

    imgs = []
    p = 1
    while True:
        imgs_new, has_next_page = get_imgs_p(url, p)
        if not imgs_new:
            break
        imgs += imgs_new
        update(cw, title, imgs)
        p += 1
        if len(imgs) >= n or not has_next_page:
            break
    return imgs[:n]


@try_n(4, sleep=30)
def get_imgs_p(url, p=1):
    id = re.find('/albums/[^/]+?([0-9]+)/', url+'/')
    print(url, id)
    url_api = 'https://api.luscious.net/graphql/nobatch/?operationName=AlbumListOwnPictures&query=+query+AlbumListOwnPictures%28%24input%3A+PictureListInput%21%29+%7B+picture+%7B+list%28input%3A+%24input%29+%7B+info+%7B+...FacetCollectionInfo+%7D+items+%7B+...PictureStandardWithoutAlbum+%7D+%7D+%7D+%7D+fragment+FacetCollectionInfo+on+FacetCollectionInfo+%7B+page+has_next_page+has_previous_page+total_items+total_pages+items_per_page+url_complete+%7D+fragment+PictureStandardWithoutAlbum+on+Picture+%7B+__typename+id+title+created+like_status+number_of_comments+number_of_favorites+status+width+height+resolution+aspect_ratio+url_to_original+url_to_video+is_animated+position+tags+%7B+category+text+url+%7D+permissions+url+thumbnails+%7B+width+height+size+url+%7D+%7D+&variables=%7B%22input%22%3A%7B%22filters%22%3A%5B%7B%22name%22%3A%22album_id%22%2C%22value%22%3A%22{}%22%7D%5D%2C%22display%22%3A%22position%22%2C%22page%22%3A{}%7D%7D'.format(id, p)
    data_raw = downloader.read_html(url_api, referer=url)
    data = json.loads(data_raw)
    has_next_page = data['data']['picture']['list']['info']['has_next_page']
    imgs = []
    for item in data['data']['picture']['list']['items']:
        img = Image(item, url)
        imgs.append(img)

    return imgs, data['data']['picture']['list']['info']['has_next_page']


def get_video(url, soup):
    url_thumb = soup.find('meta', {'property': 'og:image'}).attrs['content']

    title = re.find('videos/([^/]+)', url)
    video = soup.find('video')
    url = video.source.attrs['src']
    video = Video(url, title, url_thumb)
    return video


def get_title(soup):
    return soup.find('h1').text.strip()
