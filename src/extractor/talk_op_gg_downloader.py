# coding: UTF-8
# title: Download talk op.gg image
# author: SaidBySolo
# comment: op.gg 커뮤니티의 이미지를 다운로드합니다

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

import requests
from utils import Downloader, Soup


@Downloader.register
class DownloaderTalkOPGG(Downloader):
    type = "talkopgg"
    URLS = ["talk.op.gg"]

    def init(self) -> None:
        pass

    def read(self) -> None:
        response = requests.get(self.url)
        soup = Soup(response.text)

        self.title = soup.find("title").text

        image_element_list = soup.find("div", class_="article-content").findAll("img")

        for image_element in image_element_list:
            self.urls.append(image_element["src"])
