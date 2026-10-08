"""
Product Clustering, Price Distribution Analytics, and Abundance/Scarcity Index.
Groups similar products of the same specifications into canonical clusters and computes:
- Min, Max, Median, and Average prices across Jumia and Jiji
- Supply vs Demand Arbitrage Index (Abundant on Jiji, Scarce on Jumia)
- Recommended competitive selling price and optimal margin
"""
import re
import statistics
from typing import List, Dict, Any, Optional
import pandas as pd
from engine.matcher import ProductMatcher
from engine.calculator import ProfitCalculator

class ProductClusterEngine:
    def __init__(self, matcher: Optional[ProductMatcher] = None, calculator: Optional[ProfitCalculator] = None):
        self.matcher = matcher or ProductMatcher(min_confidence=60.0)
        self.calculator = calculator or ProfitCalculator()

    def analyze_clusters(self, deals_df: pd.DataFrame, cluster_threshold: float = 65.0) -> List[Dict[str, Any]]:
        """
        Group individual 1-to-1 arbitrage deals into canonical product clusters
        using semantic spec matching and compute market insights.
        """
        if deals_df.empty:
            return []

        clusters: List[Dict[str, Any]] = []

        for _, row in deals_df.iterrows():
            jumia_title = str(row.get("jumia_title", "")).strip()
            jiji_title = str(row.get("jiji_title", "")).strip()
            category = str(row.get("category", "General"))
            jumia_specs = self.matcher.extract_specs(jumia_title)

            # Find matching existing cluster
            target_cluster = None
            for c in clusters:
                if c["category"] != category:
                    continue

                # Check spec compatibility
                c_specs = c["specs"]
                spec_conflict = False
                for k, v in jumia_specs.items():
                    if k in c_specs and c_specs[k] != v:
                        spec_conflict = True
                        break
                if spec_conflict:
                    continue

                # Compute fuzzy similarity between product and cluster canonical title
                conf, _ = self.matcher.compute_match_confidence(
                    jumia_title=jumia_title,
                    jiji_title=c["canonical_title"]
                )

                if conf >= cluster_threshold:
                    target_cluster = c
                    # Merge any new specs
                    c["specs"].update(jumia_specs)
                    break

            # If no existing cluster matches, create a new one
            if target_cluster is None:
                target_cluster = {
                    "cluster_id": len(clusters) + 1,
                    "canonical_title": jumia_title,
                    "category": category,
                    "specs": jumia_specs,
                    "sample_image": row.get("jumia_image") or row.get("jiji_image"),
                    "jumia_items": {},  # keyed by url to eliminate duplicate listings
                    "jiji_items": {},   # keyed by url to eliminate duplicate supplier listings
                    "deals": []
                }
                clusters.append(target_cluster)

            # Add Jumia listing
            j_url = row.get("jumia_url")
            if j_url and j_url not in target_cluster["jumia_items"]:
                target_cluster["jumia_items"][j_url] = {
                    "title": jumia_title,
                    "price": float(row.get("jumia_price", 0.0)),
                    "reviews": int(row.get("jumia_reviews", 0)),
                    "rating": float(row.get("jumia_rating", 0.0)),
                    "is_express": bool(row.get("jumia_express", False)),
                    "url": j_url,
                    "image": row.get("jumia_image")
                }

            # Add Jiji supplier listing
            ji_url = row.get("jiji_url")
            if ji_url and ji_url not in target_cluster["jiji_items"]:
                target_cluster["jiji_items"][ji_url] = {
                    "title": jiji_title,
                    "price": float(row.get("jiji_price", 0.0)),
                    "region": row.get("jiji_region", "Nairobi"),
                    "location": row.get("jiji_location", ""),
                    "phone": row.get("jiji_phone"),
                    "url": ji_url,
                    "image": row.get("jiji_image")
                }

            target_cluster["deals"].append(row)

        # Compute distributions and supply vs demand metrics for each cluster
        cluster_summaries = []
        for c in clusters:
            jumia_list = list(c["jumia_items"].values())
            jiji_list = list(c["jiji_items"].values())

            if not jumia_list or not jiji_list:
                continue

            jumia_prices = [item["price"] for item in jumia_list if item["price"] > 0]
            jiji_prices = [item["price"] for item in jiji_list if item["price"] > 0]

            if not jumia_prices or not jiji_prices:
                continue

            # Jumia Price Distributions
            j_min = min(jumia_prices)
            j_max = max(jumia_prices)
            j_avg = round(sum(jumia_prices) / len(jumia_prices), 2)
            j_median = round(statistics.median(jumia_prices), 2)
            j_total_reviews = sum(item["reviews"] for item in jumia_list)
            j_avg_reviews = round(j_total_reviews / len(jumia_list), 1)

            # Jiji Wholesale Distributions
            ji_min = min(jiji_prices)
            ji_max = max(jiji_prices)
            ji_avg = round(sum(jiji_prices) / len(jiji_prices), 2)
            ji_median = round(statistics.median(jiji_prices), 2)

            # Supply vs Demand Scarcity Ratio
            jiji_count = len(jiji_list)
            jumia_count = len(jumia_list)
            supply_demand_ratio = round(jiji_count / max(1, jumia_count), 2)

            # Market Abundance / Scarcity Classification
            if jiji_count >= 2 and jumia_count <= 2 and j_total_reviews <= 15:
                scarcity_badge = "🔥 Abundant on Jiji, Scarce on Jumia"
                scarcity_status = "high_scarcity_opportunity"
                scarcity_color = "#10B981" # Green
            elif jiji_count >= 3 and jumia_count <= 4:
                scarcity_badge = "🟢 Strong Supply, Low Competition"
                scarcity_status = "favorable_supply"
                scarcity_color = "#3B82F6" # Blue
            elif jumia_count >= 8 and j_total_reviews > 80:
                scarcity_badge = "⚠️ Saturated on Jumia"
                scarcity_status = "saturated"
                scarcity_color = "#EF4444" # Red
            else:
                scarcity_badge = "⚖️ Balanced Market"
                scarcity_status = "balanced"
                scarcity_color = "#8B5CF6" # Purple

            # Recommended Selling Price Strategy
            rec_price = round(j_median * 0.95, -1)
            if rec_price <= ji_min * 1.2:
                rec_price = round(ji_min * 1.6, -1)

            fin = self.calculator.calculate_deal_finances(
                jumia_price=rec_price,
                jiji_price=ji_min,
                category=c["category"]
            )

            comp_score = self.calculator.compute_competition_score(
                reviews_count=j_avg_reviews,
                is_express=any(item["is_express"] for item in jumia_list)
            )

            opp_score = self.calculator.compute_opportunity_score(
                net_profit=fin["net_profit"],
                margin_pct=fin["margin_pct"],
                competition_score=comp_score,
                confidence_score=85.0
            )

            best_supplier = min(jiji_list, key=lambda x: x["price"])
            top_jumia = jumia_list[0]

            cluster_summaries.append({
                "cluster_id": c["cluster_id"],
                "title": c["canonical_title"],
                "category": c["category"],
                "sample_image": c["sample_image"],
                "jumia_sellers_count": jumia_count,
                "jiji_suppliers_count": jiji_count,
                "supply_demand_ratio": supply_demand_ratio,
                "scarcity_badge": scarcity_badge,
                "scarcity_status": scarcity_status,
                "scarcity_color": scarcity_color,
                # Jumia Distributions
                "jumia_min": j_min,
                "jumia_median": j_median,
                "jumia_avg": j_avg,
                "jumia_max": j_max,
                "jumia_total_reviews": j_total_reviews,
                # Jiji Distributions
                "jiji_min": ji_min,
                "jiji_median": ji_median,
                "jiji_avg": ji_avg,
                "jiji_max": ji_max,
                # Recommended Pricing & Profit
                "recommended_price": rec_price,
                "net_profit": fin["net_profit"],
                "margin_pct": fin["margin_pct"],
                "opportunity_score": opp_score,
                "competition_score": comp_score,
                # Supplier and competitor references
                "best_supplier": best_supplier,
                "top_jumia": top_jumia,
                "all_jumia_listings": jumia_list,
                "all_jiji_suppliers": jiji_list
            })

        # Sort by Opportunity Score descending
        cluster_summaries.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return cluster_summaries
