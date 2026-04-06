"""
Project: Reddit Pulse (MAD-SC Discovery Engine)
Author: scruffyie (GitHub)
Identity: /u/fusion_dev (Reddit)
Description: Automated discovery of high-confidence subreddit breakouts using 
             a post-grad research algorithm.
             Based on research paper available on request.
             Current version is doing simple http requests pending API approval
             as proof of concept.
"""

import requests
import json
import time
import os
import csv
import shutil
from datetime import datetime

# --- CONFIG ---
SUBREDDITS_FILE = "subreddits.csv"
BASELINES_FILE  = "baselines.json"
OUTPUT_JSON     = "latest_rankings.json"
OUTPUT_HTML     = "index.html"
HISTORY_DIR     = "history"

TIER_CONFIG = {"mega": 1, "large": 3, "medium": 8, "small": 20}
EMA_ALPHA, MAD_TOP_N = 0.1, 5
FEED_TYPE, TIMEFRAME = "top", "day"
USER_AGENT = "web:mad-sc-discovery-engine:v2.0 (by /u/fusion_dev)"

# --- CORE FUNCTIONS ---

def archive_old_results():
    if os.path.exists(OUTPUT_JSON):
        if not os.path.exists(HISTORY_DIR): os.makedirs(HISTORY_DIR)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        shutil.copy(OUTPUT_JSON, f"{HISTORY_DIR}/{ts}_rankings.json")

