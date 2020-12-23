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
import codecs
import json
import re

from distutils.util import strtobool
from typing import Generator
from urllib.parse import ParseResult, urlparse, parse_qs

import requests

import clf2
import page_selector

from utils import Session, Downloader, Soup, clean_title

class Page(object):
    def __init__(self, title, url):
        self.title = clean_title(title)
        self.url = url


@Downloader.register
class DownloaderNaverPost(Downloader):
    type = "naverpost"  # 타입
    URLS = ["m.post.naver.com", "post.naver.com"]

    def init(self):
        self.parsed_url = urlparse(self.url)  # url 나눔
        self.soup = get_soup(self.url)

    @property
    def client(self):
        return Client(self.parsed_url, self.soup)

    def read(self):
        if self.client.single:
            self.title = self.client.title
            posts = self.client.posts
        else:
            raise NotImplementedError

        for img_link in img_src_generator(posts):
            self.urls.append(img_link)


# https://github.com/KurtBestor/Hitomi-Downloader/blob/master/src/extractor/manatoki_downloader.py#L106 참고
@page_selector.register("naverpost")
def f(url):
    client = Client(urlparse(url), get_soup(url))
    return [
        page for page_list in client.posts for page in page_list
    ]  # 2차원 리스트 -> 1차원 리스트


# https://github.com/KurtBestor/Hitomi-Downloader/blob/master/src/extractor/manatoki_downloader.py#L84 참고
def get_soup(url: str):
    res = clf2.solve(url)
    return Soup(res["html"])


# 페이지 파싱에서 사용되는 파서
def page_soup(url: str):
    get_html_regex = re.compile(r"\"html\"\:(.+)(\n|\s)\}")
    response = requests.get(url)
    like_html = get_html_regex.search(response.text)[1]
    html = decode_escapes(like_html).replace(r"\/", "/")
    return Soup(html)


# HTML5 data-* 속성이 사용됨.
def get_img_data_linkdatas(soup: Soup) -> list:
    a_elements = soup.find_all("a", {"data-linktype": "img"})  # 링크 타입이 img인것만 전부 찾음
    return [a_element["data-linkdata"] for a_element in a_elements]  # 링크 데이터 리스트


def img_src_generator(linkdatas: list) -> Generator:
    for linkdata in linkdatas:
        data = json.loads(linkdata)
        if data.get("linkUse") is None:
            yield data["src"]  # 제네레이터
        else:
            if not strtobool(data["linkUse"]):
                yield data["src"]


# https://stackoverflow.com/a/24519338 참고
def decode_escapes(like_html: str) -> str:
    escape_sequence_regex = re.compile(
        r"""
        ( \\U........      # 8-digit hex escapes
        | \\u....          # 4-digit hex escapes
        | \\x..            # 2-digit hex escapes
        | \\[0-7]{1,3}     # Octal escapes
        | \\N\{[^}]+\}     # Unicode characters by name
        | \\[\\'"abfnrtv]  # Single-character escapes
        )""",
        re.UNICODE | re.VERBOSE,
    )

    return escape_sequence_regex.sub(
        lambda match: codecs.decode(match.group(0), "unicode-escape"), like_html
    )


# 제목
class Title:
    def __init__(self, soup: Soup):
        self.soup = soup

    def get_profile_title(self) -> clean_title:
        profile_name = self.soup.find("p", class_="nick_name").find(
            "span", class_="name"
        )  # 프로필 닉네임
        return clean_title(profile_name.text)  # 닉네임으로만

    def get_series_title(self) -> clean_title:
        series_name = self.soup.find("h2", class_="tit_series").find(
            "span", class_="ell"
        )  # 시리즈 제목
        author = self.soup.find("div", class_="series_author_wrap").find(
            "strong", class_="ell1"
        )  # 작성자
        return clean_title(f"{series_name.text} ({author.text})")  # 무난하게 붙임

    def get_title(self) -> clean_title:
        title = self.soup.find("h3", class_="se_textarea")  # 포스트 제목
        author = self.soup.find("span", class_="se_author")  # 작성자
        return clean_title(f"{title.text.replace(' ', '')} ({author.text})")  # 무난하게 붙임


