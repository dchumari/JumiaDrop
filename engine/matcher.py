"""
Product Matcher Engine.
Performs spec extraction and fuzzy attribute matching between Jumia Kenya and Jiji Kenya listings.
"""
import re
from typing import Dict, Any, Tuple, Optional
from rapidfuzz import fuzz

class ProductMatcher:
    # Common marketing boilerplate words to strip
    STOP_WORDS = {
        "generic", "hot", "sale", "high", "quality", "brand", "new", "original",
        "best", "seller", "promotion", "arrival", "portable", "durable", "cheap",
        "free", "delivery", "genuine", "authentic", "upgraded", "latest", "pro", "mini"
    }

    def __init__(self, min_confidence: float = 65.0):
        self.min_confidence = min_confidence

    def clean_title(self, title: str) -> str:
        """Strip punctuation, excessive whitespace, and promotional boilerplate."""
        if not title:
            return ""
        # Lowercase and replace punctuation with spaces
        text = re.sub(r"[^\w\s]", " ", title.lower())
        tokens = [w for w in text.split() if w and w not in self.STOP_WORDS and len(w) > 1]
        return " ".join(tokens)

    def extract_specs(self, text: str) -> Dict[str, str]:
        """
        Extract critical technical specifications (voltage, wattage, capacity, quantities)
        to prevent mismatched variants.
        """
        specs = {}
        t = text.lower()

        # Voltage: e.g. 48v, 48vf, 21v, 12v, 220v
        v_match = re.search(r"\b(\d+)\s*(?:v|vf|volt)\b", t)
        if v_match:
            specs["voltage"] = f"{v_match.group(1)}v"

        # Wattage: e.g. 120w, 60w, 1500w
        w_match = re.search(r"\b(\d+)\s*(?:w|watt)\b", t)
        if w_match:
            specs["wattage"] = f"{w_match.group(1)}w"

        # Battery capacity: e.g. 20000mah, 10000mah, 2ah, 4ah
        mah_match = re.search(r"\b(\d+)\s*(?:mah|ah)\b", t)
        if mah_match:
            specs["battery"] = f"{mah_match.group(1)}mah"

        # Volume / Liquid Capacity: e.g. 5l, 1.8l, 500ml
        vol_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:l|liter|litre|ml)\b", t)
        if vol_match:
            specs["volume"] = vol_match.group(1)

        # Multi-in-one configs: e.g. 3 in 1, 3-in-1, 4-in-1, 3in1
        in_one = re.search(r"\b(\d+)[\s-]*(?:in)[\s-]*1\b", t)
        if in_one:
            specs["multi"] = f"{in_one.group(1)}in1"

        return specs

    def compute_match_confidence(
        self,
        jumia_title: str,
        jiji_title: str,
        jiji_description: str = "",
        jumia_price: float = 0.0,
        jiji_price: float = 0.0
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Compare Jumia and Jiji product descriptions and return:
        (confidence_score 0-100, metadata_dict)
        """
        clean_jumia = self.clean_title(jumia_title)
        clean_jiji = self.clean_title(jiji_title)

        if not clean_jumia or not clean_jiji:
            return 0.0, {"reason": "empty titles"}

        # Extract specs
        jumia_specs = self.extract_specs(jumia_title)
        jiji_specs = self.extract_specs(f"{jiji_title} {jiji_description}")

        # Spec conflict check: e.g. 48V vs 12V
        spec_conflicts = []
        spec_matches = []
        for key, jm_val in jumia_specs.items():
            if key in jiji_specs:
                jj_val = jiji_specs[key]
                if jm_val != jj_val:
                    spec_conflicts.append(f"{key}: {jm_val} != {jj_val}")
                else:
                    spec_matches.append(f"{key}: {jm_val}")

        # Hard rejection or severe penalty if specs conflict directly
        if spec_conflicts:
            return 10.0, {
                "reason": "spec_conflict",
                "conflicts": spec_conflicts,
                "clean_jumia": clean_jumia,
                "clean_jiji": clean_jiji
            }

        # Token set and sort ratio
        token_set = fuzz.token_set_ratio(clean_jumia, clean_jiji)
        token_sort = fuzz.token_sort_ratio(clean_jumia, clean_jiji)
        partial = fuzz.partial_ratio(clean_jumia, clean_jiji)

        # Base similarity score
        score = (token_set * 0.5) + (token_sort * 0.3) + (partial * 0.2)

        # Bonus for matched specs
        if spec_matches:
            score = min(100.0, score + (len(spec_matches) * 5.0))

        # Price sanity check:
        # If Jiji price is higher than Jumia retail price, dropshipping is not viable
        if jumia_price > 0 and jiji_price > 0:
            if jiji_price > jumia_price:
                score = max(0.0, score - 20.0)
            elif jumia_price >= jiji_price * 1.5:
                # Strong arbitrage spread bonus
                score = min(100.0, score + 5.0)

        final_score = round(max(0.0, min(100.0, score)), 1)
        return final_score, {
            "token_set": token_set,
            "token_sort": token_sort,
            "spec_matches": spec_matches,
            "clean_jumia": clean_jumia,
            "clean_jiji": clean_jiji
        }
