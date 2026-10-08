"""
Command-line interface to execute JumiaDrop market scans.
Supports high-speed asynchronous mode and rotating proxies from 48 GitHub sources.
Usage:
    python run_scanner.py --keyword "dash cam" --category "Auto Accessories" --async
    python run_scanner.py --niche "Home & Kitchen" --async
    python run_scanner.py --refresh-proxies
"""
import argparse
import sys
import asyncio

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scanner import MarketScanner
from async_scanner import AsyncMarketScanner
from proxy_manager import global_proxy_manager
from database import get_database_stats, get_arbitrage_deals, init_db

def main():
    parser = argparse.ArgumentParser(description="JumiaDrop CLI Market Scanner")
    parser.add_argument("--keyword", type=str, help="Specific product keyword to search")
    parser.add_argument("--category", type=str, default="General", help="Product category")
    parser.add_argument("--niche", type=str, help="Run scan on a predefined starter niche")
    parser.add_argument("--all", action="store_true", help="Scan across all starter niches")
    parser.add_argument("--min-profit", type=float, default=500.0, help="Minimum net profit in KES")
    parser.add_argument("--min-margin", type=float, default=25.0, help="Minimum margin percentage")
    parser.add_argument("--min-confidence", type=float, default=60.0, help="Minimum matching confidence")
    parser.add_argument("--jumia-pages", type=int, default=1, help="Number of Jumia pages to scrape")
    parser.add_argument("--jiji-pages", type=int, default=1, help="Number of Jiji pages to scrape")
    parser.add_argument("--async", dest="use_async", action="store_true", default=True, help="Use high-speed async scraper (default: True)")
    parser.add_argument("--sync", dest="use_async", action="store_false", help="Use synchronous scraper")
    parser.add_argument("--use-proxies", action="store_true", help="Enable rotating proxy pool")
    parser.add_argument("--refresh-proxies", action="store_true", help="Fetch and validate fresh proxies from 48 sources")
    parser.add_argument("--proxy-status", action="store_true", help="Display proxy pool status")

    args = parser.parse_args()
    init_db()

    # Handle proxy management commands
    if args.proxy_status:
        st = global_proxy_manager.get_status()
        print("\n" + "="*50)
        print("🛡️ PROXY POOL STATUS:")
        print(f"• Active Working Proxies: {st['total_working']}")
        print(f"• Average Latency: {st['avg_latency_ms']} ms")
        print(f"• Fastest Proxy: {st['fastest_ms']} ms")
        print(f"• GitHub Sources Configured: {st['sources_count']}")
        print("="*50)
        return

    if args.refresh_proxies:
        print("\n⚡ Fetching and validating proxies from 48 GitHub sources...")
        def _prog(msg, pct):
            print(f"[{int(pct*100)}%] {msg}")
        count = asyncio.run(global_proxy_manager.refresh_pool(target_valid=20, on_progress=_prog))
        print(f"✅ Finished! {count} verified fast working proxies are ready in cache.")
        return

    # Scanner Execution
    if args.use_async:
        print(f"🚀 Running in HIGH-SPEED ASYNC mode (Proxies: {'ON' if args.use_proxies else 'OFF'})...")
        async_scanner = AsyncMarketScanner(
            min_profit=args.min_profit,
            min_margin=args.min_margin,
            min_confidence=args.min_confidence,
            use_proxies=args.use_proxies
        )

        async def _run_async():
            if args.keyword:
                print(f"\n🔍 Async scanning keyword: '{args.keyword}' (Category: {args.category})...")
                res = await async_scanner.scan_keyword(
                    keyword=args.keyword,
                    category_name=args.category,
                    jumia_pages=args.jumia_pages,
                    jiji_pages=args.jiji_pages
                )
                print(f"✅ Found {res['jumia_count']} Jumia listings, {res['jiji_count']} Jiji Nairobi ads.")
                print(f"🎯 Matched {res['deals_count']} products ({res['qualified_deals_count']} qualified with ≥ KES {args.min_profit} profit) in {res['duration_sec']}s.")
            elif args.niche:
                print(f"\n🚀 Async scanning starter niche: '{args.niche}'...")
                results = await async_scanner.scan_niche(args.niche, max_keywords=5)
                total_deals = sum(r['deals_count'] for r in results)
                print(f"✅ Completed niche '{args.niche}'. Total deals discovered: {total_deals}")
            elif args.all:
                print("\n🌐 Running async full sweep across all 5 starter dropshipping niches...")
                await async_scanner.scan_all_niches(max_keywords_per_niche=3)
                print("✅ Full catalog sweep complete!")
            else:
                print("Defaulting to high-demand test keyword: 'dash cam 1080p'")
                await async_scanner.scan_keyword("dash cam 1080p", category_name="Auto Accessories")

        asyncio.run(_run_async())

    else:
        # Synchronous fallback
        print("🐢 Running in standard synchronous mode...")
        scanner = MarketScanner(
            min_profit=args.min_profit,
            min_margin=args.min_margin,
            min_confidence=args.min_confidence
        )
        if args.keyword:
            res = scanner.scan_keyword(args.keyword, category_name=args.category, jumia_pages=args.jumia_pages, jiji_pages=args.jiji_pages)
        elif args.niche:
            scanner.scan_niche(args.niche)
        elif args.all:
            scanner.scan_all_niches()
        else:
            scanner.scan_keyword("dash cam 1080p", category_name="Auto Accessories")

    # Summary Report
    deals = get_arbitrage_deals(
        min_profit=args.min_profit,
        min_margin=args.min_margin,
        min_confidence=args.min_confidence,
        limit=10
    )

    stats = get_database_stats()
    print("\n" + "="*70)
    print("📊 DATABASE SUMMARY:")
    print(f"• Total Jumia Products Indexed: {stats['jumia_products']}")
    print(f"• Total Jiji Nairobi Ads Indexed: {stats['jiji_adverts']}")
    print(f"• Total Arbitrage Deals: {stats['total_deals']}")
    print(f"• Average Net Profit: KES {stats['avg_profit_kes']} ({stats['avg_margin_pct']}%)")
    print(f"• Highest Single Profit Found: KES {stats['max_profit_kes']}")
    print("="*70)

    if not deals.empty:
        print(f"\n🏆 TOP DISCOVERED ARBITRAGE OPPORTUNITIES ({len(deals)} items):")
        for i, (_, row) in enumerate(deals.head(5).iterrows(), 1):
            print(f"\n[{i}] {row['jumia_title'][:60]}")
            print(f"    🛒 Jumia Price: KSh {row['jumia_price']:,.0f} | Reviews: {row['jumia_reviews']} | Rating: {row['jumia_rating']}")
            print(f"    🏭 Jiji Supplier: KSh {row['jiji_price']:,.0f} ({row['jiji_region']})")
            print(f"    💰 Net Profit: KSh {row['net_profit']:,.0f} ({row['margin_pct']:.1f}% margin) | Opp Score: {row['opportunity_score']}/100")
            print(f"    🔗 Jumia: {row['jumia_url']}")
            print(f"    🔗 Jiji:  {row['jiji_url']}")

if __name__ == "__main__":
    main()
