"""
Asynchronous Proxy Manager for JumiaDrop.
Fetches, parses, tests, and rotates proxies from 48+ curated public sources.
Supports HTTP, HTTPS, SOCKS4, and SOCKS5.
"""
import os
import re
import json
import time
import random
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import aiohttp
from aiohttp_socks import ProxyConnector

logger = logging.getLogger(__name__)

PROXY_SOURCES = [
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/refs/heads/main/http.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/refs/heads/main/socks4.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/Proxy/refs/heads/main/socks5.txt",
    "https://raw.githubusercontent.com/Argh94/Proxy-List/refs/heads/main/HTTP.txt",
    "https://raw.githubusercontent.com/Argh94/Proxy-List/refs/heads/main/Hysteria2.txt",
    "https://raw.githubusercontent.com/Argh94/Proxy-List/refs/heads/main/SOCKS4.txt",
    "https://raw.githubusercontent.com/Argh94/Proxy-List/refs/heads/main/SOCKS5.txt",
    "https://raw.githubusercontent.com/Argh94/Proxy-List/refs/heads/main/ShadowSocks.txt",
    "https://raw.githubusercontent.com/Argh94/Proxy-List/refs/heads/main/Trojan.txt",
    "https://raw.githubusercontent.com/Argh94/Proxy-List/refs/heads/main/Tuic.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/refs/heads/main/proxies/http.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/refs/heads/main/proxies/https.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/refs/heads/main/proxies/socks4.txt",
    "https://raw.githubusercontent.com/ErcinDedeoglu/proxies/refs/heads/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/SevenworksDev/proxy-list/refs/heads/main/proxies/http.txt",
    "https://raw.githubusercontent.com/SevenworksDev/proxy-list/refs/heads/main/proxies/https.txt",
    "https://raw.githubusercontent.com/SevenworksDev/proxy-list/refs/heads/main/proxies/socks4.txt",
    "https://raw.githubusercontent.com/SevenworksDev/proxy-list/refs/heads/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/refs/heads/master/http.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/refs/heads/master/socks4.txt",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/refs/heads/master/socks5.txt",
    "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/refs/heads/main/all_elite.txt",
    "https://raw.githubusercontent.com/VPSLabCloud/VPSLab-Free-Proxy-List/refs/heads/main/all_proxies.txt",
    "https://raw.githubusercontent.com/Vann-Dev/proxy-list/refs/heads/main/proxies/http.txt",
    "https://raw.githubusercontent.com/Vann-Dev/proxy-list/refs/heads/main/proxies/https.txt",
    "https://raw.githubusercontent.com/Vann-Dev/proxy-list/refs/heads/main/proxies/socks4.txt",
    "https://raw.githubusercontent.com/Vann-Dev/proxy-list/refs/heads/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/refs/heads/master/http.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/refs/heads/master/https.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/refs/heads/master/socks4.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/refs/heads/master/socks5.txt",
    "https://raw.githubusercontent.com/elliottophellia/proxylist/refs/heads/master/results/pmix_checked.txt",
    "https://raw.githubusercontent.com/gitrecon1455/fresh-proxy-list/refs/heads/main/proxylist.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/main/socks5.txt",
    "https://raw.githubusercontent.com/iplocate/free-proxy-list/refs/heads/main/all-proxies.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/refs/heads/main/proxies/all.txt",
    "https://raw.githubusercontent.com/mzyui/proxy-list/refs/heads/main/all.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/refs/heads/main/proxies/all/data.txt",
    "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Https.txt",
    "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Socks4.txt",
    "https://raw.githubusercontent.com/r00tee/Proxy-List/main/Socks5.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/refs/heads/main/HTTPS_RAW.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/refs/heads/main/SOCKS4_RAW.txt",
    "https://raw.githubusercontent.com/roosterkid/openproxylist/refs/heads/main/SOCKS5_RAW.txt",
    "https://raw.githubusercontent.com/sunny9577/proxy-scraper/refs/heads/master/proxies.txt",
    "https://raw.githubusercontent.com/themiralay/Proxy-List-World/refs/heads/master/data.txt",
    "https://raw.githubusercontent.com/zloi-user/hideip.me/refs/heads/main/http.txt",
    "https://raw.githubusercontent.com/zloi-user/hideip.me/refs/heads/main/socks4.txt"
]

CACHE_FILE = Path(__file__).resolve().parent / "working_proxies.json"

