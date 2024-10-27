import downloader, os
from utils import Downloader, query_url, clean_title, get_ext, Session, Soup, File, urljoin, fix_dup, try_n
from hashlib import md5
import clf2
import os



class Downloader_file(Downloader):
    type = 'file'
    single = True
    URLS = []
    ACC_MTIME = True

    @classmethod
    def fix_url(cls, url):
        if url and '://' not in url:
            url = 'https://' + url.lstrip('/')
        return url

    @try_n(4)
    def read(self):
        if not self.url.strip():
            raise Exception('empty url')
        self.session = Session() #6525
        qs = query_url(self.url)
        for key in qs:
            if key.lower() in ('file', 'filename'):
                name = qs[key][-1]
                break
        else:
            name = self.url
            for esc in ['?', '#']:
                name = name.split(esc)[0]
            name = os.path.basename(name.strip('/'))

        try:
            ext = downloader.get_ext(self.url)
        except:
            ext = ''
        if not ext:
            ext = get_ext(name)

        name = os.path.splitext(name)[0]
        id_ = md5(self.url.encode('utf8')).hexdigest()[:8]

        if ext.lower()[1:] in ['htm', 'html']:
            self.single = False
            res = clf2.solve(self.url, session=self.session, cw=self.cw)
            soup = Soup(res['html'])
            ext = ''
            title = soup.find('meta', {'property': 'og:title'})
            title = title['content']
            names = {}
            srcs = set()
            for img in soup.findAll('img'):
                src = img.get('src')
                if not src:
                    continue
                src = urljoin(self.url, src)
                if src in srcs:
                    continue
                srcs.add(src)
                name = os.path.basename(src.split('?')[0].split('#')[0])
                ext = get_ext(name)
                if not ext:
                    try:
                        ext = downloader.get_ext(src)
                    except Exception as e:
                        print(e)
                name = clean_title(os.path.splitext(name)[0], n=-len(ext)) + ext
                name = fix_dup(name, names)
                file = File({'referer': self.url, 'url': src, 'name': name})
                self.urls.append(file)
        else:
            title = name
            file = File({'url': self.url, 'name': name})
            self.urls.append(file)

        tail = f' ({id_})'
        if self.single:
            tail += f'{ext}'
        self.title = clean_title(title, n=-len(tail)) + tail

        def parse(s):
            _ = {'none': None, 'true': True, 'false': False}.get(s.lower(), ' ')
            return int(s) if _ == ' ' else _

        kwargs = {}
        c = self.cw.comment()
        if c.startswith('segment:') and (s := c[len('segment:'):].strip()):
            if s.count('=') != 1:
                raise ValueError('not one "="')
            key, value = s.split('=')
            kwargs[key] = parse(value)
        if self.single or kwargs:
            self.enableSegment(**kwargs)
