# -*- coding: utf-8 -*-
"""
👑 BBKitchen Forensic Quality & Anomaly Triage Dashboard Generator
Sub-Modul 2.11 - Generates standalone interactive quality_matrix.html for zero-headache visual validation.
"""

import os
import sys
import json
import sqlite3
import re
from typing import Dict, Any, List

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)
for p in [CURRENT_DIR, PARENT_DIR]:
    if p not in sys.path:
        sys.path.append(p)

from normalize_engine import OFFICIAL_CATEGORY_SLUGS, CAT_SSOT, load_ssot_taxonomy

JARVIS_DB_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "Jarvis-OS", "domains", "business", "bbkitchen", "data", "bbk.db"))
STOREFRONT_DB_PATH = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", "bbk-storefront", "data", "bbk.db"))

def get_db_path() -> str:
    if os.path.exists(JARVIS_DB_PATH):
        return JARVIS_DB_PATH
    if os.path.exists(STOREFRONT_DB_PATH):
        return STOREFRONT_DB_PATH
    return os.path.join(CURRENT_DIR, "..", "bbk.db")

def audit_product_record(row: dict) -> Dict[str, Any]:
    flags = []
    score = 100
    
    sku = row.get("sku", "")
    title = row.get("title", "") or ""
    cat_slug = row.get("category_slug", "") or ""
    kondisi = row.get("kondisi_unit", "") or ""
    status = row.get("status_unit", "") or ""
    slug = row.get("slug", "") or ""
    caption = row.get("caption_raw", "") or ""
    
    # 1. Title Audit
    noise_keywords = ["mulus", "gress", "ready 3 unit", "sisa", "japan", "jepang", "preparetion", "ice bean"]
    for noise in noise_keywords:
        if noise in title.lower():
            flags.append(f"Title contains noise keyword: '{noise}'")
            score -= 20
            
    if not re.search(r'(\d{2,3}\s*[xX*]\s*\d{2,3}|\d+\s*(?:liter|tray|tungku|burner|pintu|cm|inch))', title, re.IGNORECASE):
        flags.append("Missing physical dimension or capacity in title")
        score -= 15

    # 2. Category Audit
    if cat_slug not in OFFICIAL_CATEGORY_SLUGS:
        flags.append(f"Invalid category slug: '{cat_slug}'")
        score -= 30
    else:
        # Check specific sink jumbo logic
        if "sink" in cat_slug:
            if "jumbo" in (caption + title).lower() and cat_slug != "sink-jumbo-stainless":
                flags.append("Sink has 'jumbo' keyword but category is not 'sink-jumbo-stainless'")
                score -= 25
            elif cat_slug == "sink-jumbo-stainless" and "jumbo" not in (caption + title).lower() and not re.search(r'bowl[:\s]*(\d{3})', caption.lower()):
                flags.append("Categorized as sink jumbo but missing jumbo keyword or 100cm+ bowl")
                score -= 15

    # 3. Binary Condition Audit
    if kondisi not in ["Bekas", "Baru"]:
        flags.append(f"Non-binary condition status: '{kondisi}' (Must be strictly 'Bekas' or 'Baru')")
        score -= 25

    # 4. Binary Status Audit
    if status not in ["READY", "SOLD"]:
        flags.append(f"Non-binary availability status: '{status}'")
        score -= 20

    # 5. Sacred Slug Audit
    if not slug:
        flags.append("Missing product permalink slug")
        score -= 30

    score = max(0, score)
    
    tier = "CLEAN"
    if score < 70 or any("Invalid category" in f or "Non-binary" in f for f in flags):
        tier = "CRITICAL"
    elif score < 90 or flags:
        tier = "REVIEW"

    return {
        "sku": sku,
        "title": title,
        "category_slug": cat_slug,
        "kondisi_unit": kondisi,
        "status_unit": status,
        "slug": slug,
        "score": score,
        "tier": tier,
        "flags": flags,
        "caption_raw": caption
    }

