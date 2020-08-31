# coding: UTF-8
# title: 마루마루(marumaru) 다운로드
# author: SaidBySolo

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

from bs4 import BeautifulSoup
import requests


@Downloader.register
class Downloader_MaruMaru(Downloader):
    type = "marumaru"
    URLS = ["marumaru.sale"]

    def init(self):
        self.url = self.url.replace("marumaru_", "")

    @property
    def id(self):
        return self.url

    def read(self):
        response = requests.get(self.url)

        soup = BeautifulSoup(response.text, "html.parser")

        self.title = soup.find("title").text

        soup_img_list = soup.find_all("img", class_="img-tag")
        if not soup_img_list:
            soup_img_list = soup.find("div", class_="view-img").find_all(
                class_="img-tag"
            )

        img_link_list = [img_link["src"] for img_link in soup_img_list]

        for img_link in img_link_list:
            if "https://marumaru.sale" in img_link:
                self.urls.append(img_link)
            else:
                self.urls.append("https://marumaru.sale" + img_link)
