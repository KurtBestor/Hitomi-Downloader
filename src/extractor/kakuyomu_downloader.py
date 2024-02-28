#coding:utf8
import downloader
import utils
from utils import Soup, urljoin, Downloader, LazyUrl, try_n, clean_title, get_print, json, File
import os
from io import BytesIO
from translator import tr_



class Page(File):
    type = 'kakuyomu'
    format = 'title'

    def __init__(self, info):
        info['title_all'] = clean_title('[{:04}] {}'.format(info['p'], info['title']))
        d = {
            'title': info['title_all'],
            }
        info['name'] = utils.format(self.type, d, '.txt')
        super().__init__(info)

    def get(self):
        text = get_text(self)
        f = BytesIO()
        f.write(text.encode('utf8'))
        f.seek(0)
        return {'url': f}



class Downloader_kakuyomu(Downloader):
    type = 'kakuyomu'
    URLS = ['kakuyomu.jp']
    MAX_CORE = 2
    detect_removed = False
    display_name = 'カクヨム'
    ACCEPT_COOKIES = [r'(.*\.)?kakuyomu\.jp']
    atts = ['info_title', 'info_description']

    def read(self):
        self.info = get_info(self.url, cw=self.cw)
        self.artist = self.info['artist']
        title_dir = clean_title('[{}] {}'.format(self.artist, self.info['title']))

        outdir = utils.dir(self.type, title_dir, self.cw)

        self.urls += self.info['pages']

        self.title = title_dir
        self.info_title = self.info['title']
        self.info_description = self.info['description']

    def post_processing(self):
        names = self.cw.names
        filename = clean_title('[merged] [{}] {}'.format(self.artist, self.info_title), n=-4) + '.txt'
        filename = os.path.join(self.dir, filename)
        try:
            with utils.open(filename, 'wb') as f:
                f.write('    {}\n\n    作者：{}\n\n\n'.format(self.info_title, self.artist).encode('utf8'))
                f.write(self.info_description.encode('utf8'))
                for i, file in enumerate(names):
                    self.cw.pbar.setFormat('[%v/%m]  {} [{}/{}]'.format(tr_('병합...'), i, len(names)))
                    with open(file, 'rb') as f_:
                        text = f_.read()
                    f.write(b'\n\n\n\n')
                    f.write(text)
        finally:
            self.cw.pbar.setFormat('[%v/%m]')


@try_n(4, sleep=30)
def get_text(page):
    html = downloader.read_html(page['referer'])
    soup = Soup(html)
    view = soup.find('div', class_='widget-episodeBody')
    story = view.text.strip()
    text = '''────────────────────────────────

  ◆  {}        {}

────────────────────────────────


{}'''.format(page['title_all'], page['date'], story)
    return text


def get_info(url, soup=None, cw=None):
    print_ = get_print(cw)
    if soup is None:
        html = downloader.read_html(url)
        soup = Soup(html)

    info = {}

    rdata = soup.find('script', id='__NEXT_DATA__').string #6620
    data = json.loads(rdata)

    wid = data['query']['workId']
    info['title'] = data['props']['pageProps']['__APOLLO_STATE__'][f'Work:{wid}']['title']
    aid = data['props']['pageProps']['__APOLLO_STATE__'][f'Work:{wid}']['author']['__ref']
    info['artist'] = data['props']['pageProps']['__APOLLO_STATE__'][f'{aid}']['activityName']

    catch = data['props']['pageProps']['__APOLLO_STATE__'][f'Work:{wid}'].get('catchphrase') or ''
    intro = data['props']['pageProps']['__APOLLO_STATE__'][f'Work:{wid}'].get('introduction') or ''
    desc = '  {}{}'.format(catch, ('\n\n\n'+intro) if intro else '')
    info['description'] = desc

    eps = []
    for tc in  data['props']['pageProps']['__APOLLO_STATE__'][f'Work:{wid}']['tableOfContents']:
        _ = data['props']['pageProps']['__APOLLO_STATE__'][tc['__ref']].get('episodes')
        if _:
            eps += _
        else: #6708
            eps += data['props']['pageProps']['__APOLLO_STATE__'][tc['__ref']]['episodeUnions']

    pages = []
    for ep in eps:
        eid = ep['__ref'].split('Episode:')[1]
        href = urljoin(url, f'/works/{wid}/episodes/{eid}')
        subtitle = data['props']['pageProps']['__APOLLO_STATE__'][ep['__ref']]['title']
        date = data['props']['pageProps']['__APOLLO_STATE__'][ep['__ref']]['publishedAt']
        page = Page({'referer': href, 'title': subtitle, 'date': date, 'p': len(pages)+1})
        pages.append(page)

    info['pages'] = pages

    return info
