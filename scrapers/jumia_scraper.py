"""
Jumia Kenya Scraper.
Scrapes product catalog search results, extracting prices, review counts, ratings, and URLs.
"""
import re
import time
import random
import logging
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from config import DEFAULT_HEADERS

logger = logging.getLogger(__name__)

class JumiaScraper:
    BASE_URL = "https://www.jumia.co.ke"

    def __init__(self, timeout: int = 15, delay_range: tuple = (0.5, 1.5)):
        self.timeout = timeout
        self.delay_range = delay_range
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def _clean_price(self, text: Optional[str]) -> float:
        if not text:
            return 0.0
        cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
        try:
            return float(cleaned)
        except ValueError:
            return 0.0

    def _parse_rating_and_reviews(self, rev_el) -> tuple:
        """Parse rating and review count from review badge text e.g. '3.6 out of 5(9)'."""
        if not rev_el:
            return 0.0, 0
        text = rev_el.text.strip()
        rating = 0.0
        reviews = 0

        # Match rating e.g. 4.2 out of 5
        m_rate = re.search(r"(\d+(?:\.\d+)?)\s*out of", text, re.IGNORECASE)
        if m_rate:
            try:
                rating = float(m_rate.group(1))
            except ValueError:
                pass

        # Match review count in parentheses e.g. (52)
        m_rev = re.search(r"\((\d+)\)", text)
        if m_rev:
            try:
                reviews = int(m_rev.group(1))
            except ValueError:
                pass

        return rating, reviews

    def search_products(self, query: str, category_name: str = "General", max_pages: int = 2) -> List[Dict[str, Any]]:
        """
        Scrape search results from Jumia Kenya for a given query.
        Returns a list of structured product dictionaries.
        """
        products = []
        for page in range(1, max_pages + 1):
            url = f"{self.BASE_URL}/catalog/?q={requests.utils.quote(query)}&page={page}"
            try:
                # Random delay to simulate human browsing
                time.sleep(random.uniform(*self.delay_range))
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code != 200:
                    logger.warning(f"Jumia returned status {resp.status_code} for URL: {url}")
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                articles = soup.select("article.prd")
                if not articles:
                    logger.info(f"No more products found on page {page} for query '{query}'")
                    break

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
                    if href and not href.startswith("http"):
                        full_url = f"{self.BASE_URL}{href}"
                    else:
                        full_url = href

                    image_url = ""
                    if img_el:
                        image_url = img_el.get("data-src") or img_el.get("src") or ""

                    # Detect Jumia Express badge
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

                logger.info(f"Scraped {len(articles)} items from Jumia page {page} for '{query}'")

            except Exception as e:
                logger.error(f"Error scraping Jumia query '{query}' page {page}: {e}")
                break

        return products

if __name__ == "__main__":
    scraper = JumiaScraper()
    items = scraper.search_products("car vacuum cleaner", category_name="Auto Accessories", max_pages=1)
    print(f"Scraped {len(items)} items from Jumia:")
    for item in items[:3]:
        print(f"- {item['title'][:50]}... | KSh {item['price']} | Reviews: {item['reviews_count']} | Rating: {item['rating']}")
