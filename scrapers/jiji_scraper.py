"""
Jiji Kenya Scraper.
Uses Jiji's high-speed JSON API to fetch Nairobi wholesale listings, prices, locations, and descriptions.
"""
import time
import random
import logging
from typing import List, Dict, Any, Optional
import requests
from config import JIJI_API_HEADERS, NAIROBI_ACCEPTED_REGIONS

logger = logging.getLogger(__name__)

class JijiScraper:
    API_URL = "https://jiji.co.ke/api_web/v1/listing"
    BASE_URL = "https://jiji.co.ke"

    def __init__(self, timeout: int = 15, delay_range: tuple = (0.5, 1.2)):
        self.timeout = timeout
        self.delay_range = delay_range
        self.session = requests.Session()
        self.session.headers.update(JIJI_API_HEADERS)

    def _is_nairobi_location(self, region_name: str, location_text: str) -> bool:
        """Verify that the seller is located within Nairobi wholesale or accessible areas."""
        combined = f"{region_name} {location_text}".lower()
        return any(nairobi_kw in combined for nairobi_kw in NAIROBI_ACCEPTED_REGIONS)

    def search_adverts(
        self,
        query: str,
        category_name: str = "General",
        max_pages: int = 2,
        strict_nairobi: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Search Jiji Kenya adverts via API.
        Returns a list of structured advert records.
        """
        adverts = []
        for page in range(1, max_pages + 1):
            params = {
                "query": query,
                "region_slug": "nairobi",
                "page": page
            }
            try:
                time.sleep(random.uniform(*self.delay_range))
                resp = self.session.get(self.API_URL, params=params, timeout=self.timeout)
                if resp.status_code != 200:
                    logger.warning(f"Jiji returned status {resp.status_code} for query '{query}'")
                    break

                data = resp.json()
                raw_items = data.get("adverts_list", {}).get("adverts", [])
                if not raw_items:
                    break

                for item in raw_items:
                    title = item.get("title", "").strip()
                    if not title:
                        continue

                    # Extract price
                    price_obj = item.get("price_obj") or {}
                    price_val = price_obj.get("value")
                    if price_val is None:
                        # Fallback to parsing price_title e.g. "KSh 2,500"
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

                    # Construct full advert URL
                    rel_url = item.get("url", "")
                    full_url = f"{self.BASE_URL}{rel_url}" if rel_url.startswith("/") else rel_url

                    # Image URL extraction
                    image_url = ""
                    image_obj = item.get("image_obj")
                    if isinstance(image_obj, dict):
                        image_url = image_obj.get("url", "")
                    elif item.get("images") and len(item["images"]) > 0:
                        image_url = item["images"][0].get("url", "")

                    short_desc = item.get("short_description", "")
                    user_id = str(item.get("user_id") or "")
                    user_phone = item.get("user_phone")

                    adverts.append({
                        "id": item.get("id"),
                        "title": title,
                        "category": category_name,
                        "price": price_val,
                        "region_name": region_name,
                        "location_text": location_text,
                        "short_description": short_desc,
                        "url": full_url,
                        "image_url": image_url,
                        "user_id": user_id,
                        "user_phone": user_phone
                    })

                logger.info(f"Found {len(raw_items)} raw ads ({len(adverts)} qualified Nairobi) on Jiji page {page} for '{query}'")

            except Exception as e:
                logger.error(f"Error fetching Jiji query '{query}' page {page}: {e}")
                break

        return adverts

if __name__ == "__main__":
    scraper = JijiScraper()
    ads = scraper.search_adverts("car vacuum cleaner cordless", category_name="Auto Accessories", max_pages=1)
    print(f"Scraped {len(ads)} Nairobi ads from Jiji:")
    for ad in ads[:3]:
        print(f"- {ad['title'][:50]}... | KSh {ad['price']} | {ad['region_name']} | {ad['location_text']}")
