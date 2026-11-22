"""Tavily implementation of Jade's provider-neutral SearchProvider contract."""
from __future__ import annotations

import asyncio
from urllib.parse import urlsplit

import requests

from ..web_search import SearchHit, SearchResponse


class TavilyProvider:
    name = "tavily"
    ENDPOINT = "https://api.tavily.com/search"

    def __init__(self, api_key: str, *, post=None):
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("TAVILY_API_KEY is required")
        self._api_key = api_key.strip()
        self._post = post or requests.post

    async def search(self, query: str, *, max_results: int, timeout: float) -> SearchResponse:
        return await asyncio.to_thread(self._search_sync, query, max_results, timeout)

    def _search_sync(self, query: str, max_results: int, timeout: float) -> SearchResponse:
        response = self._post(
            self.ENDPOINT,
            headers={
                "Authorization": "Bearer " + self._api_key,
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "topic": "general",
                "search_depth": "basic",
                "max_results": max(1, min(int(max_results), 5)),
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
                "include_published_date": True,
                "include_usage": True,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ValueError("invalid Tavily response")
        hits = []
        for entry in data["results"][:5]:
            if not isinstance(entry, dict):
                continue
            url = str(entry.get("url") or "")
            try:
                parsed = urlsplit(url)
            except ValueError:
                continue
            if parsed.scheme not in ("https", "http") or not parsed.netloc:
                continue
            hits.append(SearchHit(
                title=str(entry.get("title") or "")[:300],
                url=url[:2048],
                content=str(entry.get("content") or "")[:5000],
                published_date=(
                    str(entry["published_date"])[:100]
                    if entry.get("published_date") else None),
            ))
        usage = data.get("usage")
        credits = usage.get("credits") if isinstance(usage, dict) else None
        if not isinstance(credits, (int, float)) or isinstance(credits, bool):
            credits = None
        provider_request_id = data.get("request_id")
        return SearchResponse(
            results=tuple(hits), credits=credits,
            provider_request_id=(
                str(provider_request_id)[:150] if provider_request_id else None),
        )
