#coding:utf8
import downloader
import utils
from utils import Soup, urljoin, Downloader, LazyUrl, get_outdir, try_n, clean_title, get_print
import os
from timee import sleep
from io import BytesIO
from translator import tr_



class Page(object):
    def __init__(self, url, title, date, p):
        self.url = url
        self.title = clean_title(u'[{:04}] {}'.format(p, title), n=-4)
        self.date = date
        self.filename = u'{}.txt'.format(self.title)
        self.file = LazyUrl(self.url, self.get_file, self)

    def get_file(self, url):
        text = get_text(self)
        f = BytesIO()
        f.write(text.encode('utf8'))
        f.seek(0)
        #f.mode = 'w'
        return f


@Downloader.register
class Downloader_kakuyomu(Downloader):
    type = 'kakuyomu'
    URLS = ['kakuyomu.jp']
    MAX_CORE = 2
    detect_removed = False
    display_name = 'カクヨム'

    def init(self):
        self.info = get_info(self.url, cw=self.cw)
    
    def read(self):
        outdir = get_outdir('kakuyomu')

        self.artist = self.info['artist']
        title_dir = clean_title(u'[{}] {}'.format(self.artist, self.info['title']))
        
        for page in self.info['pages']:
            file = os.path.join(outdir, title_dir, page.filename)
            if os.path.isfile(file):
                self.urls.append(file)
            else:
                self.urls.append(page.file)

        self.title = title_dir

    def post_processing(self):
        names = self.cw.names
        filename = clean_title(u'[merged] [{}] {}'.format(self.artist, self.info['title']), n=-4) + '.txt'
        filename = os.path.join(self.dir, filename)
        try:
            with utils.open(filename, 'wb') as f:
                f.write(u'    {}\n\n    \u4f5c\u8005\uff1a{}\n\n\n'.format(self.info['title'], self.artist).encode('utf8'))
                f.write(self.info['description'].encode('utf8'))
                for i, file in enumerate(names):
                    self.cw.pbar.setFormat('[%v/%m]  {} [{}/{}]'.format(tr_(u'\ubcd1\ud569...'), i, len(names)))
                    with open(file, 'rb') as f_:
                        text = f_.read()
                    f.write(b'\n\n\n\n')
                    f.write(text)
        finally:
            self.cw.pbar.setFormat('[%v/%m]')


@try_n(4, sleep=30)
def get_text(page):
    html = downloader.read_html(page.url)
    soup = Soup(html)
    view = soup.find('div', class_='widget-episodeBody')
    story = view.text.strip()
    text =u'''────────────────────────────────

  ◆  {}        {}

────────────────────────────────


{}'''.format(page.title, page.date, story)
    return text
        

def get_info(url, soup=None, cw=None):
    print_ = get_print(cw)
    if soup is None:
        html = downloader.read_html(url)
        soup = Soup(html)

    info = {}

    info['title'] = soup.find('h1', id='workTitle').text.strip()
    info['artist'] = soup.find('span', id='workAuthor-activityName').text.strip()

    desc = soup.find('section', id='description')
    button = desc.find('span', class_='ui-truncateTextButton-expandButton')
    if button:
        print('decompose button')
        button.decompose()
    catch = desc.find('span', id='catchphrase-body')
    if catch is None: #4445
        print_('no catch')
        catch = ''
    else:
        catch = catch.text.strip()
    intro = desc.find('p', id='introduction')
    if intro is None: #4262
        print_('no intro')
        intro = ''
    else:
        intro = intro.text.strip()
    desc = u'  {}{}'.format(catch, ('\n\n\n'+intro) if intro else '')
    info['description'] = desc
    
    pages = []
    for a in soup.findAll('a', class_='widget-toc-episode-episodeTitle'):
        href = urljoin(url, a.attrs['href'])
        subtitle = a.find('span', class_='widget-toc-episode-titleLabel').text.strip()
        date = a.find('time', class_='widget-toc-episode-datePublished').text.strip()
        page = Page(href, subtitle, date, len(pages)+1)
        pages.append(page)

    info['pages'] = pages

    return info
    