def generate_html_report(output_file: str = "quality_matrix.html"):
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute("""
        SELECT p.*, r.caption_raw
        FROM products p
        LEFT JOIN raw_pipeline r ON p.sku = r.kode_unit
        ORDER BY CAST(SUBSTR(p.sku, 4) AS INTEGER) ASC
    """).fetchall()
    conn.close()

    audited = [audit_product_record(dict(r)) for r in rows]
    
    total = len(audited)
    clean_count = sum(1 for a in audited if a["tier"] == "CLEAN")
    review_count = sum(1 for a in audited if a["tier"] == "REVIEW")
    critical_count = sum(1 for a in audited if a["tier"] == "CRITICAL")
    
    clean_pct = (clean_count / total * 100) if total else 0

    json_data = json.dumps(audited)

    html_content = f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>👑 BBKitchen Catalog Forensic Quality Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body class="bg-slate-950 text-slate-100 font-sans p-6 min-h-screen">
  <div class="max-w-7xl mx-auto space-y-6">
    <!-- Header -->
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
      <div>
        <div class="flex items-center gap-3">
          <span class="text-2xl">👑</span>
          <h1 class="text-2xl font-bold text-white tracking-wide">BBKitchen Catalog Quality Matrix</h1>
        </div>
        <p class="text-sm text-slate-400 mt-1">Autonomous SSOT Forensic Validator & Triage Dashboard</p>
      </div>
      <div class="flex gap-3">
        <div class="bg-emerald-950/60 border border-emerald-500/30 px-4 py-2 rounded-xl text-center">
          <div class="text-xs text-emerald-400 font-semibold uppercase tracking-wider">Health Score</div>
          <div class="text-2xl font-black text-emerald-300">{clean_pct:.1f}%</div>
        </div>
        <div class="bg-slate-800 border border-slate-700 px-4 py-2 rounded-xl text-center">
          <div class="text-xs text-slate-400 font-semibold uppercase tracking-wider">Total Catalog</div>
          <div class="text-2xl font-black text-white">{total:,}</div>
        </div>
      </div>
    </div>

    <!-- Metric Tabs -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <button onclick="setFilter('ALL')" id="tab-ALL" class="p-4 rounded-xl border border-slate-700 bg-slate-900 hover:bg-slate-850 text-left transition flex items-center justify-between">
        <div>
          <div class="text-xs text-slate-400 font-bold uppercase tracking-wider">All Items</div>
          <div class="text-2xl font-extrabold text-white mt-1">{total:,}</div>
        </div>
        <i class="fa-solid fa-layer-group text-2xl text-slate-500"></i>
      </button>

      <button onclick="setFilter('CLEAN')" id="tab-CLEAN" class="p-4 rounded-xl border border-emerald-500/40 bg-emerald-950/20 hover:bg-emerald-950/40 text-left transition flex items-center justify-between">
        <div>
          <div class="text-xs text-emerald-400 font-bold uppercase tracking-wider">🟢 Verified Clean</div>
          <div class="text-2xl font-extrabold text-emerald-300 mt-1">{clean_count:,}</div>
        </div>
        <i class="fa-solid fa-circle-check text-2xl text-emerald-400"></i>
      </button>

      <button onclick="setFilter('REVIEW')" id="tab-REVIEW" class="p-4 rounded-xl border border-amber-500/40 bg-amber-950/20 hover:bg-amber-950/40 text-left transition flex items-center justify-between">
        <div>
          <div class="text-xs text-amber-400 font-bold uppercase tracking-wider">🟡 Needs Attention</div>
          <div class="text-2xl font-extrabold text-amber-300 mt-1">{review_count:,}</div>
        </div>
        <i class="fa-solid fa-triangle-exclamation text-2xl text-amber-400"></i>
      </button>
    </div>

    <!-- Search & Filter Controls -->
    <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row gap-4 justify-between items-center">
      <div class="relative w-full md:w-96">
        <i class="fa-solid fa-magnifying-glass absolute left-3.5 top-3.5 text-slate-500 text-sm"></i>
        <input type="text" id="searchInput" oninput="renderTable()" placeholder="Cari SKU, Judul, atau Kategori..." class="w-full bg-slate-950 border border-slate-800 rounded-lg pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-amber-500">
      </div>
      <div class="text-xs text-slate-400">
        Showing <span id="displayedCount" class="font-bold text-white">0</span> items
      </div>
    </div>

    <!-- Table Container -->
    <div class="bg-slate-900 border border-slate-800 rounded-2xl overflow-hidden shadow-2xl">
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm text-slate-300">
          <thead class="bg-slate-950 text-slate-400 uppercase text-xs tracking-wider border-b border-slate-800">
            <tr>
              <th class="py-3.5 px-4">SKU</th>
              <th class="py-3.5 px-4">Canonical Title</th>
              <th class="py-3.5 px-4">66-SSOT Category</th>
              <th class="py-3.5 px-4 text-center">Kondisi</th>
              <th class="py-3.5 px-4 text-center">Status</th>
              <th class="py-3.5 px-4 text-center">Score</th>
              <th class="py-3.5 px-4">Audit Triage</th>
            </tr>
          </thead>
          <tbody id="tableBody" class="divide-y divide-slate-800/60 font-mono text-xs">
            <!-- Rendered by JS -->
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    const items = {json_data};
    let activeFilter = 'ALL';

    function setFilter(tier) {{
      activeFilter = tier;
      renderTable();
    }}

    function renderTable() {{
      const query = document.getElementById('searchInput').value.toLowerCase();
      const tbody = document.getElementById('tableBody');
      tbody.innerHTML = '';

      let filtered = items.filter(item => {{
        if (activeFilter !== 'ALL' && item.tier !== activeFilter) return false;
        if (!query) return true;
        return item.sku.toLowerCase().includes(query) ||
               item.title.toLowerCase().includes(query) ||
               item.category_slug.toLowerCase().includes(query) ||
               item.caption_raw.toLowerCase().includes(query);
      }});

      document.getElementById('displayedCount').innerText = filtered.length.toLocaleString();

      filtered.forEach(item => {{
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-850 transition';

        const tierBadge = item.tier === 'CLEAN' 
          ? '<span class="px-2 py-0.5 rounded text-emerald-400 bg-emerald-950/60 border border-emerald-500/30 text-[10px] font-bold">VERIFIED</span>'
          : '<span class="px-2 py-0.5 rounded text-amber-400 bg-amber-950/60 border border-amber-500/30 text-[10px] font-bold">NEEDS REVIEW</span>';

        const flagsHtml = item.flags.length > 0 
          ? item.flags.map(f => `<div class="text-amber-400 text-[11px]">• ${{f}}</div>`).join('')
          : '<div class="text-slate-500 text-[11px]">100% Rules Conformed</div>';

        tr.innerHTML = `
          <td class="py-3 px-4 font-bold text-amber-400">${{item.sku}}</td>
          <td class="py-3 px-4 text-white font-sans text-xs font-semibold">${{item.title}}</td>
          <td class="py-3 px-4 text-cyan-300 font-mono text-[11px]">${{item.category_slug}}</td>
          <td class="py-3 px-4 text-center">
            <span class="px-2 py-0.5 rounded font-bold text-[10px] ${{item.kondisi_unit === 'Baru' ? 'bg-blue-950 text-blue-300 border border-blue-500/30' : 'bg-slate-800 text-slate-300'}}">
              ${{item.kondisi_unit}}
            </span>
          </td>
          <td class="py-3 px-4 text-center">
            <span class="px-2 py-0.5 rounded font-bold text-[10px] ${{item.status_unit === 'READY' ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/30' : 'bg-red-950 text-red-300 border border-red-500/30'}}">
              ${{item.status_unit}}
            </span>
          </td>
          <td class="py-3 px-4 text-center font-bold ${{item.score >= 90 ? 'text-emerald-400' : 'text-amber-400'}}">${{item.score}}</td>
          <td class="py-3 px-4 font-sans">${{flagsHtml}}</td>
        `;
        tbody.appendChild(tr);
      }});
    }}

    renderTable();
  </script>
</body>
</html>
"""

    report_path = os.path.join(CURRENT_DIR, "..", output_file)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"📊 [QUALITY REPORT] Generated standalone dashboard at: {os.path.abspath(report_path)}")
    print(f"   Total: {total:,} | Clean: {clean_count:,} ({clean_pct:.1f}%) | Review: {review_count:,} | Critical: {critical_count:,}")

if __name__ == "__main__":
    generate_html_report()
