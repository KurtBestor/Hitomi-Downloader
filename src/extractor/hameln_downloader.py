#coding: utf8
import downloader
import os
import utils
from utils import Soup, urljoin, get_text, LazyUrl, try_n, Downloader, lazy, clean_title
import ree as re
from io import BytesIO
from translator import tr_



class Downloader_hameln(Downloader):
    type = 'hameln'
    URLS = ['syosetu.org']
    MAX_CORE = 2
    detect_removed = False
    ACCEPT_COOKIES = [r'(.*\.)?syosetu\.org']

    def init(self):
        id_ = re.find('/novel/([^/]+)', self.url)
        if id_ is not None:
            self.url = 'https://syosetu.org/novel/{}/'.format(id_)

    @lazy
    def soup(self):
        html = read_html(self.url)
        soup = Soup(html)
        return soup

    @lazy
    def info(self):
        return get_info(self.url, self.soup)

    def read(self):
        for page in get_pages(self.url, self.soup):
            text = Text(page, len(self.urls)+1)
            self.urls.append(text.url)

        self.artist = self.info['artist']
        self.title = clean_title('[{}] {}'.format(self.artist, self.info['title']), n=-len('[merged] .txt'))

    def post_processing(self):
        names = self.cw.names
        filename = os.path.join(self.dir, '[merged] {}.txt'.format(self.title))
        try:
            with utils.open(filename, 'wb') as f:
                f.write('    {}\n\n    作者：{}\n\n\n'.format(self.info['title'], self.artist).encode('utf8'))
                if self.info['novel_ex']:
                    f.write(self.info['novel_ex'].encode('utf8'))
                for i, file in enumerate(names):
                    self.cw.pbar.setFormat('[%v/%m]  {} [{}/{}]'.format(tr_('병합...'), i, len(names)))
                    with open(file, 'rb') as f_:
                        text = f_.read()
                    f.write(b'\n\n\n\n')
                    f.write(text)
        finally:
            self.cw.pbar.setFormat('[%v/%m]')


class Text:
    def __init__(self, page, p):
        self.page = page
        self.url = LazyUrl(page.url, self.get, self)
        self.filename = clean_title('[{:04}] {}'.format(p, page.title), n=-4) + '.txt'

    def get(self, url):
        text = read_page(self.page)
        f = BytesIO()
        f.write(text.encode('utf8'))
        f.seek(0)
        return f


class Page:
    def __init__(self, title, url):
        self.title = clean_title(title)
        self.url = url



def read_html(url):
    return downloader.read_html(url, cookies={'over18': 'off'}, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/72.0.3626.119 Safari/537.36'})


def get_sss(soup):
    sss = [ss for ss in soup.findAll('div', class_='ss') if ss.attrs.get('id')!='fmenu']
    return sss


def get_pages(url, soup=None):
    if soup is None:
        html = read_html(url)
        soup = Soup(html)

    sss = get_sss(soup)
    list = sss[-1]

    pages = []
    for tr in list.findAll('tr'):
        a = tr.find('a')
        if a is None:
            continue
        text =a.text.strip()
        href = urljoin(url, a.attrs['href'])
        page = Page(text, href)
        pages.append(page)

    return pages


@try_n(22, sleep=30)
def read_page(page):
    html = read_html(page.url)
    soup = Soup(html)

    text_top = get_text(soup.find('div', id='maegaki'))
    print(text_top.count('\n'))
    text_mid = get_text(soup.find('div', id='honbun'))
    text_bot = get_text(soup.find('div', id='atogaki'))

    texts = [text for text in (text_top, text_mid, text_bot) if text]

    story = '''

────────────────────────────────

'''.join(texts)

    text = '''────────────────────────────────

  ◆  {}

────────────────────────────────


{}'''.format(page.title, story)

    return text


def get_info(url, soup=None):
    if soup is None:
        html = read_html(url)
        soup = Soup(html)

    info = {}
    info['artist'] = soup.find('span', {'itemprop':'author'}).text.strip()
    info['title'] = soup.find('span', {'itemprop':'name'}).text.strip()
    sss = get_sss(soup)
    info['novel_ex'] = get_text(sss[-2])
    return info
