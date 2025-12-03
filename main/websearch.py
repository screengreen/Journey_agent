from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

import requests


@dataclass
class Page:
    url: str
    title: Optional[str]
    html: str


class TavilyHtmlFetcher:
    """
    Класс для поиска страниц в интернете и получения их HTML-кода.
    Использует Tavily Search API и обычный HTTP-запрос для HTML.
    """

    def __init__(
        self,
        default_max_results: int = 5,
        request_timeout: int = 10,
        tavily_endpoint: str = "https://api.tavily.com/search",
    ):
        api_key = os.getenv("TAVILY_API_KEY")
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Переменная окружения TAVILY_API_KEY не найдена. "
                "Проверь .env или окружение."
            )

        self.api_key = api_key
        self.default_max_results = default_max_results
        self.request_timeout = request_timeout
        self.tavily_endpoint = tavily_endpoint


    def search(self, query: str, max_results: Optional[int] = None) -> List[Page]:
        """
        Делает поиск по запросу и возвращает список страниц с их HTML-кодом.

        :param query: поисковой запрос
        :param max_results: макс. количество результатов
        :return: список Page(url, title, html)
        """
        max_results = max_results or self.default_max_results

        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }

        resp = requests.post(
            self.tavily_endpoint,
            json=payload,
            timeout=self.request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])

        pages: List[Page] = []

        for item in results:
            url = item.get("url")
            title = item.get("title")

            if not url:
                continue

            html = ""
            try:
                resp = requests.get(url, timeout=self.request_timeout)
                resp.raise_for_status()
                html = resp.text
            except Exception:
                html = ""

            pages.append(Page(url=url, title=title, html=html))

        return pages
