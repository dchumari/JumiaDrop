"""
JumiaDrop - Jiji to Jumia Dropshipping Arbitrage Dashboard.
Interactive Streamlit application featuring:
- Specification Clustering with Compact Layout and Image Thumbnails
- Abundance-to-Scarcity Market Distribution Insights
- 💎 Blue Ocean Reverse Sourcing (Products on Jiji but Unlisted on Jumia)
- 📦 Deep Catalog Bulk Harvester (Crawling up to 50 pages from Official Template Categories)
- 🛡️ 48-Source Rotating Proxy Pool & High-Speed Asynchronous Crawling
"""
import streamlit as st
import pandas as pd
import io
import asyncio
from datetime import datetime
import database
from database import (
    init_db,
    get_arbitrage_deals,
    get_database_stats,
    update_deal_status,
    get_connection
)

# Resilient import fallback
if hasattr(database, "get_distinct_categories"):
    get_distinct_categories = database.get_distinct_categories
else:
    def get_distinct_categories():
        return []

from template_loader import global_template_loader
from async_scanner import AsyncMarketScanner
from scanner import MarketScanner
from bulk_harvester import BulkCatalogHarvester
from engine.reverse_sourcing import ReverseSourcingEngine, get_blue_ocean_deals
from proxy_manager import global_proxy_manager, PROXY_SOURCES
from engine.clustering import ProductClusterEngine
from notifier import TelegramNotifier
from scheduler import ScanScheduler
from config import (
    STARTER_NICHES,
    DEFAULT_CATEGORY_COMMISSIONS,
    DEFAULT_MIN_NET_PROFIT_KES,
    DEFAULT_MIN_MARGIN_PCT,
    DEFAULT_PACKAGING_COST_KES,
    DEFAULT_BODA_RUNNER_COST_KES
)

