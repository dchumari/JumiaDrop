"""
Master Marketplace Crawler for JumiaDrop.
Crawls the entire Jumia Kenya catalog and Jiji Kenya Nairobi wholesale listings
across all major categories up to 50 pages deep, building a local database of tens of thousands of products.

Usage:
    python crawl_all.py --pages 5                  # Quick mass crawl (approx 2,000-4,000 products)
    python crawl_all.py --pages 20                 # Deep mass crawl (approx 10,000-15,000 products)
    python crawl_all.py --pages 50 --use-proxies   # Full catalog harvest (20,000+ products)
    python crawl_all.py --category "Automobile" --pages 10
"""
import sys
import time
import argparse
import asyncio
import logging
from typing import List, Dict, Any, Optional
import pandas as pd

# Ensure UTF-8 console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from template_loader import global_template_loader
from bulk_harvester import BulkCatalogHarvester
from scrapers.async_jiji_scraper import AsyncJijiScraper
from scrapers.async_jumia_scraper import AsyncJumiaScraper
from engine.calculator import ProfitCalculator
from engine.matcher import ProductMatcher
from proxy_manager import global_proxy_manager
from database import (
    init_db,
    save_jumia_product,
    save_jiji_advert,
    save_arbitrage_deal,
    get_database_stats,
    log_scan_event,
    get_connection
)

logger = logging.getLogger(__name__)

# Primary Dropshipping Category Mappings between Jumia and Jiji
CATEGORY_MAPPINGS = [
    {
        "name": "Automobile",
        "jumia_slug": "automobile",
        "jiji_slug": "vehicle-parts-accessories",
        "commission": 0.12
    },
    {
        "name": "Home & Office",
        "jumia_slug": "home-office",
        "jiji_slug": "home-appliances",
        "commission": 0.14
    },
    {
        "name": "Electronics",
        "jumia_slug": "electronics",
        "jiji_slug": "electronics",
        "commission": 0.09
    },
    {
        "name": "Phones & Tablets",
        "jumia_slug": "phones-tablets",
        "jiji_slug": "mobile-phones-tablets",
        "commission": 0.08
    },
    {
        "name": "Health & Beauty",
        "jumia_slug": "health-beauty",
        "jiji_slug": "beauty-and-personal-care",
        "commission": 0.15
    },
    {
        "name": "Industrial & Scientific",
        "jumia_slug": "industrial-scientific",
        "jiji_slug": "office-and-commercial-equipment-tools",
        "commission": 0.12
    },
    {
        "name": "Baby Products",
        "jumia_slug": "baby-products",
        "jiji_slug": "babies-and-kids",
        "commission": 0.12
    },
    {
        "name": "Computing",
        "jumia_slug": "computing",
        "jiji_slug": "computers-and-laptops",
        "commission": 0.09
    },
    {
        "name": "Sporting Goods",
        "jumia_slug": "sporting-goods",
        "jiji_slug": "sports-fitness",
        "commission": 0.12
    },
    {
        "name": "Fashion",
        "jumia_slug": "fashion",
        "jiji_slug": "fashion",
        "commission": 0.16
    }
]

