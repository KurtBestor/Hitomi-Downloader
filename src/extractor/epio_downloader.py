import downloader
from utils import Soup, try_n, LazyUrl, Downloader, lock, get_print, clean_title
from timee import sleep
import base64
import json
import constants
import ree as re
KEY = b'gefdzfdef'


@Downloader.register
class Downloader_epio(Downloader):
    type = 'epio'
    URLS = ['epio.app']

    def read(self):
        info = get_info(self.url, cw=self.cw)
        
        imgs = info['imgs']

        for img in imgs:
            self.urls.append(img.url)

        self.title = clean_title(info['title'])


class Image(object):
    
    def __init__(self, url, referer, p):
        self._url = url
        self.url = LazyUrl(referer, self.get, self)
        ext = '.jpg'#
        self.filename = u'{:04}{}'.format(p, ext)

    def get(self, referer):
        return self._url


def get_info(url, cw=None):
    info = _get_info(url, cw)

    imgs = []
    html = info['content']
    soup = Soup(html)
    for img in soup.findAll('img'):
        src = img.attrs.get('src')
        if not src:
            continue

        # 1696
        if not isinstance(src, bytes):
            src = src.encode('utf8')
        t = base64.b64encode(src)
        if isinstance(t, bytes):
            t = t.decode('utf8')
        src = 'https://cdn1-images.epio.app/image/download/{}'.format(t)
        
        img = Image(src, url, len(imgs))
        imgs.append(img)
    info['imgs'] = imgs

    return info


def get_id(url):
    return re.find('article/detail/([0-9a-z]+)', url)


from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import aes
backend = default_backend()
def decrypt(s, cw=None):
    print_ = get_print(cw)
    key, iv = aes.key_and_iv(s[:16], KEY)
    print_('key: {}\niv: {}'.format(key, iv))
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=backend)
    r = -len(s) % 16
    if r:
        s += b'\x00' * r
    dec = cipher.decryptor()
    s_dec = dec.update(s[16:]) + dec.finalize()
    s_dec = s_dec[:-s_dec[-1]]
    if r:
        s_dec = s_dec[:-r]
    return s_dec



def _get_info(url, cw=None):
    id = get_id(url)

    url_api = 'https://girlimg.epio.app/api/articles/{}?lang=en-us'.format(id)
    html = downloader.read_html(url_api, referer=url)
    s = json.loads(html)['string']

    s = base64.b64decode(s)
    s = decrypt(s, cw)
    info = json.loads(s)

    return info
