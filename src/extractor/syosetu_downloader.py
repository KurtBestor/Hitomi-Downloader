#coding:utf8
import downloader
import utils
from utils import Soup, urljoin, LazyUrl, try_n, Downloader, get_outdir, get_print, clean_title, Session
import ree as re
from io import BytesIO
from timee import sleep
import os
from translator import tr_


class Text(object):

    def __init__(self, title, update, url, session, single):
        if single:
            self.p = None
            self.title = title
        else:
            self.p = int(re.findall('/([0-9]+)', url)[(-1)])
            title = (u'[{:04}] {}').format(self.p, title)
            title = clean_title(title, n=-4)
            self.title = title
        self.filename = (u'{}.txt').format(self.title)

        def f(url):
            text = get_text(url, self.title, update, session)
            f = BytesIO()
            f.write(text.encode('utf8'))
            f.seek(0)
            return f

        self.url = LazyUrl(url, f, self)


@Downloader.register
class Downloader_syosetu(Downloader):
    type = 'syosetu'
    URLS = ['syosetu.com']
    MAX_CORE = 2
    detect_removed = False
    display_name = '小説家になろう'

    def init(self):
        self.url = (u'https://ncode.syosetu.com/{}/').format(self.id_)

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
        self.novel_ex = ex.text.strip() if ex else None
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
                    update += (u'  ({})').format(update2)
                a = subtitle.find('a')
                subtitle = a.text.strip()
                href = urljoin(self.url, a.attrs['href'])
                if not re.search(('ncode.syosetu.com/{}/[0-9]+').format(self.id_), href):
                    self.print_((u'skip: {}').format(href))
                    continue
                text = Text(subtitle, update, href, session, False)
                texts.append(text)

        else:
            self.single = True
            text = Text(title_dir, None, self.url, session, True)
            texts.append(text)
        self.print_((u'single: {}').format(self.single))
        outdir = get_outdir('syosetu')
        for text in texts:
            if self.single:
                file = os.path.join(outdir, text.filename)
            else:
                file = os.path.join(outdir, title_dir, text.filename)
            if os.path.isfile(file):
                self.urls.append(file)
            else:
                self.urls.append(text.url)

        self.title = title_dir

    def post_processing(self):
        if self.single:
            return
        names = self.cw.names
        filename = os.path.join(self.dir, (u'[merged] {}.txt').format(self.title))
        try:
            with utils.open(filename, 'wb') as f:
                f.write(u'    {}\n\n    \u4f5c\u8005\uff1a{}\n\n\n'.format(self.__title, self.artist).encode('utf8'))
                if self.novel_ex:
                    f.write(self.novel_ex.encode('utf8'))
                for i, file in enumerate(names):
                    self.cw.pbar.setFormat(u"[%v/%m]  {} [{}/{}]".format(tr_(u'\ubcd1\ud569...'), i, len(names)))
                    with open(file, 'rb') as f_:
                        text = f_.read()
                    f.write(b'\n\n\n\n')
                    f.write(text)
        finally:
            self.cw.pbar.setFormat("[%v/%m]")


def get_title_artist(soup):
    artist = soup.find('div', class_='novel_writername').text.replace(u'\u4f5c\u8005', '').replace(u'\uff1a', '').replace(':', '').replace(u'\u3000', ' ').strip()
    rem = len(artist.encode('utf8', 'ignore')) + len('[merged] [] .txt') + len(' (n8273ds)')
    return clean_title(soup.find('p', class_='novel_title').text.strip(), n=-rem), clean_title(artist)


@try_n(22, sleep=30)
def get_text(url, subtitle, update, session):
    html = downloader.read_html(url, session=session)
    soup = Soup(html)
    if update:
        update = u'        ' + update
    else:
        update = ''
        
    story = soup.find('div', id='novel_honbun').text.strip()
        
    p = soup.find('div', id='novel_p')
    p = '' if p is None else p.text.strip()
    if p:
        story = '{}\n\n════════════════════════════════\n\n{}'.format(p, story)
        
    #2888
    a = soup.find('div', id='novel_a')
    a = '' if a is None else a.text.strip()
    if a:
        story = '{}\n\n════════════════════════════════\n\n{}'.format(story, a)
        
    text =u'''────────────────────────────────

  ◆  {}{}

────────────────────────────────


{}'''.format(subtitle, update, story)
    return text


def get_session():
    session = Session()
    session.cookies.set(name='over18', value='yes', path='/', domain='.syosetu.com')
    return session