def generate_html_report(metadata, posts):
    """Generates a clean, responsive HTML dashboard."""
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Reddit Pulse: MAD-SC Discovery</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f4f7f6; color: #333; line-height: 1.6; padding: 20px; }}
            .container {{ max-width: 900px; margin: auto; }}
            header {{ background: #1a1a1b; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
            .post-card {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 5px solid #ff4500; box-shadow: 0 2px 4px rgba(0,0,0,0.05); transition: transform 0.2s; }}
            .post-card:hover {{ transform: translateY(-2px); }}
            .post-title {{ font-size: 1.25rem; font-weight: bold; text-decoration: none; color: #0079d3; display: block; margin-bottom: 5px; }}
            .subreddit-tag {{ background: #edeff1; padding: 2px 8px; border-radius: 12px; font-size: 0.85rem; font-weight: bold; color: #1c1c1c; }}
            .metrics-row {{ margin-top: 10px; font-size: 0.9rem; color: #787c7e; display: flex; gap: 15px; flex-wrap: wrap; }}
            .metric-pill {{ background: #f6f7f8; padding: 4px 10px; border-radius: 4px; border: 1px solid #ddd; }}
            .fusion-highlight {{ color: #ff4500; font-weight: bold; border-color: #ff4500; }}
            footer {{ text-align: center; margin-top: 40px; font-size: 0.8rem; color: #aaa; }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Reddit Pulse Dashboard</h1>
                <p>Calculated at: {run_time} | Feed: {feed} ({timeframe})</p>
            </header>
            <main>
                {post_html}
            </main>
            <footer>
                <p>MAD-SC Engine v2.0 | Research paper on request</p>
            </footer>
        </div>
    </body>
    </html>
    """
    
    post_items = []
    for p in posts:
        # Convert created_utc to human readable
        dt_object = datetime.fromtimestamp(p['created_utc'])
        human_time = dt_object.strftime("%b %d, %H:%M")
        
        post_html = f"""
        <div class="post-card">
            <a href="{p['url']}" class="post-title" target="_blank">{p['title']}</a>
            <span class="subreddit-tag">r/{p['subreddit']}</span>
            <div class="metrics-row">
                <span class="metric-pill">Score: <strong>{p['raw_score']}</strong></span>
                <span class="metric-pill fusion-highlight">Fusion: {p['fusion_score']}</span>
                <span class="metric-pill">Velocity: {p['velocity']}x</span>
                <span class="metric-pill">Confidence: {p['confidence']}</span>
                <span>{human_time}</span>
            </div>
        </div>
        """
        post_items.append(post_html)

    full_html = html_template.format(
        run_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
        feed=metadata['feed'],
        timeframe=metadata['timeframe'],
        post_html="".join(post_items)
    )
    
    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(full_html)

def run_engine():
    print("--- Starting Tiered Discovery Engine ---")
    archive_old_results()
    
    # 1. Load Subreddits and Baselines
    tiered_groups = {}
    with open(SUBREDDITS_FILE, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            t, s = row['tier'].lower().strip(), row['subreddit'].lower().strip()
            if t not in tiered_groups: tiered_groups[t] = []
            tiered_groups[t].append(s)

    baselines = json.load(open(BASELINES_FILE)) if os.path.exists(BASELINES_FILE) else {}
    all_posts, sub_distributions = [], {}

    # 2. Fetch Data
    for tier, subs in tiered_groups.items():
        batch_size = TIER_CONFIG.get(tier, 5)
        chunks = [subs[i:i + batch_size] for i in range(0, len(subs), batch_size)]
        for batch in chunks:
            url = f"https://www.reddit.com/r/{'+'.join(batch)}/{FEED_TYPE}.json?limit=100&t={TIMEFRAME}"
            try:
                r = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=15)
                if r.status_code == 200:
                    for child in r.json().get('data', {}).get('children', []):
                        d = child['data']
                        if d['score'] < 1: continue
                        sub = d['subreddit'].lower()
                        all_posts.append({
                            'title': d['title'], 'subreddit': sub, 'raw_score': d['score'],
                            'url': f"https://reddit.com{d['permalink']}", 'created_utc': d['created_utc']
                        })
                        if sub not in sub_distributions: sub_distributions[sub] = []
                        sub_distributions[sub].append(d['score'])
                time.sleep(2)
            except Exception as e: print(f"Error fetching {batch}: {e}")

    # 3. Process Metrics
    final_posts = []
    for p in all_posts:
        sub = p['subreddit']
        scores = sub_distributions.get(sub, [p['raw_score']])
        
        # Calculate MAD-SC Confidence
        mad_global = 0.001
        if len(scores) >= 2:
            diffs = [abs(scores[i] - scores[i+1]) for i in range(len(scores)-1)]
            mad_global = sum(diffs) / len(diffs)
        
        mad_subset = 0.001
        if len(scores) >= MAD_TOP_N + 1:
            subset_diffs = [abs(scores[i] - scores[i+1]) for i in range(MAD_TOP_N)]
            mad_subset = sum(subset_diffs) / len(subset_diffs)
            
        confidence = round(mad_subset / mad_global if mad_global > 0.001 else 1.0, 2)
        
        # Velocity logic
        current_avg = sum(scores) / len(scores)
        old_b = baselines.get(sub, current_avg)
        new_b = (current_avg * EMA_ALPHA) + (old_b * (1 - EMA_ALPHA))
        baselines[sub] = new_b
        
        velocity = round(p['raw_score'] / new_b if new_b > 0 else 1.0, 2)
        p['fusion_score'] = round(velocity * confidence, 4)
        p['velocity'], p['confidence'] = velocity, confidence
        final_posts.append(p)

    final_posts.sort(key=lambda x: x['fusion_score'], reverse=True)
    
    # 4. Save and Render
    metadata = {"feed": FEED_TYPE, "timeframe": TIMEFRAME}
    
    with open(OUTPUT_JSON, "w") as f:
        json.dump({"metadata": metadata, "posts": final_posts[:500]}, f, indent=4)
    with open(BASELINES_FILE, "w") as f:
        json.dump(baselines, f, indent=4)
        
    generate_html_report(metadata, final_posts[:100])
    print(f"--- SUCCESS: Rankings and HTML Dashboard updated ---")

if __name__ == "__main__":
    run_engine()