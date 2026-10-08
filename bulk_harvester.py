"""
Bulk Catalog Harvester for Jumia Kenya.
Crawls deep category trees up to 50 pages with resume support, proxy rotation,
and incremental SQLite database commits.
"""
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional
import requests
from bs4 import BeautifulSoup
from config import DEFAULT_HEADERS
from template_loader import global_template_loader
from proxy_manager import global_proxy_manager
from database import save_jumia_product, log_scan_event, get_connection

logger = logging.getLogger(__name__)

class BulkCatalogHarvester:
    BASE_URL = "https://www.jumia.co.ke"

    def __init__(self, timeout: float = 12.0, max_concurrent: int = 5):
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    def _clean_price(self, text: Optional[str]) -> float:
        if not text:
            return 0.0
        import re
        cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def _parse_rating_and_reviews(self, rev_el) -> tuple:
        import re
        if not rev_el:
            return 0.0, 0
        text = rev_el.text.strip()
        rating, reviews = 0.0, 0
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

    def _fetch_category_page(self, slug: str, page: int, use_proxy: bool = False) -> str:
        """Fetch a category catalog page synchronously with optional proxy."""
        url = f"{self.BASE_URL}/{slug}/?page={page}"
        proxy_url = global_proxy_manager.get_proxy() if use_proxy else None

        if proxy_url:
            try:
                proxies = {"http": proxy_url, "https": proxy_url}
                resp = requests.get(url, headers=DEFAULT_HEADERS, proxies=proxies, timeout=self.timeout)
                if resp.status_code == 200:
                    return resp.text
                global_proxy_manager.report_failure(proxy_url)
            except Exception as e:
                global_proxy_manager.report_failure(proxy_url)
                logger.debug(f"Proxy failed on {url}: {e}")

        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.text
        except Exception as e:
            logger.error(f"Error requesting {url}: {e}")

        return ""

    async def harvest_category(
        self,
        category_name: str,
        start_page: int = 1,
        max_pages: int = 10,
        use_proxies: bool = False,
        on_progress = None
    ) -> Dict[str, Any]:
        """
        Deep crawl up to 50 pages of a category and save items incrementally.
        """
        slug = global_template_loader.get_slug_for_category(category_name)
        start_time = time.time()
        logger.info(f"Starting bulk harvest for '{category_name}' (Slug: {slug}), pages {start_page} to {max_pages}...")

        total_saved = 0
        pages_crawled = 0
        loop = asyncio.get_running_loop()

        for page in range(start_page, max_pages + 1):
            if on_progress:
                pct = (page - start_page + 1) / (max_pages - start_page + 1)
                on_progress(f"Crawling {category_name} (Page {page}/{max_pages}) - Saved: {total_saved} items...", pct)

            html = await loop.run_in_executor(None, self._fetch_category_page, slug, page, use_proxies)
            if not html:
                logger.warning(f"No content returned for {slug} page {page}. Stopping crawl.")
                break

            soup = BeautifulSoup(html, "html.parser")
            articles = soup.select("article.prd")
            if not articles:
                logger.info(f"End of catalog reached at page {page} for {category_name}.")
                break

            page_items = []
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

                item_record = {
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
                }
                save_jumia_product(item_record)
                total_saved += 1

            pages_crawled += 1
            # Polite delay between pages
            await asyncio.sleep(0.6)

        duration = round(time.time() - start_time, 2)
        log_scan_event(
            scan_type="bulk_category_harvest",
            target=category_name,
            jumia_c=total_saved,
            jiji_c=0,
            deals_c=0,
            duration=duration
        )

        if on_progress:
            on_progress(f"Bulk harvest complete! Indexed {total_saved} products across {pages_crawled} pages in {duration}s.", 1.0)

        return {
            "category": category_name,
            "pages_crawled": pages_crawled,
            "items_saved": total_saved,
            "duration_sec": duration
        }
