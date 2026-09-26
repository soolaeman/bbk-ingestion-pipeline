# -*- coding: utf-8 -*-
"""
👑 BBKitchen On-Demand ISR Revalidation Client (revalidate_client.py)
Supports both Single SKU and Bulk Revalidation on Vercel Live Storefront.
Zero Deploy Quota Usage • Instant <0.5s Edge Cache Purge.
"""

import os
import requests
from typing import List, Optional, Dict, Any

STOREFRONT_URL = os.getenv("STOREFRONT_URL", "https://bukanbarukitchen.com").rstrip("/")
REVALIDATE_SECRET = os.getenv("REVALIDATE_SECRET", "bbk_revalidate_secret_key_2026")

def trigger_revalidation(
    skus: Optional[List[str]] = None,
    slugs: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
    all_catalog: bool = False,
    base_url: Optional[str] = None,
    secret: Optional[str] = None
) -> Dict[str, Any]:
    """
    Triggers On-Demand ISR on the Vercel Storefront.
    
    Args:
        skus: List of SKUs to revalidate (e.g. ['BBK3215'])
        slugs: List of URL slugs to revalidate
        categories: List of category slugs to revalidate
        all_catalog: If True, purges all products, categories, and homepage caches
        base_url: Override storefront URL
        secret: Override revalidation secret token
        
    Returns:
        JSON response dict from storefront API
    """
    target_url = (base_url or STOREFRONT_URL).rstrip("/") + "/api/revalidate"
    auth_secret = secret or REVALIDATE_SECRET

    payload = {
        "secret": auth_secret,
        "all": all_catalog,
        "skus": skus or [],
        "slugs": slugs or [],
        "categories": categories or []
    }

    try:
        res = requests.post(
            target_url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "x-revalidate-secret": auth_secret
            },
            timeout=10
        )
        if res.status_code == 200:
            data = res.json()
            print(f"✅ [ISR Revalidation Success] Type: {data.get('type')} | Paths: {len(data.get('paths', []))}")
            return data
        else:
            print(f"⚠️ [ISR Revalidation Warning] HTTP {res.status_code}: {res.text}")
            return {"error": f"HTTP {res.status_code}", "details": res.text}
    except Exception as e:
        print(f"❌ [ISR Revalidation Error] Could not reach {target_url}: {e}")
        return {"error": "ConnectionError", "details": str(e)}

if __name__ == "__main__":
    print("=== Testing BBKitchen Revalidation Client ===")
    print("Testing local or live endpoint...")
    # Dry run test on local/mock
    test_res = trigger_revalidation(skus=["BBK3215"], slugs=["showcase-1-pintu-gea-second-231l-bbk3215"])
    print("Result:", test_res)