class MasterMarketplaceCrawler:
    def __init__(self, use_proxies: bool = False, max_concurrent: int = 5):
        self.use_proxies = use_proxies
        self.max_concurrent = max_concurrent
        self.jumia_harvester = BulkCatalogHarvester()
        self.jiji_scraper = AsyncJijiScraper()
        self.calculator = ProfitCalculator()
        self.matcher = ProductMatcher(min_confidence=60.0)

    async def crawl_jiji_category(
        self,
        category_name: str,
        jiji_slug: str,
        max_pages: int = 10,
        on_progress = None
    ) -> int:
        """Crawl wholesale ads from Jiji Nairobi for a specific category."""
        saved_count = 0
        for page in range(1, max_pages + 1):
            if on_progress:
                on_progress(f"Jiji Nairobi [{category_name}] page {page}/{max_pages}...", page / max_pages)
            # Fetch with category_slug parameter
            params = {
                "category_slug": jiji_slug,
                "region_slug": "nairobi",
                "page": page
            }
            # Use scraper session with category_slug
            try:
                import requests
                from config import JIJI_API_HEADERS
                proxy_url = global_proxy_manager.get_proxy() if self.use_proxies else None
                proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
                resp = requests.get(
                    "https://jiji.co.ke/api_web/v1/listing",
                    params=params,
                    headers=JIJI_API_HEADERS,
                    proxies=proxies,
                    timeout=12
                )
                if resp.status_code == 200:
                    raw_items = resp.json().get("adverts_list", {}).get("adverts", [])
                    if not raw_items:
                        break
                    for item in raw_items:
                        title = item.get("title", "").strip()
                        if not title:
                            continue
                        price_obj = item.get("price_obj") or {}
                        val = price_obj.get("value")
                        if val is None or float(val) <= 0:
                            continue

                        rel_url = item.get("url", "")
                        full_url = f"https://jiji.co.ke{rel_url}" if rel_url.startswith("/") else rel_url

                        image_url = ""
                        image_obj = item.get("image_obj")
                        if isinstance(image_obj, dict):
                            image_url = image_obj.get("url", "")
                        elif item.get("images") and len(item["images"]) > 0:
                            image_url = item["images"][0].get("url", "")

                        record = {
                            "id": item.get("id"),
                            "title": title,
                            "category": category_name,
                            "price": float(val),
                            "region_name": item.get("region_name", "Nairobi"),
                            "location_text": item.get("region_item_text", ""),
                            "short_description": item.get("short_description", ""),
                            "url": full_url,
                            "image_url": image_url,
                            "user_id": str(item.get("user_id") or ""),
                            "user_phone": item.get("user_phone")
                        }
                        save_jiji_advert(record)
                        saved_count += 1
            except Exception as e:
                logger.debug(f"Error crawling Jiji page {page} ({jiji_slug}): {e}")

            await asyncio.sleep(0.4)

        return saved_count

    async def match_existing_catalog(self, category_name: str, on_progress = None) -> int:
        """
        Run in-memory matching between unindexed Jumia products and Jiji ads for a category.
        """
        conn = get_connection()
        jumia_df = pd.read_sql_query(
            "SELECT * FROM jumia_products WHERE category = ? ORDER BY id DESC LIMIT 500",
            conn,
            params=[category_name]
        )
        jiji_df = pd.read_sql_query(
            "SELECT * FROM jiji_adverts WHERE category = ? ORDER BY id DESC LIMIT 500",
            conn,
            params=[category_name]
        )
        conn.close()

        if jumia_df.empty or jiji_df.empty:
            return 0

        deals_matched = 0
        total = len(jumia_df)

        for idx, (_, jm) in enumerate(jumia_df.iterrows(), 1):
            if on_progress and idx % 20 == 0:
                on_progress(f"Matching deals in [{category_name}] ({idx}/{total})...", idx / total)

            best_deal = None
            best_conf = 0.0

            for _, jj in jiji_df.iterrows():
                conf, _ = self.matcher.compute_match_confidence(
                    jumia_title=jm["title"],
                    jiji_title=jj["title"],
                    jiji_description=jj.get("short_description") or "",
                    jumia_price=jm["price"],
                    jiji_price=jj["price"]
                )

                if conf >= 55.0 and conf > best_conf:
                    fin = self.calculator.calculate_deal_finances(
                        jumia_price=jm["price"],
                        jiji_price=jj["price"],
                        category=category_name
                    )
                    comp_score = self.calculator.compute_competition_score(
                        reviews_count=jm.get("reviews_count", 0),
                        rating=jm.get("rating", 0.0),
                        is_express=bool(jm.get("is_express"))
                    )
                    opp_score = self.calculator.compute_opportunity_score(
                        net_profit=fin["net_profit"],
                        margin_pct=fin["margin_pct"],
                        competition_score=comp_score,
                        confidence_score=conf
                    )

                    best_conf = conf
                    best_deal = {
                        "jumia_id": jm["id"],
                        "jiji_id": jj["id"],
                        "confidence_score": conf,
                        "category": category_name,
                        "jumia_price": jm["price"],
                        "jiji_price": jj["price"],
                        "jumia_commission": fin["jumia_commission"],
                        "vat_amount": fin["vat_amount"],
                        "packaging_cost": fin["packaging_cost"],
                        "boda_cost": fin["boda_cost"],
                        "total_cost": fin["total_cost"],
                        "net_profit": fin["net_profit"],
                        "margin_pct": fin["margin_pct"],
                        "competition_score": comp_score,
                        "opportunity_score": opp_score,
                        "status": "active"
                    }

            if best_deal:
                save_arbitrage_deal(best_deal)
                deals_matched += 1

        return deals_matched

    async def crawl_all_categories(
        self,
        pages_per_category: int = 5,
        target_categories: Optional[List[str]] = None,
        on_progress = None
    ) -> Dict[str, Any]:
        """
        Execute deep mass crawl across all primary categories on both Jumia and Jiji.
        """
        start_time = time.time()
        init_db()

        cats_to_crawl = CATEGORY_MAPPINGS
        if target_categories:
            cats_to_crawl = [c for c in CATEGORY_MAPPINGS if c["name"] in target_categories]

        total_cats = len(cats_to_crawl)
        summary = {
            "categories_crawled": 0,
            "total_jumia_saved": 0,
            "total_jiji_saved": 0,
            "total_deals_matched": 0,
            "duration_seconds": 0
        }

        for idx, cat in enumerate(cats_to_crawl, 1):
            c_name = cat["name"]
            j_slug = cat["jumia_slug"]
            ji_slug = cat["jiji_slug"]

            cat_progress_base = (idx - 1) / total_cats
            if on_progress:
                on_progress(f"▶️ [{idx}/{total_cats}] Crawling Category: {c_name} (up to {pages_per_category} pages)...", cat_progress_base)

            # 1. Crawl Jumia Category
            j_res = await self.jumia_harvester.harvest_category(
                category_name=c_name,
                start_page=1,
                max_pages=pages_per_category,
                use_proxies=self.use_proxies
            )
            jumia_saved = j_res["items_saved"]

            # 2. Crawl Jiji Nairobi Category
            jiji_saved = await self.crawl_jiji_category(
                category_name=c_name,
                jiji_slug=ji_slug,
                max_pages=pages_per_category
            )

            # 3. Match Products
            deals_matched = await self.match_existing_catalog(category_name=c_name)

            summary["categories_crawled"] += 1
            summary["total_jumia_saved"] += jumia_saved
            summary["total_jiji_saved"] += jiji_saved
            summary["total_deals_matched"] += deals_matched

            logger.info(f"Category {c_name} completed: +{jumia_saved} Jumia, +{jiji_saved} Jiji, +{deals_matched} deals.")

        summary["duration_seconds"] = round(time.time() - start_time, 2)
        if on_progress:
            on_progress(f"🎉 Mass Crawl Complete! Indexed {summary['total_jumia_saved']} Jumia items, {summary['total_jiji_saved']} Jiji ads, and matched {summary['total_deals_matched']} deals in {summary['duration_seconds']}s.", 1.0)

        return summary