# Page Configuration
st.set_page_config(
    page_title="JumiaDrop | Jiji-to-Jumia Dropshipping Engine",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FF9900, #00A86B);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .cluster-card {
        background-color: #161B22;
        border-radius: 12px;
        border: 1px solid #30363D;
        padding: 14px 18px;
        margin-bottom: 14px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    .deal-card {
        background-color: #161B22;
        border-radius: 12px;
        border: 1px solid #30363D;
        padding: 16px;
        margin-bottom: 16px;
    }
    .profit-badge {
        background: linear-gradient(135deg, #10B981, #059669);
        color: white;
        padding: 4px 12px;
        border-radius: 18px;
        font-weight: bold;
        font-size: 1rem;
        display: inline-block;
    }
    .scarcity-pill {
        padding: 4px 10px;
        border-radius: 14px;
        font-weight: 700;
        font-size: 0.8rem;
        display: inline-block;
    }
    .blue-ocean-badge {
        background: linear-gradient(135deg, #3B82F6, #1D4ED8);
        color: white;
        padding: 4px 12px;
        border-radius: 14px;
        font-weight: 700;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize database
init_db()

# Categories extracted from the user's 21 Excel templates
template_categories = global_template_loader.get_primary_categories()
if not template_categories:
    template_categories = list(STARTER_NICHES.keys())

all_categories = ["All"] + template_categories

# Sidebar: Global Filters
st.sidebar.title("🎯 Arbitrage Filters")
st.sidebar.caption("Filter discovered items from local database")

selected_category = st.sidebar.selectbox("📂 Template Category", all_categories, index=0)

min_profit_filter = st.sidebar.slider(
    "💰 Min Net Profit (KES)",
    min_value=0,
    max_value=5000,
    value=int(DEFAULT_MIN_NET_PROFIT_KES),
    step=100
)

min_margin_filter = st.sidebar.slider(
    "📈 Min Profit Margin (%)",
    min_value=5,
    max_value=75,
    value=int(DEFAULT_MIN_MARGIN_PCT),
    step=5
)

competition_filter = st.sidebar.selectbox(
    "🏆 Jumia Competition Level",
    ["All Levels", "🔥 Low (< 15 reviews)", "⚖️ Moderate (< 35 reviews)", "Uncontested (0 reviews)"]
)

min_confidence_filter = st.sidebar.slider(
    "🔍 Min Match Confidence (%)",
    min_value=40,
    max_value=95,
    value=55,
    step=5
)

search_keyword = st.sidebar.text_input("🔎 Search in Titles", "")

only_scarcity = st.sidebar.checkbox(
    "🔥 Only: Abundant on Jiji, Scarce on Jumia",
    value=False,
    help="Filters for products with high wholesale supply in Nairobi but very few competing sellers on Jumia"
)

st.sidebar.divider()
st.sidebar.markdown("### ⚡ Engine Settings")
use_proxies_toggle = st.sidebar.checkbox("🛡️ Use Rotating Proxies", value=False, help="Rotate requests across validated proxies from 48 GitHub sources")
use_async_toggle = st.sidebar.checkbox("🚀 High-Speed Async Engine", value=True, help="Concurrently crawl in parallel")

# Compute max_reviews
max_revs = None
if competition_filter == "Uncontested (0 reviews)":
    max_revs = 0
elif competition_filter == "🔥 Low (< 15 reviews)":
    max_revs = 15
elif competition_filter == "⚖️ Moderate (< 35 reviews)":
    max_revs = 35

# Header
col_header, col_refresh = st.columns([5, 1])
with col_header:
    st.markdown("<div class='main-header'>🛍️ JumiaDrop Engine</div>", unsafe_allow_html=True)
    st.caption("Jiji Kenya ➔ Jumia Kenya Dropshipping Arbitrage & Reverse Sourcing Suite")
with col_refresh:
    if st.button("🔄 Refresh Data", width='stretch'):
        st.rerun()

# Top Metrics Row
stats = get_database_stats()
proxy_stats = global_proxy_manager.get_status()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("📦 Indexed Jumia Products", f"{stats['jumia_products']:,}")
m2.metric("🏭 Jiji Wholesale Ads", f"{stats['jiji_adverts']:,}")
m3.metric("🎯 Arbitrage Deals", f"{stats['total_deals']:,}")
m4.metric("💰 Avg Net Profit", f"KES {stats['avg_profit_kes']:,.0f}")
m5.metric("🛡️ Verified Proxies", f"{proxy_stats['total_working']} online")

st.divider()

# Navigation Tabs
tab_explore, tab_blue_ocean, tab_scanner, tab_proxies, tab_settings, tab_export = st.tabs([
    "💎 Arbitrage Opportunities",
    "🌊 Blue Ocean (Unlisted on Jumia)",
    "🚀 Live & Bulk Harvester",
    "🛡️ Proxy Pool & Network",
    "⚙️ Settings & Fees",
    "📥 Export Center"
])

# -------------------------------------------------------------
# TAB 1: ARBITRAGE OPPORTUNITIES & CLUSTER MARKET INSIGHTS
# -------------------------------------------------------------
with tab_explore:
    deals_df = get_arbitrage_deals(
        category=selected_category,
        min_profit=float(min_profit_filter),
        min_margin=float(min_margin_filter),
        max_reviews=max_revs,
        min_confidence=float(min_confidence_filter),
        status="All",
        limit=200
    )

    if search_keyword and not deals_df.empty:
        deals_df = deals_df[
            deals_df["jumia_title"].str.contains(search_keyword, case=False, na=False) |
            deals_df["jiji_title"].str.contains(search_keyword, case=False, na=False)
        ]

    cluster_engine = ProductClusterEngine()
    clusters = cluster_engine.analyze_clusters(deals_df)

    if only_scarcity and clusters:
        clusters = [c for c in clusters if c["scarcity_status"] in ("high_scarcity_opportunity", "favorable_supply")]

    st.subheader(f"Discovered Arbitrage ({len(clusters)} Product Families | {len(deals_df)} Direct Matches)")

    if not clusters and deals_df.empty:
        st.info("💡 No deals match your exact filter criteria. Run a bulk harvest in the 'Live & Bulk Harvester' tab to index thousands of products!")
    else:
        view_mode = st.radio(
            "Display Layout:",
            ["📦 Compact Specification Clusters (with Images)", "🎴 Side-by-Side Deal Cards", "📊 Data Table"],
            horizontal=True
        )

        # ---------------------------------------------------------
        # VIEW 1: COMPACT CLUSTERS WITH THUMBNAIL IMAGES
        # ---------------------------------------------------------
        if view_mode == "📦 Compact Specification Clusters (with Images)":
            st.caption("Minimized, image-rich product family cards showing Min, Median, Average, and Max price spreads.")

            for cluster in clusters:
                with st.container():
                    st.markdown("<div class='cluster-card'>", unsafe_allow_html=True)

                    # Main Card Header with Image and Key Details
                    c_img_col, c_info_col, c_price_col, c_action_col = st.columns([1, 4, 3, 2])

                    with c_img_col:
                        img_url = cluster.get("sample_image")
                        if img_url and str(img_url).startswith("http"):
                            st.image(img_url, width=90)
                        else:
                            st.write("📦 No image")

                    with c_info_col:
                        st.markdown(f"**{cluster['title'][:65]}...**")
                        st.caption(f"Category: `{cluster['category']}` | Sellers: **{cluster['jumia_sellers_count']} Jumia** vs **{cluster['jiji_suppliers_count']} Jiji**")
                        st.markdown(f"<span class='scarcity-pill' style='background-color: {cluster['scarcity_color']}; color: white;'>{cluster['scarcity_badge']}</span>", unsafe_allow_html=True)

                    with c_price_col:
                        st.markdown(f"🛒 **Jumia Median:** `KSh {cluster['jumia_median']:,.0f}` *(Range: {cluster['jumia_min']:,.0f} - {cluster['jumia_max']:,.0f})*")
                        st.markdown(f"🏭 **Wholesale Best:** <span style='color:#10B981; font-weight:bold;'>KSh {cluster['jiji_min']:,.0f}</span> *(Avg: {cluster['jiji_avg']:,.0f})*", unsafe_allow_html=True)
                        st.caption(f"🎯 Recommended Price: **KSh {cluster['recommended_price']:,.0f}**")

                    with c_action_col:
                        st.markdown(f"<span class='profit-badge'>+KES {cluster['net_profit']:,.0f}</span>", unsafe_allow_html=True)
                        st.caption(f"**{cluster['margin_pct']:.1f}% Margin**")
                        st.markdown(f"[🔗 Best Supplier]({cluster['best_supplier']['url']})")

                    # Collapsible Deep-Dive
                    with st.expander("📊 Expand Market Details, Competitor Breakdown & Wholesale Contacts"):
                        d1, d2 = st.columns(2)
                        with d1:
                            st.markdown("##### 🛒 Jumia Competing Listings:")
                            for idx, jm in enumerate(cluster["all_jumia_listings"], 1):
                                st.write(f"{idx}. [{jm['title'][:45]}...]({jm['url']}) - **KSh {jm['price']:,.0f}** ({jm['reviews']} reviews)")
                        with d2:
                            st.markdown("##### 🏭 Jiji Wholesale Suppliers in Nairobi:")
                            for idx, sup in enumerate(cluster["all_jiji_suppliers"], 1):
                                st.write(f"{idx}. [{sup['title'][:45]}...]({sup['url']}) - **KSh {sup['price']:,.0f}** ({sup['region']})")

                    st.markdown("</div>", unsafe_allow_html=True)

        # ---------------------------------------------------------
        # VIEW 2: 1-TO-1 DEAL CARDS
        # ---------------------------------------------------------
        elif view_mode == "🎴 Side-by-Side Deal Cards":
            for _, deal in deals_df.iterrows():
                with st.container():
                    st.markdown("<div class='deal-card'>", unsafe_allow_html=True)
                    
                    b_col1, b_col2, b_col3, b_col4 = st.columns([2, 1, 1, 1])
                    with b_col1:
                        st.markdown(f"**Category:** `{deal['category']}` | **Confidence:** `{deal['confidence_score']:.0f}%`")
                    with b_col2:
                        st.markdown(f"<span class='profit-badge'>+KES {deal['net_profit']:,.0f}</span>", unsafe_allow_html=True)
                    with b_col3:
                        st.caption(f"Margin: **{deal['margin_pct']:.1f}%**")
                    with b_col4:
                        st.caption(f"Reviews: **{deal['jumia_reviews']}**")

                    st.write("")

                    col_jumia, col_arrow, col_jiji = st.columns([5, 1, 5])
                    with col_jumia:
                        st.markdown("#### 🛒 Jumia Kenya (Selling)")
                        j_img_col, j_info_col = st.columns([1, 2])
                        with j_img_col:
                            if deal["jumia_image"] and str(deal["jumia_image"]).startswith("http"):
                                st.image(deal["jumia_image"], width=110)
                        with j_info_col:
                            st.markdown(f"**[{deal['jumia_title'][:65]}...]({deal['jumia_url']})**")
                            st.markdown(f"**Retail:** <span style='font-size:1.2rem; color:#FF9900; font-weight:bold;'>KSh {deal['jumia_price']:,.0f}</span>", unsafe_allow_html=True)

                    with col_arrow:
                        st.markdown("<div style='text-align: center; margin-top: 30px; font-size: 1.8rem;'>➡️</div>", unsafe_allow_html=True)

                    with col_jiji:
                        st.markdown("#### 🏭 Jiji Supplier (Wholesale)")
                        ji_img_col, ji_info_col = st.columns([1, 2])
                        with ji_img_col:
                            if deal["jiji_image"] and str(deal["jiji_image"]).startswith("http"):
                                st.image(deal["jiji_image"], width=110)
                        with ji_info_col:
                            st.markdown(f"**[{deal['jiji_title'][:65]}...]({deal['jiji_url']})**")
                            st.markdown(f"**Cost:** <span style='font-size:1.2rem; color:#10B981; font-weight:bold;'>KSh {deal['jiji_price']:,.0f}</span>", unsafe_allow_html=True)
                            st.caption(f"Location: **{deal['jiji_region']}**")

                    st.markdown("</div>", unsafe_allow_html=True)

        else:
            display_cols = ["deal_id", "category", "jumia_title", "jumia_price", "jiji_price", "net_profit", "margin_pct", "jumia_reviews", "jiji_region"]
            st.dataframe(deals_df[display_cols], width='stretch', height=400)

# -------------------------------------------------------------
# TAB 2: BLUE OCEAN (UNLISTED ON JUMIA)
# -------------------------------------------------------------
with tab_blue_ocean:
    st.subheader("🌊 Blue Ocean Sourcing: Products on Jiji with 0 Competitors on Jumia")
    st.write("These are high-demand items readily available from wholesale suppliers in Nairobi, but **not yet listed by anyone on Jumia Kenya**.")

    col_bo1, col_bo2 = st.columns([3, 1])
    with col_bo1:
        bo_query = st.text_input("Wholesale Product Term to Check on Jiji", "solar rechargeable fan")
        bo_cat = st.selectbox("Category for Blue Ocean Search", template_categories)
    with col_bo2:
        st.write("")
        st.write("")
        run_bo = st.button("🚀 Hunt for Unlisted Products", type="primary", width='stretch')

    bo_engine = ReverseSourcingEngine(use_proxies=use_proxies_toggle)

    if run_bo:
        p_bar = st.progress(0.0)
        p_txt = st.empty()
        def _bo_prog(msg, pct):
            p_txt.write(msg)
            p_bar.progress(pct)

        with st.spinner("Checking wholesale supply on Jiji against Jumia competition..."):
            found_unlisted = asyncio.run(bo_engine.scan_for_unlisted_products(
                query=bo_query,
                category_name=bo_cat,
                max_jiji_pages=2,
                on_progress=_bo_prog
            ))

        st.success(f"✅ Blue Ocean Search Complete! Found {len(found_unlisted)} products with ZERO competing listings on Jumia.")
        st.rerun()

    # Display Existing Blue Ocean Deals
    bo_df = get_blue_ocean_deals(
        category=selected_category if selected_category != "All" else None,
        min_profit=float(min_profit_filter),
        min_margin=float(min_margin_filter)
    )

    st.write(f"**Discovered Blue Ocean Products ({len(bo_df)} unlisted items):**")
    if bo_df.empty:
        st.info("No unlisted Blue Ocean products indexed yet. Use the search tool above to hunt for wholesale items!")
    else:
        for _, bo in bo_df.iterrows():
            with st.container():
                st.markdown("<div class='cluster-card'>", unsafe_allow_html=True)
                b_img, b_desc, b_nums, b_link = st.columns([1, 4, 3, 2])

                with b_img:
                    if bo["image_url"] and str(bo["image_url"]).startswith("http"):
                        st.image(bo["image_url"], width=90)
                    else:
                        st.write("📦 No image")

                with b_desc:
                    st.markdown(f"**{bo['title']}**")
                    st.markdown("<span class='blue-ocean-badge'>💎 ZERO Competitors on Jumia</span>", unsafe_allow_html=True)
                    st.caption(f"Supplier Location: **{bo['jiji_region']}** ({bo['jiji_location'] or 'Nairobi'})")

                with b_nums:
                    st.markdown(f"🏭 **Wholesale Cost:** `KSh {bo['jiji_price']:,.0f}`")
                    st.markdown(f"🎯 **Suggested Jumia Price:** `KSh {bo['recommended_jumia_price']:,.0f}`")
                    st.caption(f"Estimated Fees & Delivery: KES {bo['packaging_cost'] + bo['boda_cost'] + bo['estimated_commission'] + bo['vat_amount']:,.0f}")

                with b_link:
                    st.markdown(f"<span class='profit-badge'>+KES {bo['net_profit']:,.0f}</span>", unsafe_allow_html=True)
                    st.caption(f"**{bo['margin_pct']:.1f}% Margin**")
                    st.markdown(f"[🔗 Contact Jiji Supplier]({bo['jiji_url']})")

                st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------------------------------
# TAB 3: LIVE & BULK HARVESTER (CRAWL UP TO 50 PAGES)
# -------------------------------------------------------------
with tab_scanner:
    st.subheader("📦 Deep Catalog Bulk Harvester")
    st.write("Crawl up to **50 pages per category** directly from the official Jumia template taxonomy to build a database of thousands of products.")

    h_col1, h_col2, h_col3 = st.columns([3, 2, 2])
    with h_col1:
        target_harvest_cat = st.selectbox("Select Jumia Category to Deep Crawl", ["ALL Major Categories"] + template_categories)
    with h_col2:
        harvest_depth = st.slider("Pages per Category (up to 50)", min_value=1, max_value=50, value=5)
    with h_col3:
        st.write("")
        st.write("")
        start_harvest = st.button("🌐 Crawl Whole Jumia & Jiji", type="primary", width='stretch')

    if start_harvest:
        from crawl_all import MasterMarketplaceCrawler
        h_bar = st.progress(0.0)
        h_txt = st.empty()

        def _h_prog(msg, pct):
            h_txt.write(msg)
            h_bar.progress(pct)

        target_cats = None if target_harvest_cat == "ALL Major Categories" else [target_harvest_cat]
        crawler = MasterMarketplaceCrawler(use_proxies=use_proxies_toggle)

        with st.spinner(f"Ingesting marketplace catalog ({harvest_depth} pages)..."):
            res = asyncio.run(crawler.crawl_all_categories(
                pages_per_category=int(harvest_depth),
                target_categories=target_cats,
                on_progress=_h_prog
            ))

        st.success(f"🎉 Mass Ingestion Complete! Saved {res['total_jumia_saved']} Jumia products, {res['total_jiji_saved']} Jiji wholesale ads, and matched {res['total_deals_matched']} deals in {res['duration_seconds']}s.")
        st.rerun()

    st.divider()
    st.subheader("🔍 Keyword-On-Demand Quick Scan")
    col_k1, col_k2, col_k3 = st.columns([3, 2, 1])
    with col_k1:
        kw_input = st.text_input("Enter product search term", "portable high pressure washer")
    with col_k2:
        cat_input = st.selectbox("Assign Category", template_categories)
    with col_k3:
        pages_input = st.number_input("Pages", min_value=1, max_value=5, value=1)

    if st.button("🔍 Run Keyword Scan", width='stretch'):
        scanner = AsyncMarketScanner(use_proxies=use_proxies_toggle) if use_async_toggle else MarketScanner()
        with st.spinner("Scanning..."):
            if use_async_toggle:
                res = asyncio.run(scanner.scan_keyword(
                    keyword=kw_input,
                    category_name=cat_input,
                    jumia_pages=int(pages_input),
                    jiji_pages=int(pages_input)
                ))
            else:
                res = scanner.scan_keyword(
                    keyword=kw_input,
                    category_name=cat_input,
                    jumia_pages=int(pages_input),
                    jiji_pages=int(pages_input)
                )
        st.success(f"✅ Found {res['jumia_count']} Jumia items, {res['jiji_count']} Jiji ads, {res['deals_count']} matches!")
        st.rerun()

# -------------------------------------------------------------
# TAB 4: PROXY POOL & NETWORK
# -------------------------------------------------------------
with tab_proxies:
    st.subheader("🛡️ Rotating Proxy Pool Management")
    st.write(f"Connected to **{len(PROXY_SOURCES)}** GitHub proxy list providers.")

    p1, p2, p3, p4 = st.columns(4)
    p_status = global_proxy_manager.get_status()
    p1.metric("Online Verified Proxies", f"{p_status['total_working']}")
    p2.metric("Average Latency", f"{p_status['avg_latency_ms']} ms")
    p3.metric("Fastest Proxy", f"{p_status['fastest_ms']} ms")
    p4.metric("Configured Sources", f"{p_status['sources_count']} lists")

    st.divider()
    target_count = st.slider("Target Number of Working Proxies", 5, 50, 15)

    if st.button("🔄 Fetch & Validate Fresh Proxies Now", type="primary"):
        p_bar = st.progress(0.0)
        p_text = st.empty()
        def _on_p_prog(msg, pct):
            p_text.write(msg)
            p_bar.progress(pct)

        with st.spinner("Validating proxies concurrently..."):
            found_count = asyncio.run(global_proxy_manager.refresh_pool(
                target_valid=target_count,
                max_workers=50,
                on_progress=_on_p_prog
            ))
        st.success(f"✅ Proxy validation complete! {found_count} fast proxies ready.")
        st.rerun()

    if global_proxy_manager.working_proxies:
        st.markdown("#### 🟢 Active Verified Proxies")
        st.dataframe(pd.DataFrame(global_proxy_manager.working_proxies), width='stretch')

# -------------------------------------------------------------
# TAB 5: SETTINGS & UNIT ECONOMICS
# -------------------------------------------------------------
with tab_settings:
    st.subheader("⚙️ Kenyan Unit Economics & Fee Configuration")
    col_fee1, col_fee2 = st.columns(2)
    with col_fee1:
        st.markdown("#### Operational Fulfillment Buffers")
        packaging_fee = st.number_input("Jumia Flyer / Packaging Cost (KES)", value=float(DEFAULT_PACKAGING_COST_KES), step=5.0)
        boda_runner_fee = st.number_input("Nairobi Boda / Runner Allowance (KES)", value=float(DEFAULT_BODA_RUNNER_COST_KES), step=10.0)
        vat_tax_rate = st.number_input("VAT on Jumia Commission (%)", value=16.0, step=1.0) / 100.0

    with col_fee2:
        st.markdown("#### Jumia Category Commission Rates (%)")
        st.caption("Customizable per category based on Jumia Kenya vendor fee schedule.")
        st.slider("Automobile (%)", 5, 25, 12)
        st.slider("Electronics (%)", 5, 25, 9)
        st.slider("Home & Office (%)", 5, 25, 14)
        st.slider("Health & Beauty (%)", 5, 25, 15)

    st.divider()
    st.markdown("#### 🤖 Telegram Bot Notifications")
    tg_notifier = TelegramNotifier()
    st.write(f"Telegram Configured: **{'✅ Connected' if tg_notifier.is_configured() else '❌ Not Configured'}**")

# -------------------------------------------------------------
# TAB 6: EXPORT CENTER
# -------------------------------------------------------------
with tab_export:
    st.subheader("📥 Export Qualified Opportunities")
    export_df = get_arbitrage_deals(
        min_profit=float(min_profit_filter),
        min_margin=float(min_margin_filter),
        min_confidence=float(min_confidence_filter),
        limit=500
    )

    if export_df.empty:
        st.info("No deals available to export. Run a harvest or adjust the sidebar filters.")
    else:
        st.write(f"**Ready to export:** `{len(export_df)}` deals")
        col_exp1, col_exp2 = st.columns(2)

        csv_data = export_df.to_csv(index=False).encode('utf-8')
        with col_exp1:
            st.download_button(
                label="📄 Download as CSV",
                data=csv_data,
                file_name=f"jumia_dropship_deals_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                width='stretch'
            )

        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            export_df.to_excel(writer, sheet_name='Arbitrage Deals', index=False)
        excel_data = excel_buffer.getvalue()

        with col_exp2:
            st.download_button(
                label="📊 Download as Excel (.xlsx)",
                data=excel_data,
                file_name=f"jumia_dropship_deals_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width='stretch'
            )

        st.dataframe(export_df.head(10), width='stretch')
