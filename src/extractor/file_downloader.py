import downloader, os
from utils import Downloader, query_url, clean_title, get_ext, Session
from hashlib import md5



class Downloader_file(Downloader):
    type = 'file'
    single = True
    URLS = []

    def init(self):
        self.session = Session() #6525

    @classmethod
    def fix_url(cls, url):
        if url and '://' not in url:
            url = 'https://' + url.lstrip('/')
        return url

    def read(self):
        if not self.url.strip():
            raise Exception('empty url')
        qs = query_url(self.url)
        for key in qs:
            if key.lower() in ('file', 'filename'):
                name = qs[key][(-1)]
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

        self.urls.append(self.url)

        id_ = md5(self.url.encode('utf8')).hexdigest()[:8]
        tail = ' ({}){}'.format(id_, ext)
        filename = clean_title(name, n=-len(tail)) + tail

        self.filenames[self.url] = filename

        self.title = filename