# 총 포스트 수
class Total:
    def __init__(self, soup: Soup):
        self.soup = soup

    # 0: 팔로워 1: 팔로잉 2: 포스트 3: 좋아요한글
    def get_total_post(self):
        profile_info = self.soup.find("div", class_="expert_num_info")  # 프로필 정보
        total_post_element = profile_info.find_all("li", class_="inner")[2]
        return total_post_element.find("span", class_="num").text  # 총몇개인지만 리턴

    # 0: 포스트 1: 팔로워
    def get_series_total_post(self):
        series_info = self.soup.find("div", class_="series_follow_area")  # 시리즈 정보
        total_post_element = series_info.find_all("a")[0]
        return total_post_element.find("em").text  # 총몇개인지만 리턴


# 왜 제네레이터로 만들었냐고 물어보면 그냥 수정할때나 다른곳에서도 편하게쓸려고 해놓음
class UrlGenerator:
    def __init__(self, parsed_url: ParseResult, total_count: int):
        self.parsed_url = parsed_url
        self.count = (
            round(int(total_count) / 20) + 1
            if not (int(total_count) / 20).is_integer()
            else round(int(total_count) / 20)
        )

    def all_post_url_generator(self):
        query = parse_qs(self.parsed_url.query)
        for i in range(self.count):
            new_url_query = (
                f"?memberNo={query['memberNo'][0]}&fromNo={i + 1}"  # 쿼리를 만듭시다
            )
            url = f"https://{self.parsed_url.netloc}/async{self.parsed_url.path}{new_url_query}"
            yield url

    def all_series_url_generator(self):
        query = parse_qs(self.parsed_url.query)
        for i in range(self.count):
            new_url_query = f"?memberNo={query['memberNo'][0]}&seriesNo={query['seriesNo'][0]}&fromNo={i + 1}"  # 쿼리를 만듭시다
            url = f"https://{self.parsed_url.netloc}/my/series/detail/more.nhn{new_url_query}"
            yield url


# 여기서 페이지 리스트 만듬
class PostPage:
    def __init__(self, soup: page_soup):
        self.soup = soup

    def all_post_page_generator(self):
        titles = self.soup.find_all("strong", class_="tit_feed ell")
        link_elements = self.soup.find_all("a", class_="link_end", href=True)

        page = [
            Page(title.text.replace(" ", ""), link_element["href"])
            for link_element, title in zip(link_elements, titles)
        ]

        yield page[::-1]

    def all_series_page_generator(self):
        titles = [
            element.find("span")
            for element in self.soup.find_all("div", class_="spot_post_name")
        ]
        link_elements = self.soup.find_all("a", class_="spot_post_area", href=True)

        page = [
            Page(title.text.replace(" ", ""), link_element["href"])
            for link_element, title in zip(link_elements, titles)
        ]

        yield page[::-1]


# 귀찮아서 프로퍼티 떡칠 여기서 제네레이터들 전부 리스트로 만들어줄거에요
class PageClient:
    def __init__(self, parsed_url: ParseResult, total):
        self.parsed_url = parsed_url
        self.total = total

    @property
    def all_url_list(self):
        ug = UrlGenerator(self.parsed_url, self.total)
        return list(ug.all_post_url_generator())

    @property
    def page_soup_list(self):
        return [page_soup(url) for url in self.all_url_list]

    def all_post(self):
        for soup in self.page_soup_list:
            page = PostPage(soup)
            return list(page.all_post_page_generator())

    def all_series_post(self):
        for soup in self.page_soup_list:
            page = PostPage(soup)
            return list(page.all_series_page_generator())


# 필요한 클래스 전부 상속후 편하게 쓸수있게 만듬
class Client(PageClient, Title, Total):
    def __init__(self, parsed_url: ParseResult, soup: Soup):
        Title.__init__(self, soup)
        Total.__init__(self, soup)

        if parsed_url.path.startswith("/viewer"):
            self.title = self.get_title()
            self.posts = get_img_data_linkdatas(self.soup)
            self.single = True

        elif parsed_url.path.startswith("/my.nhn"):
            PageClient.__init__(self, parsed_url, self.get_total_post())
            self.title = self.get_profile_title()
            self.posts = self.all_post()
            self.single = False

        elif parsed_url.path.startswith("/my/series"):
            PageClient.__init__(self, parsed_url, self.get_series_total_post())
            self.title = self.get_series_title()
            self.posts = self.all_series_post()
            self.single = False

        else:
            raise Exception("유효하지 않습니다.")
