import downloader, json, os
from constants import try_n
from utils import Downloader, query_url, clean_title, get_ext
from timee import sleep
from hashlib import md5


@Downloader.register
class Downloader_file(Downloader):
    type = 'file'
    single = True
    URLS = []

    @classmethod
    def fix_url(cls, url):
        if '://' not in url:
            url = 'https://' + url.lstrip('/')
        return 'file_' + url

    def read(self):
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
