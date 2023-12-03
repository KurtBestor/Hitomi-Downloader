#coding:utf8
import downloader
import utils
from utils import Soup, urljoin, LazyUrl, try_n, Downloader, clean_title, Session
import ree as re
from io import BytesIO
import os
from translator import tr_


class Text:

    def __init__(self, title, update, url, session, single):
        if single:
            self.p = None
            self.title = title
        else:
            self.p = int(re.findall('/([0-9]+)', url)[(-1)])
            title = '[{:04}] {}'.format(self.p, title)
            title = clean_title(title, n=-4)
            self.title = title
        self.filename = '{}.txt'.format(self.title)

        def f(url):
            text = get_text(url, self.title, update, session)
            f = BytesIO()
            f.write(text.encode('utf8'))
            f.seek(0)
            return f

        self.url = LazyUrl(url, f, self)



class Downloader_syosetu(Downloader):
    type = 'syosetu'
    URLS = ['syosetu.com']
    MAX_CORE = 2
    detect_removed = False
    display_name = '小説家になろう'
    ACCEPT_COOKIES = [r'(.*\.)?syosetu\.com']

    def init(self):
        self.url = 'https://ncode.syosetu.com/{}/'.format(self.id_)

    @property
    def id_(self):
        ids = re.findall('.com/([^/]+)', self.url)
        if ids:
            id = ids[0]
        else:
            id = self.url
        return id

    def read(self):
        for try_ in range(8):
            self.print_('get_session')
            try:
                session = get_session()
                html = downloader.read_html(self.url, session=session)
                soup = Soup(html)
                get_title_artist(soup)
                break
            except Exception as e:
                print(e)

        else:
            raise

        title, self.artist = get_title_artist(soup)
        self.__title = title
        ncode = re.find(r'syosetu.com/([^/]+)', self.url, err='no ncode') #3938
        title_dir = clean_title('[{}] {} ({})'.format(self.artist, title, ncode))
        ex = soup.find('div', id='novel_ex')
        self.novel_ex = utils.get_text(ex, '') if ex else None
        texts = []
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
                    update += '  ({})'.format(update2)
                a = subtitle.find('a')
                subtitle = a.text.strip()
                href = urljoin(self.url, a.attrs['href'])
                if not re.search('ncode.syosetu.com/{}/[0-9]+'.format(self.id_), href):
                    self.print_('skip: {}'.format(href))
                    continue
                text = Text(subtitle, update, href, session, False)
                texts.append(text)

        else:
            self.single = True
            text = Text(title_dir, None, self.url, session, True)
            texts.append(text)
        self.print_('single: {}'.format(self.single))
        for text in texts:
            if self.single:
                file = os.path.join(utils.dir(self.type, '', self.cw), text.filename)
            else:
                file = os.path.join(utils.dir(self.type, title_dir, self.cw), text.filename)
            if os.path.isfile(file):
                self.urls.append(file)
            else:
                self.urls.append(text.url)

        self.title = title_dir

    def post_processing(self):
        if self.single:
            return
        names = self.cw.names
        filename = os.path.join(self.dir, '[merged] {}.txt'.format(self.title))
        try:
            with utils.open(filename, 'wb') as f:
                f.write('    {}\n\n    \u4f5c\u8005\uff1a{}\n\n\n'.format(self.__title, self.artist).encode('utf8'))
                if self.novel_ex:
                    f.write(self.novel_ex.encode('utf8'))
                for i, file in enumerate(names):
                    self.cw.pbar.setFormat(u"[%v/%m]  {} [{}/{}]".format(tr_('\ubcd1\ud569...'), i, len(names)))
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
    html = downloader.read_html(url, session=session)
    soup = Soup(html)
    if update:
        update = '        ' + update
    else:
        update = ''

    story = utils.get_text(soup.find('div', id='novel_honbun'), '')

    p = soup.find('div', id='novel_p')
    p = '' if p is None else utils.get_text(p, '')
    if p:
        story = '{}\n\n════════════════════════════════\n\n{}'.format(p, story)

    #2888
    a = soup.find('div', id='novel_a')
    a = '' if a is None else utils.get_text(a, '')
    if a:
        story = '{}\n\n════════════════════════════════\n\n{}'.format(story, a)

    text ='''────────────────────────────────

  ◆  {}{}

────────────────────────────────


{}'''.format(subtitle, update, story)
    return text


def get_session():
    session = Session()
    session.cookies.set(name='over18', value='yes', path='/', domain='.syosetu.com')
    return session
