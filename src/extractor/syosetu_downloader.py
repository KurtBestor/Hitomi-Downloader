#coding:utf8
import downloader
import utils
from utils import urljoin, try_n, Downloader, clean_title, Session, File, check_alive, get_max_range
import ree as re
from io import BytesIO
import os
from translator import tr_
from timee import sleep


class Text(File):
    type = 'syosetu'
    format = 'title'

    def __init__(self, info):
        title = info['subtitle']
        if not info['single']:
            p = int(re.findall('/([0-9]+)', info['referer'])[-1])
            title = clean_title(f'[{p:04}] {title}')
        info['title_all'] = title
        d = {
            'title': info['title_all'],
            }
        info['name'] = utils.format(self.type, d, '.txt')
        super().__init__(info)

    def get(self):
        text = get_text(self['referer'], self['title_all'], self['update'], self.session)
        f = BytesIO()
        f.write(text.encode('utf8'))
        f.seek(0)
        return {'url': f}



def get_id(url):
    return re.find(r'.com/([^/]+)', url) or url



class Downloader_syosetu(Downloader):
    type = 'syosetu'
    URLS = ['syosetu.com']
    MAX_CORE = 2
    detect_removed = False
    display_name = '小説家になろう'
    ACCEPT_COOKIES = [r'(.*\.)?syosetu\.com']
    atts = ['_title_', 'novel_ex']

    @classmethod
    def fix_url(cls, url):
        return f'https://ncode.syosetu.com/{get_id(url)}/'

    def read(self):
        for try_ in range(8):
            self.print_('get_session')
            try:
                self.session = get_session()
                self.purge_cookies()
                soup = downloader.read_soup(self.url, session=self.session)
                get_title_artist(soup)
                break
            except Exception as e:
                print(e)

        else:
            raise

        title, self.artist = get_title_artist(soup)
        self._title_ = title
        ncode = re.find(r'syosetu.com/([^/]+)', self.url, err='no ncode') #3938
        title_dir = clean_title(f'[{self.artist}] {title} ({ncode})')
        ex = soup.find('div', id='novel_ex')
        self.novel_ex = utils.get_text(ex, '') if ex else None
        texts = []

        # Range
        max_pid = get_max_range(self.cw)

        while check_alive(self.cw):
            subtitles = soup.findAll('dd', class_='subtitle')
            if subtitles:
                for subtitle in subtitles:
                    update = subtitle.parent.find('dt', class_='long_update')
                    update2 = None
                    if update:
                        for span in update.findAll('span'):
                            update2 = span.attrs['title']
                            span.decompose()

                        update = update.text.strip()
                    if update2:
                        update += f'  ({update2})'
                    a = subtitle.find('a')
                    subtitle = a.text.strip()
                    href = urljoin(self.url, a.attrs['href'])
                    if not re.search(f'ncode.syosetu.com/{get_id(self.url)}/[0-9]+', href):
                        self.print_(f'skip: {href}')
                        continue
                    text = Text({'referer': href, 'subtitle': subtitle, 'update': update, 'single': False})
                    texts.append(text)
            else:
                self.single = True
                text = Text({'referer': self.url, 'subtitle': title_dir, 'update': None, 'single': True})
                texts.append(text)
            if len(texts) >= max_pid:
                break
            if pager_next := soup.find('a', class_='novelview_pager-next'): #6830
                sleep(1)
                url_next = urljoin(self.url, pager_next['href'])
                self.print_(f'url_next: {url_next}')
                soup = downloader.read_soup(url_next, self.url, session=self.session)
            else:
                break
        self.print_(f'single: {self.single}')
        self.urls += texts

        self.title = title_dir

    def post_processing(self):
        if self.single:
            return
        names = self.cw.names
        filename = os.path.join(self.dir, f'[merged] {self.title}.txt')
        try:
            with utils.open(filename, 'wb') as f:
                f.write(f'    {self._title_}\n\n    \u4f5c\u8005\uff1a{self.artist}\n\n\n'.encode('utf8'))
                if self.novel_ex:
                    f.write(self.novel_ex.encode('utf8'))
                for i, file in enumerate(names):
                    self.cw.pbar.setFormat(f'[%v/%m]  {tr_("병합...")} [{i}/{len(names)}]')
                    with open(file, 'rb') as f_:
                        text = f_.read()
                    f.write(b'\n\n\n\n')
                    f.write(text)
        finally:
            self.cw.pbar.setFormat("[%v/%m]")


def get_title_artist(soup):
    artist = soup.find('div', class_='novel_writername').text.replace('\u4f5c\u8005', '').replace('\uff1a', '').replace(':', '').replace('\u3000', ' ').strip()
    rem = len(artist.encode('utf8', 'ignore')) + len('[merged] [] .txt') + len(' (n8273ds)')
    return clean_title(soup.find('p', class_='novel_title').text.strip(), n=-rem), clean_title(artist)


@try_n(22, sleep=30)
def get_text(url, subtitle, update, session):
    soup = downloader.read_soup(url, session=session)
    if update:
        update = '        ' + update
    else:
        update = ''

    story = utils.get_text(soup.find('div', id='novel_honbun'), '')

    p = soup.find('div', id='novel_p')
    p = '' if p is None else utils.get_text(p, '')
    if p:
        story = f'{p}\n\n════════════════════════════════\n\n{story}'

    #2888
    a = soup.find('div', id='novel_a')
    a = '' if a is None else utils.get_text(a, '')
    if a:
        story = f'{story}\n\n════════════════════════════════\n\n{a}'

    text = f'''────────────────────────────────

  ◆  {subtitle}{update}

────────────────────────────────


{story}'''
    return text


def get_session():
    session = Session()
    session.cookies.set(name='over18', value='yes', path='/', domain='.syosetu.com')
    return session
