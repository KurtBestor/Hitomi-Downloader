# coding: UTF-8
# title: Download naver post image
# author: SaidBySolo
# comment: 네이버 포스트의 이미지를 다운로드합니다

"""
MIT License

Copyright (c) 2020 SaidBySolo

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import clf2
from utils import Session, Downloader, Soup


@Downloader.register
class DownloaderNaverPost(Downloader):
    type = "post"  # 타입

    def init(self):
        pass

    def id(self):
        pass

    def read(self):
        self.title = "test"
        url = self.url.replace("post_", "")
        html = get_soup(url)
        img_urls = get_img_links(html)
        self.title = "aa"
        for img_url in img_urls:
            self.urls.append(img_url)


def get_img_links(soup):
    imgs_element = soup.find_all(
        "img", id=lambda value: value and value.startswith("SEDOC"), src=True
    )

    img_links = [img_element["src"] for img_element in imgs_element]
    return img_links


def get_posts(url):
    pass


def get_soup(url):
    session = Session()
    res = clf2.solve(url, session=session)
    soup = Soup(res["html"])
    return soup