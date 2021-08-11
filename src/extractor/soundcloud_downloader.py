#coding: utf8
import downloader
import json
from io import BytesIO
from utils import Downloader, LazyUrl, get_print, try_n, lock, clean_title
from error_printer import print_error
import os
from timee import sleep
import ffmpeg
import ytdl
from m3u8_tools import M3u8_stream
CLIENT_ID = None


@lock
def get_cid(force=False):
    global CLIENT_ID
    if CLIENT_ID is None or force:
        print('update cid...')
        d = ytdl.YoutubeDL()
        e = ytdl.extractor.soundcloud.SoundcloudIE(d)
        e._update_client_id()
        CLIENT_ID = e._CLIENT_ID
    return CLIENT_ID


class Audio(object):
    _url = None
    
    def __init__(self, info, album_art, cw=None):
        self.info = info
        self.album_art = album_art
        self.cw = cw
        self.url = LazyUrl(info['webpage_url'], self.get, self, pp=self.pp)

    def get(self, url):
        print_ = get_print(self.cw)
        if self._url:
            return self._url

        info = self.info
        
##        ydl = ytdl.YoutubeDL()
##        info = ydl.extract_info(url)

        formats = info['formats']
        print(formats)
        formats = sorted(formats, key=lambda x: int(x.get('abr', 0)), reverse=True)
        url_audio = None
        
        for format in formats:
            protocol = format['protocol']
            print_(u'【{}】 format【{}】 abr【{}】'.format(protocol, format['format'], format.get('abr', 0)))
            if not url_audio and protocol in ['http', 'https']:
                url_audio = format['url']

        if not url_audio:
            url_audio = M3u8_stream(formats[0]['url'])
            self.album_art = False#
        
        self.username = info['uploader']
        self.title = u'{} - {}'.format(self.username, info['title'])
        self.filename = u'{}{}'.format(clean_title(self.title, allow_dot=True, n=-4), '.mp3')

        thumb = None
        for t in info['thumbnails'][::-1]:
            width = t.get('width', 1080)
            if not 100 <= width <= 500:
                continue
            url_thumb = t['url']
            thumb = BytesIO()
            try:
                downloader.download(url_thumb, buffer=thumb)
                break
            except Exception as e:
                print(e)
                thumb = None
        self.thumb = thumb
        
        self._url = url_audio
        return self._url

    def pp(self, filename):
        cw = self.cw
        with cw.convert(self):
            return self._pp(filename)

    def _pp(self, filename):
        if self.thumb and self.album_art:
            self.thumb.seek(0)#
            ffmpeg.add_cover(filename, self.thumb, {'artist':self.username, 'title':self.info['title']}, cw=self.cw)


@Downloader.register
class Downloader_soundcloud(Downloader):
    type = 'soundcloud'
    single = True
    URLS = ['soundcloud.com']
    #lock = True
    audio = None
    display_name = 'SoundCloud'
    
    def init(self):
        if 'soundcloud.com' in self.url.lower():
            self.url = self.url.replace('http://', 'https://')
        else:
            self.url = 'https://soundcloud.com/{}'.format(self.url)

    def read(self):
        album_art = self.ui_setting.albumArt.isChecked()
        info = get_audios(self.url, self.cw, album_art)
        audios = info['audios']
        
        if not audios:
            raise Exception('no audios')

        # first audio must be valid
        while audios:
            audio = audios[0]
            try:
                audio.url()
                break
            except Exception as e:
                e_ = e
                print(e)
                audios.remove(audio)
        else:
            raise e_

        if len(audios) > 1:
            audio = self.process_playlist(info['title'], audios)
        else:
            self.urls.append(audio.url)
            self.title = audio.title

        self.artist = audio.username
        self.setIcon(audio.thumb)


@try_n(2)
def get_audios(url, cw, album_art):
    print_ = get_print(cw)
    url = url.rstrip('/')
    if url.count('/') == 3:
        url += '/tracks'

    info = {
        #'extract_flat': True,
        }

    ydl = ytdl.YoutubeDL(cw=cw)
    info = ydl.extract_info(url)
    if 'entries' in info:
        entries = info['entries']
        title = info['title']
        for _type in ['All', 'Tracks', 'Albums', 'Sets', 'Reposts', 'Likes', 'Spotlight']:
            x = '({})'.format(_type)
            if x in title:
                title = title.replace(x, '')
                kind = _type
                break
        else:
            kind = 'Playlist'
        print_(u'kind: {}'.format(kind))
        info['title'] = u'[{}] {}'.format(kind.capitalize(), title)
    else:
        entries = [info]

    audios = []
    for e in entries:
        if '/sets/' in e['webpage_url']:
            continue
        audio = Audio(e, album_art, cw=cw)
        audios.append(audio)

    info['audios'] = audios
    
    return info


