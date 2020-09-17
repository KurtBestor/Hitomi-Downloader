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
import json
from typing import Generator
from urllib.parse import urlparse

import clf2
from utils import Session, Downloader, Soup, clean_title


@Downloader.register
class DownloaderNaverPost(Downloader):
    type = "naver_post"  # 타입
    URLS = ["m.post.naver.com", "post.naver.com"]

    def init(self):
        self.url = self.url.replace("naver_post_", "")
        self.parsed_url = urlparse(self.url)
        self.soup = get_soup(self.url)

    def id(self):
        pass

    @property
    def name(self):
        return get_title(self.soup)

    def read(self):
        if self.parsed_url.path.startswith("/viewer"):
            self.title = self.name
            data_linkdatas = get_img_data_linkdatas(self.soup)


# https://github.com/KurtBestor/Hitomi-Downloader/blob/master/src/extractor/manatoki_downloader.py#L84 참고
def get_soup(url: str):
    session = Session()
    res = clf2.solve(url, session=session)
    soup = Soup(res["html"])
    return soup


# HTML5 data-* 속성이 사용됨.
def get_img_data_linkdatas(soup) -> list:
    a_elements = soup.find_all("a", {"data-linktype": "img"})  # 링크 타입이 img인것만 전부 찾음
    return [a_element["data-linkdata"] for a_element in a_elements]  # 링크 데이터 리스트


def generator_img_src_list(linkdatas: list) -> Generator:
    for linkdata in linkdatas:
        img_json = json.load(linkdata)  # a문제


def get_title(soup):
    title = soup.find("h3", class_="se_textarea")  # 포스트제목
    author = soup.find("span", class_="se_author")  # 작성자
    return clean_title(f"{title.text} ({author.text})")  # 무난하게 븉임