class ProxyManager:
    def __init__(self, cache_file: Path = CACHE_FILE):
        self.cache_file = cache_file
        self.working_proxies: List[Dict[str, Any]] = []
        self.failed_counts: Dict[str, int] = {}
        self._current_index = 0
        self.load_cached_proxies()

    def load_cached_proxies(self) -> int:
        """Load previously verified proxies from local cache."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.working_proxies = data.get("proxies", [])
                    logger.info(f"Loaded {len(self.working_proxies)} cached working proxies.")
                    return len(self.working_proxies)
            except Exception as e:
                logger.warning(f"Failed to read proxy cache: {e}")
        return 0

    def save_cached_proxies(self):
        """Save verified working proxies to local cache."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump({
                    "updated_at": time.time(),
                    "count": len(self.working_proxies),
                    "proxies": self.working_proxies
                }, f, indent=2)
            logger.info(f"Saved {len(self.working_proxies)} working proxies to {self.cache_file}")
        except Exception as e:
            logger.error(f"Failed to save proxy cache: {e}")

    async def fetch_source(self, session: aiohttp.ClientSession, url: str) -> List[str]:
        """Fetch raw proxy text from a single source."""
        proxies = []
        # Determine protocol hint from source URL
        url_lower = url.lower()
        proto_hint = "http"
        if "socks5" in url_lower:
            proto_hint = "socks5"
        elif "socks4" in url_lower:
            proto_hint = "socks4"
        elif "https" in url_lower:
            proto_hint = "http"

        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    text = await resp.text(errors="ignore")
                    for line in text.splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        
                        # Match ip:port pattern
                        m = re.search(r"(?:(https?|socks4|socks5)://)?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{2,5})", line)
                        if m:
                            proto = m.group(1) or proto_hint
                            ip_port = m.group(2)
                            proxies.append(f"{proto}://{ip_port}")
        except Exception as e:
            logger.debug(f"Source fetch failed ({url[:40]}...): {e}")
        return proxies

    async def fetch_all_sources(self, max_concurrent: int = 20) -> List[str]:
        """Concurrently fetch proxies from all 48 source lists."""
        logger.info(f"Fetching raw proxies from {len(PROXY_SOURCES)} sources...")
        conn = aiohttp.TCPConnector(limit=max_concurrent, ssl=False)
        async with aiohttp.ClientSession(connector=conn) as session:
            tasks = [self.fetch_source(session, url) for url in PROXY_SOURCES]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_proxies: Set[str] = set()
        for res in results:
            if isinstance(res, list):
                all_proxies.update(res)

        logger.info(f"Collected {len(all_proxies)} unique raw proxy candidates.")
        return list(all_proxies)

    async def validate_proxy(self, proxy_url: str, test_url: str = "http://httpbin.org/ip", timeout: float = 4.0) -> Optional[Dict[str, Any]]:
        """Test whether a proxy is alive and measure its response latency."""
        start = time.time()
        try:
            connector = ProxyConnector.from_url(proxy_url, ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(test_url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    if resp.status == 200:
                        latency = round((time.time() - start) * 1000, 1)
                        return {
                            "proxy": proxy_url,
                            "latency_ms": latency,
                            "last_checked": time.time()
                        }
        except Exception:
            pass
        return None

    async def refresh_pool(self, target_valid: int = 50, batch_size: int = 150, max_workers: int = 60, on_progress = None) -> int:
        """
        Fetch new proxies and validate until we have enough fast working proxies.
        """
        if on_progress:
            on_progress("Downloading proxies from 48 GitHub sources...", 0.1)

        raw_list = await self.fetch_all_sources()
        if not raw_list:
            logger.warning("No proxies fetched from sources.")
            return len(self.working_proxies)

        # Shuffle candidates so we test varied sources
        random.shuffle(raw_list)

        if on_progress:
            on_progress(f"Validating candidates with {max_workers} concurrent test workers...", 0.3)

        tested = 0
        valid: List[Dict[str, Any]] = []
        sem = asyncio.Semaphore(max_workers)

        async def _test(p):
            nonlocal tested
            async with sem:
                res = await self.validate_proxy(p)
                tested += 1
                if res:
                    valid.append(res)
                return res

        # Process in batches to stop early once target_valid is reached
        for i in range(0, min(len(raw_list), 600), batch_size):
            batch = raw_list[i : i + batch_size]
            await asyncio.gather(*[_test(p) for p in batch], return_exceptions=True)
            if on_progress:
                pct = min(0.9, 0.3 + (tested / 600) * 0.6)
                on_progress(f"Tested {tested} proxies -> {len(valid)} working...", pct)
            if len(valid) >= target_valid:
                break

        # Sort valid proxies by lowest latency
        valid.sort(key=lambda x: x["latency_ms"])
        self.working_proxies = valid
        self.save_cached_proxies()

        if on_progress:
            on_progress(f"Proxy pool refreshed: {len(valid)} fast working proxies ready!", 1.0)

        logger.info(f"Proxy validation finished. {len(valid)} working proxies ready.")
        return len(valid)

    def get_proxy(self) -> Optional[str]:
        """Get the next working proxy via round-robin."""
        if not self.working_proxies:
            return None
        self._current_index = (self._current_index + 1) % len(self.working_proxies)
        return self.working_proxies[self._current_index]["proxy"]

    def report_failure(self, proxy_url: str):
        """Track failures and eject non-functional proxies."""
        self.failed_counts[proxy_url] = self.failed_counts.get(proxy_url, 0) + 1
        if self.failed_counts[proxy_url] >= 2:
            self.working_proxies = [p for p in self.working_proxies if p["proxy"] != proxy_url]
            logger.debug(f"Removed unreliable proxy: {proxy_url}")

    def get_status(self) -> Dict[str, Any]:
        """Get summary stats of active proxy pool."""
        count = len(self.working_proxies)
        avg_latency = round(sum(p["latency_ms"] for p in self.working_proxies) / count, 1) if count > 0 else 0
        return {
            "total_working": count,
            "avg_latency_ms": avg_latency,
            "fastest_ms": self.working_proxies[0]["latency_ms"] if count > 0 else 0,
            "sources_count": len(PROXY_SOURCES)
        }

# Global singleton proxy manager
global_proxy_manager = ProxyManager()

if __name__ == "__main__":
    pm = ProxyManager()
    print("Testing proxy refresh pipeline (finding 10 fast proxies)...")
    count = asyncio.run(pm.refresh_pool(target_valid=10, max_workers=50))
    print(f"Result: {count} verified proxies.")
    if pm.working_proxies:
        for p in pm.working_proxies[:5]:
            print(f"  {p['proxy']} - {p['latency_ms']}ms")