def main():
    parser = argparse.ArgumentParser(description="JumiaDrop Master Marketplace Crawler")
    parser.add_argument("--pages", type=int, default=5, help="Number of pages to crawl per category (1-50, default: 5)")
    parser.add_argument("--category", type=str, help="Specific category to crawl (e.g. Automobile, Electronics, Home & Office)")
    parser.add_argument("--use-proxies", action="store_true", help="Enable 48-source rotating proxy pool")

    args = parser.parse_args()

    crawler = MasterMarketplaceCrawler(use_proxies=args.use_proxies)
    target_cats = [args.category] if args.category else None

    print("\n" + "="*70)
    print("🌐 JUMIADROP: MASTER MARKETPLACE CRAWLER")
    print(f"• Target Depth: {args.pages} pages per category")
    print(f"• Categories: {args.category or 'ALL 10 Major Categories'}")
    print(f"• Rotating Proxies: {'ON' if args.use_proxies else 'OFF'}")
    print("="*70 + "\n")

    def _cli_prog(msg, pct):
        print(f"[{int(pct*100):3d}%] {msg}")

    res = asyncio.run(crawler.crawl_all_categories(
        pages_per_category=args.pages,
        target_categories=target_cats,
        on_progress=_cli_prog
    ))

    stats = get_database_stats()
    print("\n" + "="*70)
    print("🏆 FINAL DATABASE TOTALS:")
    print(f"• Total Jumia Products in DB: {stats['jumia_products']:,}")
    print(f"• Total Jiji Nairobi Ads in DB: {stats['jiji_adverts']:,}")
    print(f"• Total Arbitrage Deals in DB: {stats['total_deals']:,}")
    print(f"• Average Net Profit: KES {stats['avg_profit_kes']:,.0f} ({stats['avg_margin_pct']:.1f}% margin)")
    print(f"• Execution Time: {res['duration_seconds']} seconds")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
