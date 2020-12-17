# coding: UTF-8
# title: Hiyobi.me 북마크 다운로드 스크립트
# comment: Hiyobi.me 북마크를 다운로드합니다
# author: SaidBySolo

"""
MIT License

Copyright (c) 2020 Saebasol

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
import asyncio

import aiohttp

from utils import Downloader


@Downloader.register
class DownloaderHiyobiBookmark(Downloader):
    type = "hiyobibookmark"

    def init(self) -> None:
        self.url: str = self.url.replace("hiyobibookmark_", "").split("/")
        self.bookmark_info_list = []

    def read(self) -> None:
        if not len(self.url) == 2:
            return self.Invalid("이메일/비밀번호 형식으로 작성해주세요.")

        email = self.url[0]
        password = self.url[1]

        result = asyncio.run(self.main(email, password))

        if isinstance(result, str):
            url = f"https://hastebin.com/raw/{result}"
            self.title = result
            self.urls.append(url)
            self.filenames[url] = f"{result}.txt"
        else:
            return result

    async def main(self, email: str, password: str):
        token = await self.post_account_info(email, password)

        bookmark_info = await self.post_hiyobi_bookmark(token)

        bookmark_total_count: int = bookmark_info["count"]

        if bookmark_total_count == 0:
            return self.Invalid("북마크된 정보가 없는거같아요.")

        count = (
            round(bookmark_total_count / 15) + 1
            if not (bookmark_total_count / 15).is_integer()
            else round(bookmark_total_count / 15)
        ) + 1

        await self.add_in_bookmark_info_list(count, token)

        hastebin_key = await self.post_hastebin(self.bookmark_info_list)
        return hastebin_key

    async def add_in_bookmark_info_list(self, count: int, token: str) -> None:
        for paging in range(1, count):
            paged_bookmark_info = await self.post_hiyobi_bookmark(token, paging)
            self.parsing_bookmark(paged_bookmark_info["list"])

    def parsing_bookmark(self, bookmark_list: list) -> None:
        for bookmark_element in bookmark_list:
            search = bookmark_element["search"]
            number = bookmark_element["number"]
            if search:
                self.bookmark_info_list.append(search)
            elif number:
                self.bookmark_info_list.append(str(number))
            else:
                # 추후 디버깅
                raise Exception(bookmark_element)

    async def post(self, url: str, **kwargs) -> dict:
        async with aiohttp.ClientSession() as cs:
            async with cs.post(url, **kwargs) as r:
                return await r.json()

    async def post_hastebin(self, bookmark_text: list) -> str:
        response = await self.post(
            "https://hastebin.com/documents", data="\n".join(bookmark_text)
        )
        return response["key"]

    async def post_hiyobi_bookmark(self, token: str, paging: int = 1) -> dict:
        await asyncio.sleep(1)
        response = await self.post(
            f"https://api.hiyobi.me/bookmark/{paging}",
            headers={
                "referrer": "https://hiyobi.me/",
                "authorization": f"Bearer {token}",
            },
            json={"paging": paging},
        )
        return response

    async def post_account_info(self, email: str, password: str) -> str:
        response = await self.post(
            "https://api.hiyobi.me/user/login",
            headers={
                "referrer": "https://hiyobi.me/",
            },
            json={"email": email, "password": password, "remember": True},
        )
        return response["data"]["token"]
