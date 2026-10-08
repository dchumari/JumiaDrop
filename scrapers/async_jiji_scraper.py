"""
High-Speed Asynchronous Jiji Kenya Scraper.
Uses concurrent thread-pool execution with requests and proxy rotation to fetch wholesale listings from Jiji API.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional
import requests
from config import JIJI_API_HEADERS, NAIROBI_ACCEPTED_REGIONS
from proxy_manager import global_proxy_manager

logger = logging.getLogger(__name__)

class AsyncJijiScraper:
    API_URL = "https://jiji.co.ke/api_web/v1/listing"
    BASE_URL = "https://jiji.co.ke"

    def __init__(self, max_workers: int = 10, timeout: float = 12.0):
        self.max_workers = max_workers
        self.timeout = timeout
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def _is_nairobi_location(self, region_name: str, location_text: str) -> bool:
        combined = f"{region_name} {location_text}".lower()
        return any(nairobi_kw in combined for nairobi_kw in NAIROBI_ACCEPTED_REGIONS)

    def _sync_fetch_page(self, query: str, page: int, use_proxy: bool = False) -> Dict[str, Any]:
        """Fetch a single page from Jiji API with optional proxy rotation."""
        params = {
            "query": query,
            "region_slug": "nairobi",
            "page": page
        }
        proxy_url = global_proxy_manager.get_proxy() if use_proxy else None

        # 1. Attempt with proxy if requested
        if proxy_url:
            try:
                proxies = {"http": proxy_url, "https": proxy_url}
                resp = requests.get(self.API_URL, params=params, headers=JIJI_API_HEADERS, proxies=proxies, timeout=self.timeout)
                if resp.status_code == 200:
                    return resp.json()
                else:
                    global_proxy_manager.report_failure(proxy_url)
            except Exception as e:
                global_proxy_manager.report_failure(proxy_url)
                logger.debug(f"Proxy {proxy_url} failed on Jiji page {page}: {e}")

        # 2. Fast direct fallback
        try:
            resp = requests.get(self.API_URL, params=params, headers=JIJI_API_HEADERS, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
            logger.warning(f"Jiji API returned HTTP {resp.status_code} for '{query}' p.{page}")
        except Exception as e:
            logger.error(f"Error requesting Jiji API '{query}' p.{page}: {e}")

        return {}

    async def search_adverts(
        self,
        query: str,
        category_name: str = "General",
        max_pages: int = 2,
        strict_nairobi: bool = True,
        use_proxies: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Asynchronously search Jiji across multiple pages concurrently.
        """
        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(self.executor, self._sync_fetch_page, query, p, use_proxies)
            for p in range(1, max_pages + 1)
        ]
        pages_data = await asyncio.gather(*tasks, return_exceptions=True)

        adverts = []
        for data in pages_data:
            if not isinstance(data, dict):
                continue

            raw_items = data.get("adverts_list", {}).get("adverts", [])
            for item in raw_items:
                title = item.get("title", "").strip()
                if not title:
                    continue

                price_obj = item.get("price_obj") or {}
                price_val = price_obj.get("value")
                if price_val is None:
                    price_title = item.get("price_title", "")
                    digits = "".join(filter(str.isdigit, price_title))
                    price_val = float(digits) if digits else 0.0
                else:
                    price_val = float(price_val)

                if price_val <= 0:
                    continue

                region_name = item.get("region_name", "")
                location_text = item.get("region_item_text", "")

                if strict_nairobi and not self._is_nairobi_location(region_name, location_text):
                    continue

                rel_url = item.get("url", "")
                full_url = f"{self.BASE_URL}{rel_url}" if rel_url.startswith("/") else rel_url

                image_url = ""
                image_obj = item.get("image_obj")
                if isinstance(image_obj, dict):
                    image_url = image_obj.get("url", "")
                elif item.get("images") and len(item["images"]) > 0:
                    image_url = item["images"][0].get("url", "")

                adverts.append({
                    "id": item.get("id"),
                    "title": title,
                    "category": category_name,
                    "price": price_val,
                    "region_name": region_name,
                    "location_text": location_text,
                    "short_description": item.get("short_description", ""),
                    "url": full_url,
                    "image_url": image_url,
                    "user_id": str(item.get("user_id") or ""),
                    "user_phone": item.get("user_phone")
                })

        return adverts
