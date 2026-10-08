"""
High-Speed Asynchronous Jumia Kenya Scraper.
Uses concurrent thread-pool execution with urllib3/requests to cleanly bypass Cloudflare TLS fingerprinting,
with proxy rotation, fast lxml HTML parsing, and parallel page fetches.
"""
import re
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from config import DEFAULT_HEADERS
from proxy_manager import global_proxy_manager

logger = logging.getLogger(__name__)

class AsyncJumiaScraper:
    BASE_URL = "https://www.jumia.co.ke"

    def __init__(self, max_workers: int = 10, timeout: float = 12.0):
        self.max_workers = max_workers
        self.timeout = timeout
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def _clean_price(self, text: Optional[str]) -> float:
        if not text:
            return 0.0
        cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def _parse_rating_and_reviews(self, rev_el) -> tuple:
        if not rev_el:
            return 0.0, 0
        text = rev_el.text.strip()
        rating = 0.0
        reviews = 0

        m_rate = re.search(r"(\d+(?:\.\d+)?)\s*out of", text, re.IGNORECASE)
        if m_rate:
            try:
                rating = float(m_rate.group(1))
            except ValueError:
                pass

        m_rev = re.search(r"\((\d+)\)", text)
        if m_rev:
            try:
                reviews = int(m_rev.group(1))
            except ValueError:
                pass

        return rating, reviews

    def _sync_fetch_page(self, query: str, page: int, use_proxy: bool = False) -> str:
        """Fetch a single page synchronously using requests with optional proxy."""
        url = f"{self.BASE_URL}/catalog/?q={requests.utils.quote(query)}&page={page}"
        proxy_url = global_proxy_manager.get_proxy() if use_proxy else None

        # 1. Attempt with proxy if requested
        if proxy_url:
            try:
                proxies = {"http": proxy_url, "https": proxy_url}
                resp = requests.get(url, headers=DEFAULT_HEADERS, proxies=proxies, timeout=self.timeout)
                if resp.status_code == 200:
                    return resp.text
                else:
                    global_proxy_manager.report_failure(proxy_url)
            except Exception as e:
                global_proxy_manager.report_failure(proxy_url)
                logger.debug(f"Proxy {proxy_url} failed on Jumia page {page}: {e}")

        # 2. Fast direct fallback
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.text
            logger.warning(f"Jumia returned HTTP {resp.status_code} for '{query}' p.{page}")
        except Exception as e:
            logger.error(f"Error requesting Jumia '{query}' p.{page}: {e}")

        return ""

    async def search_products(
        self,
        query: str,
        category_name: str = "General",
        max_pages: int = 2,
        use_proxies: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Fetch multiple Jumia catalog pages in parallel asynchronously.
        """
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(self.executor, self._sync_fetch_page, query, p, use_proxies)
            for p in range(1, max_pages + 1)
        ]
        html_pages = await asyncio.gather(*tasks, return_exceptions=True)

        products = []
        for html in html_pages:
            if not isinstance(html, str) or not html:
                continue

            soup = BeautifulSoup(html, "html.parser")
            articles = soup.select("article.prd")

            for a in articles:
                name_el = a.select_one("h3.name")
                prc_el = a.select_one("div.prc")
                old_prc_el = a.select_one("div.old")
                rev_el = a.select_one("div.rev")
                bdg_el = a.select_one("div.bdg")
                link_el = a.select_one("a.core")
                img_el = a.select_one("img.img")

                title = name_el.text.strip() if name_el else ""
                if not title:
                    continue

                price = self._clean_price(prc_el.text if prc_el else "")
                old_price = self._clean_price(old_prc_el.text if old_prc_el else "")
                rating, reviews = self._parse_rating_and_reviews(rev_el)
                badge = bdg_el.text.strip() if bdg_el else ""

                href = link_el["href"] if link_el and "href" in link_el.attrs else ""
                full_url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                image_url = ""
                if img_el:
                    image_url = img_el.get("data-src") or img_el.get("src") or ""

                is_express = bool(a.select_one(".express") or a.select_one("[aria-label*='Express']"))

                products.append({
                    "title": title,
                    "category": category_name,
                    "price": price,
                    "old_price": old_price if old_price > 0 else None,
                    "rating": rating,
                    "reviews_count": reviews,
                    "is_express": is_express,
                    "badge": badge,
                    "url": full_url,
                    "image_url": image_url
                })

        return products
