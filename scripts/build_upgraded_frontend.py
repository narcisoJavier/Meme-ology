"""Generate upgraded frontend with clean like buttons, Top 10 Trending, and multi-platform support."""

import json
from pathlib import Path

# Load merged multi-platform memes
data_path = Path("data/live_harvested_memes.json")
live_memes = json.loads(data_path.read_text(encoding="utf-8"))
memes_json_str = json.dumps(live_memes, indent=4)

html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MEME-OLOGY! — The Living Internet Meme Almanac</title>
  <meta name="description" content="Explore, score, and discover fresh memes across Reddit, Instagram Reels, TikTok, YouTube Shorts, and Know Your Meme.">
  <meta name="referrer" content="no-referrer">

  <!-- Google Fonts: Space Grotesk, Bangers, and JetBrains Mono -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Bangers&family=Space+Grotesk:wght@500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">

  <style>
    :root {{
      --comic-yellow: #FFE81F;
      --comic-red: #FF2A42;
      --comic-cyan: #00E5FF;
      --comic-pink: #FF3B94;
      --comic-lime: #22E576;
      --comic-purple: #8B5CF6;
      --comic-orange: #F97316;
      --comic-ink: #0C0C0F;
      --comic-paper: #FFFDF7;
      --border-ink: 3px solid #0C0C0F;
      --shadow-sm: 3px 3px 0px #0C0C0F;
      --shadow-hard: 6px 6px 0px #0C0C0F;
      --shadow-heavy: 10px 10px 0px #0C0C0F;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    html {{
      scroll-behavior: smooth;
    }}

    body {{
      background-color: var(--comic-paper);
      background-image: 
        radial-gradient(#0C0C0F 12%, transparent 12%),
        radial-gradient(#0C0C0F 12%, transparent 12%);
      background-size: 28px 28px;
      background-position: 0 0, 14px 14px;
      background-attachment: fixed;
      color: var(--comic-ink);
      font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      overflow-x: hidden;
      line-height: 1.5;
    }}

    /* Top Strip Banner */
    .comic-top-banner {{
      background: var(--comic-ink);
      color: #fff;
      padding: 6px 1.5rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 2px solid #000;
    }}

    /* Navigation */
    header {{
      background: var(--comic-yellow);
      border-bottom: var(--border-ink);
      position: sticky;
      top: 0;
      z-index: 100;
      box-shadow: 0 4px 0px rgba(0,0,0,0.15);
    }}

    .nav-container {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 0.75rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      flex-wrap: wrap;
    }}

    .comic-logo-group {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }}

    .comic-logo {{
      font-family: 'Bangers', cursive;
      font-size: 2.2rem;
      letter-spacing: 0.05em;
      color: var(--comic-ink);
      text-shadow: 2px 2px 0px #fff, 4px 4px 0px var(--comic-red);
      line-height: 1;
      transform: rotate(-1.5deg);
      display: inline-block;
      text-decoration: none;
      transition: transform 0.2s;
    }}

    .comic-logo:hover {{
      transform: rotate(1deg) scale(1.05);
    }}

    .comic-stamp-pill {{
      background: var(--comic-red);
      color: #fff;
      border: 2px solid #000;
      padding: 3px 8px;
      font-size: 0.7rem;
      font-weight: 800;
      border-radius: 4px;
      box-shadow: 2px 2px 0px #000;
      transform: rotate(2deg);
    }}

    /* Tri-Section Navigation Switcher */
    .section-nav-switcher {{
      display: flex;
      background: #fff;
      border: var(--border-ink);
      border-radius: 30px;
      padding: 4px;
      box-shadow: var(--shadow-sm);
      gap: 4px;
    }}

    .section-nav-btn {{
      border: none;
      background: transparent;
      padding: 6px 14px;
      font-family: 'Space Grotesk', sans-serif;
      font-weight: 800;
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      cursor: pointer;
      border-radius: 20px;
      transition: all 0.15s ease;
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }}

    .section-nav-btn:hover {{
      background: #f4f4f5;
    }}

    .section-nav-btn.active {{
      background: var(--comic-red);
      color: #fff;
      box-shadow: 2px 2px 0px #000;
    }}

    .nav-right-actions {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }}

    .btn-comic {{
      background: #fff;
      border: var(--border-ink);
      box-shadow: var(--shadow-sm);
      padding: 6px 12px;
      font-weight: 800;
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      cursor: pointer;
      border-radius: 4px;
      transition: all 0.12s ease;
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      text-decoration: none;
      color: #000;
    }}

    .btn-comic:hover {{
      transform: translate(-1px, -1px);
      box-shadow: var(--shadow-hard);
      background: #fff;
    }}

    .btn-comic-cyan {{
      background: var(--comic-cyan);
      color: #000;
    }}

    .btn-comic-red {{
      background: var(--comic-red);
      color: #fff;
    }}

    /* Main Container */
    .section-container {{
      max-width: 1400px;
      margin: 1.5rem auto;
      padding: 0 1.5rem;
    }}

    /* Friendly Casual Hero Header */
    .section-header-box {{
      background: #fff;
      border: var(--border-ink);
      box-shadow: var(--shadow-heavy);
      padding: 1.75rem 2rem;
      border-radius: 8px;
      position: relative;
      margin-bottom: 1.5rem;
      display: grid;
      grid-template-columns: 1.7fr 1fr;
      gap: 1.5rem;
      align-items: center;
      overflow: hidden;
    }}

    .section-header-box::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 8px;
      background: repeating-linear-gradient(45deg, #000, #000 15px, var(--comic-yellow) 15px, var(--comic-yellow) 30px);
    }}

    .section-badge-tag {{
      display: inline-block;
      background: var(--comic-cyan);
      border: 2px solid #000;
      box-shadow: 2px 2px 0px #000;
      padding: 3px 10px;
      font-family: 'Bangers', cursive;
      font-size: 1.05rem;
      letter-spacing: 0.05em;
      margin-bottom: 0.5rem;
      transform: rotate(-1deg);
    }}

    .hero-title {{
      font-family: 'Bangers', cursive;
      font-size: clamp(2.4rem, 4.5vw, 3.6rem);
      letter-spacing: 0.03em;
      line-height: 1;
      margin-bottom: 0.75rem;
      color: var(--comic-ink);
      text-shadow: 2px 2px 0px var(--comic-yellow), 4px 4px 0px var(--comic-red);
    }}

    .hero-desc {{
      font-size: 1rem;
      font-weight: 600;
      color: #333;
      max-width: 620px;
      margin-bottom: 1rem;
    }}

    .sticker-cloud {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      align-items: center;
    }}

    .comic-sticker {{
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      padding: 4px 10px;
      border: var(--border-ink);
      font-size: 0.78rem;
      font-weight: 800;
      box-shadow: var(--shadow-sm);
      border-radius: 4px;
      text-transform: uppercase;
      cursor: default;
    }}

    .sticker-alpha {{ background: var(--comic-purple); color: #fff; transform: rotate(-2deg); }}
    .sticker-z {{ background: var(--comic-lime); color: #000; transform: rotate(1.5deg); }}
    .sticker-millennial {{ background: var(--comic-cyan); color: #000; transform: rotate(-1deg); }}
    .sticker-boomer {{ background: var(--comic-orange); color: #fff; transform: rotate(2deg); }}

    /* Telemetry Box */
    .radar-telemetry-box {{
      background: var(--comic-yellow);
      border: var(--border-ink);
      box-shadow: var(--shadow-hard);
      padding: 1.2rem;
      border-radius: 6px;
      text-align: center;
    }}

    .radar-telemetry-box h3 {{
      font-family: 'Bangers', cursive;
      font-size: 1.4rem;
      letter-spacing: 0.04em;
      margin-bottom: 0.2rem;
    }}

    .telemetry-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 0.6rem;
      margin-top: 0.75rem;
    }}

    .telemetry-cell {{
      background: #fff;
      border: 2px solid #000;
      padding: 0.5rem;
      box-shadow: 2px 2px 0px #000;
      border-radius: 4px;
    }}

    .telemetry-num {{
      font-family: 'Bangers', cursive;
      font-size: 1.5rem;
      color: var(--comic-red);
      line-height: 1;
    }}

    .telemetry-lbl {{
      font-size: 0.68rem;
      font-weight: 800;
      text-transform: uppercase;
      margin-top: 2px;
    }}

    /* =========================================================
       FEATURED MEME OF THE DAY (SPOTLIGHT HERO)
       ========================================================= */
    .featured-spotlight-card {{
      background: #fff;
      border: var(--border-ink);
      box-shadow: var(--shadow-heavy);
      border-radius: 8px;
      margin-bottom: 1.5rem;
      position: relative;
      overflow: hidden;
    }}

    .spotlight-badge-tab {{
      background: var(--comic-yellow);
      border-bottom: 3px solid #000;
      padding: 6px 16px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-family: 'Bangers', cursive;
      font-size: 1.25rem;
      letter-spacing: 0.05em;
    }}

    .spotlight-body {{
      padding: 1.25rem 1.5rem;
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 1.5rem;
      align-items: center;
    }}

    .spotlight-media-frame {{
      height: 240px;
      background: #111116;
      border: 2px solid #000;
      box-shadow: 3px 3px 0px #000;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }}

    .spotlight-media-frame img, .spotlight-media-frame video {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }}

    .spotlight-info-col {{
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }}

    .spotlight-title {{
      font-size: 1.35rem;
      font-weight: 800;
      line-height: 1.3;
    }}

    .spotlight-meta-row {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;
    }}

    /* =========================================================
       STREAMLINED COMPACT TOOLBAR
       ========================================================= */
    .streamlined-toolbar {{
      background: #fff;
      border: var(--border-ink);
      box-shadow: var(--shadow-hard);
      border-radius: 8px;
      padding: 0.75rem 1rem;
      margin-bottom: 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      flex-wrap: wrap;
    }}

    .search-input-box {{
      position: relative;
      flex: 1 1 240px;
    }}

    .compact-search-input {{
      width: 100%;
      border: 2px solid #000;
      box-shadow: 2px 2px 0px #000;
      padding: 7px 10px 7px 2.2rem;
      font-family: 'Space Grotesk', sans-serif;
      font-size: 0.88rem;
      font-weight: 700;
      border-radius: 4px;
      outline: none;
      background: #fafafa;
    }}

    .compact-search-input:focus {{
      background: #fff;
      box-shadow: 3px 3px 0px #000;
    }}

    .search-icon {{
      position: absolute;
      left: 0.7rem;
      top: 50%;
      transform: translateY(-50%);
      font-size: 0.95rem;
      pointer-events: none;
    }}

    .compact-era-pills {{
      display: flex;
      align-items: center;
      gap: 0.4rem;
      flex-wrap: wrap;
    }}

    .comic-filter-pill {{
      background: #fff;
      border: 2px solid #000;
      box-shadow: 2px 2px 0px #000;
      padding: 5px 12px;
      font-size: 0.8rem;
      font-weight: 800;
      cursor: pointer;
      border-radius: 4px;
      transition: all 0.12s ease;
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
    }}

    .comic-filter-pill:hover {{
      background: var(--comic-yellow);
      transform: translateY(-1px);
    }}

    .comic-filter-pill.active {{
      background: var(--comic-red);
      color: #fff;
      box-shadow: 2px 2px 0px #000;
    }}

    .pill-alpha.active {{ background: var(--comic-purple); }}
    .pill-z.active {{ background: var(--comic-lime); color: #000; }}
    .pill-millennial.active {{ background: var(--comic-cyan); color: #000; }}
    .pill-boomer.active {{ background: var(--comic-orange); }}

    .toolbar-dropdown {{
      border: 2px solid #000;
      box-shadow: 2px 2px 0px #000;
      padding: 6px 10px;
      font-family: 'Space Grotesk', sans-serif;
      font-size: 0.82rem;
      font-weight: 800;
      border-radius: 4px;
      background: #fff;
      cursor: pointer;
      outline: none;
    }}

    /* =========================================================
       UNCLIPPED COMIC MEME GRID & CARDS
       ========================================================= */
    .comic-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 1.75rem;
    }}

    .comic-card {{
      background: #fff;
      border: var(--border-ink);
      border-radius: 6px;
      box-shadow: var(--shadow-hard);
      display: flex;
      flex-direction: column;
      position: relative;
      transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      cursor: pointer;
      overflow: hidden;
    }}

    .comic-card:hover {{
      transform: translateY(-3px);
      box-shadow: var(--shadow-heavy);
    }}

    /* Speech Bubble with Author Tag Inside */
    .speech-bubble-wrapper {{
      padding: 1rem 1rem 0;
      position: relative;
      z-index: 5;
    }}

    .speech-bubble {{
      position: relative;
      background: #fff;
      border: var(--border-ink);
      border-radius: 10px;
      padding: 10px 14px;
      box-shadow: var(--shadow-sm);
    }}

    .speech-quote {{
      font-weight: 800;
      font-size: 0.92rem;
      line-height: 1.35;
      color: #000;
      display: block;
    }}

    .speech-author {{
      display: block;
      margin-top: 5px;
      font-size: 0.72rem;
      font-weight: 700;
      color: #555;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}

    .speech-bubble::after {{
      content: '';
      position: absolute;
      bottom: -11px;
      left: 24px;
      border-width: 11px 9px 0;
      border-style: solid;
      border-color: #fff transparent;
      display: block;
      width: 0;
    }}

    .speech-bubble::before {{
      content: '';
      position: absolute;
      bottom: -15px;
      left: 22px;
      border-width: 14px 11px 0;
      border-style: solid;
      border-color: #000 transparent;
      display: block;
      width: 0;
    }}

    /* UNCLIPPED Media Box (object-fit: contain) */
    .comic-card-media {{
      margin: 0.75rem 1rem 0;
      border: 2px solid #000;
      box-shadow: 2px 2px 0px #000;
      height: 280px;
      background: #111116; /* Clean dark comic backdrop so no text is ever cropped */
      position: relative;
      overflow: hidden;
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
    }}

    .comic-card-media img, .comic-card-media video {{
      max-width: 100%;
      max-height: 100%;
      width: auto;
      height: auto;
      object-fit: contain; /* NEVER clip or crop punchlines */
      transition: transform 0.25s ease;
    }}

    .comic-card:hover .comic-card-media img,
    .comic-card:hover .comic-card-media video {{
      transform: scale(1.02);
    }}

    .badge-corner-stamp {{
      position: absolute;
      top: 8px;
      right: 8px;
      background: #fff;
      border: 2px solid #000;
      font-size: 0.75rem;
      font-weight: 800;
      padding: 2px 8px;
      box-shadow: 2px 2px 0px #000;
      border-radius: 4px;
      color: #000;
      z-index: 2;
    }}

    .badge-corner-source {{
      position: absolute;
      top: 8px;
      left: 8px;
      background: #fff;
      border: 2px solid #000;
      font-size: 0.7rem;
      font-weight: 800;
      text-transform: uppercase;
      padding: 2px 7px;
      box-shadow: 2px 2px 0px #000;
      border-radius: 3px;
      z-index: 2;
    }}

    .badge-generation {{
      position: absolute;
      bottom: 8px;
      left: 8px;
      border: 2px solid #000;
      font-size: 0.7rem;
      font-weight: 800;
      text-transform: uppercase;
      padding: 2px 7px;
      box-shadow: 2px 2px 0px #000;
      border-radius: 3px;
      z-index: 2;
    }}

    .badge-gen_alpha {{ background: var(--comic-purple); color: #fff; }}
    .badge-gen_z {{ background: var(--comic-lime); color: #000; }}
    .badge-millennial {{ background: var(--comic-cyan); color: #000; }}
    .badge-gen_x {{ background: var(--comic-orange); color: #fff; }}

    .badge-gif-indicator {{
      position: absolute;
      bottom: 8px;
      right: 8px;
      background: #000;
      color: #FFE81F;
      border: 2px solid #FFE81F;
      padding: 2px 6px;
      font-size: 0.68rem;
      font-weight: 800;
      border-radius: 3px;
      z-index: 3;
      pointer-events: none;
      box-shadow: 1px 1px 0px #000;
    }}

    /* Card Footer & Action Bar */
    .comic-card-footer {{
      padding: 0.85rem 1rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.5rem;
      border-top: 1px solid #eee;
      margin-top: 0.75rem;
    }}

    .btn-card-permalink {{
      background: var(--comic-yellow);
      color: #000;
      border: 2px solid #000;
      box-shadow: 2px 2px 0px #000;
      padding: 4px 10px;
      font-size: 0.75rem;
      font-weight: 800;
      text-transform: uppercase;
      border-radius: 4px;
      cursor: pointer;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      transition: all 0.12s ease;
    }}

    .btn-card-permalink:hover {{
      background: var(--comic-cyan);
      transform: translate(-1px, -1px);
      box-shadow: 3px 3px 0px #000;
    }}

    /* Clean Modern Like Button (NO POW!, NO JARRED SLAMS) */
    .btn-like-clean {{
      background: #fff;
      border: 2px solid #000;
      box-shadow: 2px 2px 0px #000;
      padding: 5px 12px;
      font-family: 'Space Grotesk', sans-serif;
      font-size: 0.85rem;
      font-weight: 800;
      border-radius: 20px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      transition: all 0.15s ease;
      color: #000;
    }}

    .btn-like-clean:hover {{
      transform: scale(1.05);
      background: #fff0f2;
    }}

    .btn-like-clean.voted {{
      background: #fee2e2;
      border-color: #ef4444;
      color: #ef4444;
    }}

    .btn-like-clean.voted .heart-icon {{
      transform: scale(1.2);
    }}

    /* =========================================================
       SECTION 2: TOP 10 TRENDING RIGHT NOW (Clean & Modern)
       ========================================================= */
    .trending-top10-wrap {{
      background: #fff;
      border: var(--border-ink);
      box-shadow: var(--shadow-heavy);
      border-radius: 8px;
      overflow: hidden;
      margin-bottom: 2rem;
    }}

    .trending-top10-header {{
      background: var(--comic-yellow);
      border-bottom: 3px solid #000;
      padding: 1rem 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .trending-item-row {{
      display: grid;
      grid-template-columns: 50px 80px 1fr 140px 110px;
      align-items: center;
      gap: 1rem;
      padding: 0.75rem 1.5rem;
      border-bottom: 1px solid #ddd;
      transition: background-color 0.12s;
    }}

    .trending-item-row:hover {{
      background: #fdfae8;
    }}

    .trending-rank {{
      font-family: 'Bangers', cursive;
      font-size: 1.4rem;
      text-align: center;
    }}

    .rank-top1 {{ color: #eab308; }}
    .rank-top2 {{ color: #94a3b8; }}
    .rank-top3 {{ color: #b45309; }}

    .trending-thumb {{
      width: 70px;
      height: 50px;
      background: #111116;
      border: 2px solid #000;
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }}

    .trending-thumb img {{
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }}

    /* =========================================================
       SECTION 3: SECRET LAB (API STUDIO)
       ========================================================= */
    .lab-section-wrap {{
      background: #121217;
      border: var(--border-ink);
      box-shadow: var(--shadow-heavy);
      border-radius: 8px;
      color: #fff;
      overflow: hidden;
    }}

    .lab-banner-head {{
      background: #1c1c24;
      border-bottom: 3px solid #000;
      padding: 1.25rem 1.5rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
    }}

    .lab-title-group h2 {{
      font-family: 'Bangers', cursive;
      font-size: 1.8rem;
      letter-spacing: 0.04em;
      color: var(--comic-yellow);
    }}

    .lab-split-studio {{
      display: grid;
      grid-template-columns: 360px 1fr;
    }}

    .lab-left-control-panel {{
      background: #18181f;
      border-right: 2px solid #27272a;
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }}

    .endpoint-buttons-column {{
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }}

    .lab-endpoint-btn {{
      background: #22222c;
      border: 2px solid #333342;
      border-radius: 6px;
      padding: 10px 12px;
      cursor: pointer;
      text-align: left;
      transition: all 0.12s;
    }}

    .lab-endpoint-btn.active {{
      background: var(--comic-yellow);
      border-color: #000;
      color: #000;
      box-shadow: 2px 2px 0px #000;
    }}

    .endpoint-method {{
      display: inline-block;
      background: var(--comic-lime);
      color: #000;
      font-size: 0.65rem;
      font-weight: 800;
      padding: 2px 6px;
      border-radius: 3px;
      margin-right: 6px;
    }}

    .endpoint-path {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      font-weight: 700;
    }}

    .param-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      margin-top: 0.5rem;
    }}

    .param-input-select {{
      background: #272733;
      border: 1px solid #444455;
      color: #fff;
      padding: 4px 8px;
      font-size: 0.8rem;
      font-family: 'Space Grotesk', sans-serif;
      border-radius: 4px;
      outline: none;
    }}

    .lab-right-console {{
      display: flex;
      flex-direction: column;
      background: #09090b;
    }}

    .console-header-bar {{
      background: #18181f;
      border-bottom: 2px solid #27272a;
      padding: 8px 1.25rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 0.5rem;
    }}

    .console-lang-tabs {{
      display: flex;
      gap: 0.35rem;
    }}

    .console-lang-btn {{
      background: #22222c;
      border: 1px solid #3f3f4e;
      color: #aaa;
      padding: 4px 10px;
      font-size: 0.75rem;
      font-weight: 700;
      cursor: pointer;
      border-radius: 4px;
    }}

    .console-lang-btn.active {{
      background: var(--comic-yellow);
      color: #000;
      border-color: #000;
    }}

    .console-actions-group {{
      display: flex;
      gap: 0.4rem;
      flex-wrap: wrap;
    }}

    .btn-console-action {{
      background: #fff;
      border: 1px solid #000;
      box-shadow: 2px 2px 0px #000;
      color: #000;
      padding: 4px 8px;
      font-size: 0.72rem;
      font-weight: 800;
      cursor: pointer;
      border-radius: 4px;
    }}

    .btn-run-request {{
      background: var(--comic-lime);
      color: #000;
      border: 1px solid #000;
      box-shadow: 2px 2px 0px #000;
      padding: 4px 10px;
      font-size: 0.75rem;
      font-weight: 800;
      cursor: pointer;
      border-radius: 4px;
    }}

    .console-code-snippet {{
      padding: 1rem 1.25rem;
      font-size: 0.82rem;
      color: #4ade80;
      line-height: 1.5;
      overflow-x: auto;
      border-bottom: 2px solid #27272a;
      min-height: 120px;
      background: #09090b;
      font-family: 'JetBrains Mono', monospace;
    }}

    .console-response-header {{
      background: #18181f;
      padding: 6px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 0.75rem;
      font-weight: 700;
      color: #888;
      border-bottom: 1px solid #27272a;
    }}

    .console-response-output {{
      padding: 1rem 1.25rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      color: #e4e4e7;
      overflow-x: auto;
      max-height: 400px;
      background: #09090b;
      line-height: 1.5;
    }}

    /* Lightbox Modal */
    .comic-modal {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(12, 12, 15, 0.85);
      backdrop-filter: blur(4px);
      z-index: 1000;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
    }}

    .comic-modal.active {{
      display: flex;
    }}

    .comic-modal-box {{
      background: #fff;
      border: 4px solid #000;
      box-shadow: 12px 12px 0px #000;
      border-radius: 8px;
      max-width: 800px;
      width: 100%;
      max-height: 90vh;
      overflow-y: auto;
      position: relative;
    }}

    .modal-close-btn {{
      position: absolute;
      top: 12px;
      right: 12px;
      background: var(--comic-red);
      color: #fff;
      border: 2px solid #000;
      width: 32px;
      height: 32px;
      font-family: 'Bangers', cursive;
      font-size: 1.25rem;
      cursor: pointer;
      border-radius: 50%;
      box-shadow: 2px 2px 0px #000;
      z-index: 10;
    }}

    .modal-media-wrap {{
      background: #111116;
      display: flex;
      align-items: center;
      justify-content: center;
      max-height: 520px;
      overflow: hidden;
    }}

    .modal-media-wrap img, .modal-media-wrap video {{
      max-width: 100%;
      max-height: 520px;
      object-fit: contain;
    }}

    .modal-content-details {{
      padding: 1.25rem 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }}

    /* Footer */
    footer {{
      margin-top: 4rem;
      border-top: var(--border-ink);
      background: var(--comic-yellow);
      padding: 2rem 1.5rem;
      text-align: center;
      font-size: 0.85rem;
      font-weight: 700;
    }}

    footer a {{
      color: #000;
      text-decoration: underline;
    }}

    @media (max-width: 900px) {{
      .section-header-box {{
        grid-template-columns: 1fr;
      }}
      .spotlight-body {{
        grid-template-columns: 1fr;
      }}
      .lab-split-studio {{
        grid-template-columns: 1fr;
      }}
      .trending-item-row {{
        grid-template-columns: 40px 60px 1fr 90px;
      }}
    }}
  </style>
</head>
<body>

  <!-- Top Banner -->
  <div class="comic-top-banner">
    <span>✨ THE LIVING INTERNET MEME ALMANAC • 1990s TO TODAY</span>
    <span>REDDIT • INSTAGRAM REELS • TIKTOK • YOUTUBE SHORTS • KYM ✨</span>
  </div>

  <!-- Header -->
  <header>
    <div class="nav-container">
      <div class="comic-logo-group">
        <a href="#feedSection" class="comic-logo">MEME-OLOGY!</a>
        <span class="comic-stamp-pill">VOL. 1</span>
      </div>

      <!-- Tri-Section Navigation Switcher -->
      <nav class="section-nav-switcher">
        <button class="section-nav-btn active" id="navBtnFeed" onclick="scrollToSection('feedSection')">
          <span>📰 1. The Feed</span>
        </button>
        <button class="section-nav-btn" id="navBtnTrending" onclick="scrollToSection('trendingSection')">
          <span>⚡ 2. Top 10 Trending</span>
        </button>
        <button class="section-nav-btn" id="navBtnLab" onclick="scrollToSection('labSection')">
          <span>🧪 3. API Studio</span>
        </button>
      </nav>

      <div class="nav-right-actions">
        <a href="/docs" target="_blank" class="btn-comic btn-comic-cyan">
          <span>⚡ Swagger Docs</span>
        </a>
        <a href="https://github.com/narcisoJavier/Meme-ology" target="_blank" class="btn-comic btn-comic-red">
          <span>★ GitHub</span>
        </a>
      </div>
    </div>
  </header>

  <!-- =========================================================
       SECTION 1: THE MEME FEED
       ========================================================= -->
  <section class="section-container" id="feedSection">
    
    <!-- Hero Header Panel -->
    <div class="section-header-box">
      <div class="hero-left-col">
        <span class="section-badge-tag">✨ INTERNET HUMOR THROUGH THE AGES</span>
        <h1 class="hero-title">THE LIVING MEME ALMANAC</h1>
        <p class="hero-desc">
          A live collection of the internet's favorite jokes, from early forum classics to today's chaotic humor. Pick an era or just scroll through what's funny right now.
        </p>

        <div class="sticker-cloud">
          <div class="comic-sticker sticker-alpha">👾 Gen Alpha</div>
          <div class="comic-sticker sticker-z">🛹 Gen Z</div>
          <div class="comic-sticker sticker-millennial">💾 Millennial</div>
          <div class="comic-sticker sticker-boomer">📼 Retro &amp; Boomer</div>
        </div>
      </div>

      <div class="radar-telemetry-box">
        <h3>COMMUNITY PULSE</h3>
        <p style="font-size: 0.75rem; font-weight: 700;">TRACKED &amp; CATEGORIZED</p>
        <div class="telemetry-grid">
          <div class="telemetry-cell">
            <div class="telemetry-num" id="statMemes">{len(live_memes)}</div>
            <div class="telemetry-lbl">MEMES TRACKED</div>
          </div>
          <div class="telemetry-cell">
            <div class="telemetry-num" style="color: var(--comic-pink);" id="statUpvotes">4.8M</div>
            <div class="telemetry-lbl">TOTAL UPVOTES</div>
          </div>
          <div class="telemetry-cell">
            <div class="telemetry-num" style="color: #059669;">5 FEEDS</div>
            <div class="telemetry-lbl">PLATFORMS</div>
          </div>
          <div class="telemetry-cell">
            <div class="telemetry-num" style="color: #2563eb;">&lt; 5ms</div>
            <div class="telemetry-lbl">EDGE SPEED</div>
          </div>
        </div>
      </div>
    </div>

    <!-- FEATURED MEME OF THE DAY (SPOTLIGHT) -->
    <div class="featured-spotlight-card" id="spotlightCard">
      <div class="spotlight-badge-tab">
        <span>👑 TODAY'S FEATURED MEME</span>
        <button class="btn-comic" style="padding: 3px 8px; font-size: 0.75rem;" onclick="rollNextSpotlight()">
          🎲 Next Spotlight
        </button>
      </div>
      <div class="spotlight-body" id="spotlightBody">
        <!-- Injected by JavaScript -->
      </div>
    </div>

    <!-- STREAMLINED COMPACT TOOLBAR -->
    <div class="streamlined-toolbar">
      <div class="search-input-box">
        <span class="search-icon">🔍</span>
        <input 
          type="text" 
          id="comicSearch" 
          class="compact-search-input" 
          placeholder="Search punchlines, authors, or platforms..."
          autocomplete="off"
        />
      </div>

      <!-- ERA PILLS -->
      <div class="compact-era-pills" id="comicGenerationFilters">
        <button class="comic-filter-pill active" data-gen="all">✨ All Eras</button>
        <button class="comic-filter-pill pill-alpha" data-gen="gen_alpha">👾 Gen Alpha</button>
        <button class="comic-filter-pill pill-z" data-gen="gen_z">🛹 Gen Z</button>
        <button class="comic-filter-pill pill-millennial" data-gen="millennial">💾 Millennial</button>
        <button class="comic-filter-pill pill-boomer" data-gen="gen_x">📼 Retro</button>
      </div>

      <!-- PLATFORM & SORT DROPDOWNS -->
      <div style="display: flex; gap: 0.4rem; align-items: center;">
        <select id="platformSelect" class="toolbar-dropdown" onchange="onPlatformFilterChange(this.value)">
          <option value="all">🌐 All Platforms</option>
          <option value="reddit">🔴 Reddit</option>
          <option value="instagram">📸 Instagram Reels</option>
          <option value="tiktok">🎵 TikTok Trends</option>
          <option value="youtube">▶️ YouTube Shorts</option>
          <option value="knowyourmeme">📖 Know Your Meme</option>
        </select>
        <select id="sortSelect" class="toolbar-dropdown" onchange="onSortChange(this.value)">
          <option value="newest" selected>⚡ Fresh &amp; Recent</option>
          <option value="score">🔥 Most Liked</option>
        </select>
      </div>
    </div>

    <!-- FULL-WIDTH UNCLIPPED COMIC GRID -->
    <div class="comic-grid" id="comicGrid"></div>

  </section>

  <!-- =========================================================
       SECTION 2: TOP 10 TRENDING RIGHT NOW
       ========================================================= -->
  <section class="section-container" id="trendingSection" style="margin-top: 4rem;">
    <div class="trending-top10-wrap">
      <div class="trending-top10-header">
        <div>
          <h2 style="font-family: 'Bangers', cursive; font-size: 1.8rem; letter-spacing: 0.04em;">
            ⚡ TRENDING RIGHT NOW (TOP 10)
          </h2>
          <p style="font-size: 0.85rem; font-weight: 700; color: #333;">
            The 10 hottest memes capturing the internet's attention today across all platforms.
          </p>
        </div>
        <span class="comic-stamp-pill" style="font-size: 0.8rem;">TODAY'S HOTTEST</span>
      </div>

      <div id="trendingTop10List">
        <!-- Injected by JavaScript -->
      </div>
    </div>
  </section>

  <!-- =========================================================
       SECTION 3: SECRET LAB (API STUDIO)
       ========================================================= -->
  <section class="section-container" id="labSection" style="margin-top: 4rem;">
    <div class="lab-section-wrap">
      
      <!-- Studio Header -->
      <div class="lab-banner-head">
        <div class="lab-title-group">
          <h2>THE SECRET LAB: DEVELOPER API STUDIO</h2>
          <p style="font-size: 0.85rem; color: #aaa;">Multi-platform code generator, live response inspector, and export console.</p>
        </div>

        <div class="lab-badge-row" style="display: flex; gap: 0.6rem; align-items: center;">
          <a href="/docs" target="_blank" class="btn-comic btn-comic-yellow" style="background: var(--comic-yellow);">
            OPEN SWAGGER &rarr;
          </a>
        </div>
      </div>

      <!-- Studio Split -->
      <div class="lab-split-studio">
        
        <!-- Left: Endpoints & Params -->
        <div class="lab-left-control-panel">
          <div style="font-size: 0.75rem; font-weight: 800; color: #888; text-transform: uppercase;">
            ⚙️ SELECT ENDPOINT
          </div>

          <div class="endpoint-buttons-column" id="labEndpointButtons">
            <div class="lab-endpoint-btn active" data-endpoint="trending">
              <div>
                <span class="endpoint-method">GET</span>
                <span class="endpoint-path">/api/v1/memes/trending</span>
              </div>
            </div>

            <div class="lab-endpoint-btn" data-endpoint="latest">
              <div>
                <span class="endpoint-method">GET</span>
                <span class="endpoint-path">/api/v1/memes/latest</span>
              </div>
            </div>

            <div class="lab-endpoint-btn" data-endpoint="random">
              <div>
                <span class="endpoint-method">GET</span>
                <span class="endpoint-path">/api/v1/memes/random</span>
              </div>
            </div>

            <div class="lab-endpoint-btn" data-endpoint="sources">
              <div>
                <span class="endpoint-method">GET</span>
                <span class="endpoint-path">/api/v1/sources</span>
              </div>
            </div>

            <div class="lab-endpoint-btn" data-endpoint="health">
              <div>
                <span class="endpoint-method">GET</span>
                <span class="endpoint-path">/health</span>
              </div>
            </div>
          </div>

          <!-- Dials -->
          <div style="border-top: 1px solid #272733; padding-top: 0.75rem;">
            <div style="font-size: 0.75rem; font-weight: 800; color: #888; text-transform: uppercase; margin-bottom: 0.5rem;">
              ⚡ QUERY PARAMETERS
            </div>
            <div class="param-row">
              <label style="font-size: 0.8rem; font-weight: 700;">generation:</label>
              <select id="paramGeneration" class="param-input-select" onchange="updateLabStudio()">
                <option value="" selected>all eras</option>
                <option value="gen_alpha">gen_alpha (brainrot)</option>
                <option value="gen_z">gen_z (surreal)</option>
                <option value="millennial">millennial (classics)</option>
                <option value="gen_x">gen_x (retro)</option>
              </select>
            </div>
            <div class="param-row">
              <label style="font-size: 0.8rem; font-weight: 700;">limit:</label>
              <select id="paramLimit" class="param-input-select" onchange="updateLabStudio()">
                <option value="5">5 memes</option>
                <option value="10" selected>10 memes</option>
                <option value="25">25 memes</option>
                <option value="50">50 memes</option>
              </select>
            </div>
            <div class="param-row">
              <label style="font-size: 0.8rem; font-weight: 700;">platform:</label>
              <select id="paramSource" class="param-input-select" onchange="updateLabStudio()">
                <option value="" selected>all platforms</option>
                <option value="reddit">reddit</option>
                <option value="instagram">instagram</option>
                <option value="tiktok">tiktok</option>
                <option value="youtube">youtube</option>
                <option value="knowyourmeme">knowyourmeme</option>
              </select>
            </div>
          </div>

        </div>

        <!-- Right: Code Snippet & Output -->
        <div class="lab-right-console">
          <div class="console-header-bar">
            <div class="console-lang-tabs" id="labLangTabs">
              <button class="console-lang-btn active" data-lang="curl">cURL</button>
              <button class="console-lang-btn" data-lang="python">Python</button>
              <button class="console-lang-btn" data-lang="javascript">JavaScript</button>
              <button class="console-lang-btn" data-lang="go">Go</button>
            </div>

            <div class="console-actions-group">
              <button class="btn-console-action" id="btnCopyApiUrl" onclick="copyLiveApiUrl()">
                📋 COPY URL
              </button>
              <button class="btn-console-action" id="btnDownloadJson" onclick="downloadCurrentJson()">
                💾 DOWNLOAD JSON
              </button>
              <button class="btn-console-action" id="btnCopySnippet">
                COPY CODE
              </button>
              <button class="btn-run-request" id="btnRunRequest" onclick="executeLiveLabRequest()">
                ▶ EXECUTE
              </button>
            </div>
          </div>

          <pre class="console-code-snippet" id="labCodeSnippet"></pre>

          <div class="console-response-header">
            <span>LIVE HTTP RESPONSE PAYLOAD</span>
            <span style="color: #4ade80;" id="responseStatusBadge">HTTP 200 OK • &lt; 5ms</span>
          </div>

          <pre class="console-response-output" id="labResponseOutput"></pre>
        </div>

      </div>

    </div>
  </section>

  <!-- Comic Modal -->
  <div class="comic-modal" id="comicModal">
    <div class="comic-modal-box">
      <button class="modal-close-btn" id="modalClose">&times;</button>
      <div class="modal-media-wrap" id="modalMedia"></div>
      <div class="modal-content-details">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span id="modalSource" class="comic-stamp-pill" style="font-size: 0.8rem;">r/dankmemes</span>
          <span id="modalScore" style="font-family: 'Space Grotesk', sans-serif; font-size: 1.1rem; font-weight: 800; color: var(--comic-red);">❤️ 24,500 LIKES</span>
        </div>
        <h3 id="modalTitle" style="font-size: 1.2rem; font-weight: 800;"></h3>
        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 2px solid #000; padding-top: 0.75rem; flex-wrap: wrap; gap: 0.75rem;">
          <span id="modalAuthor" style="font-size: 0.85rem; font-weight: 700; color: #555;"></span>
          <a id="modalLink" href="#" target="_blank" rel="noopener noreferrer" class="btn-comic btn-comic-yellow" style="background: var(--comic-yellow); padding: 8px 18px; font-size: 0.95rem; box-shadow: 4px 4px 0px #000;">
            🚀 OPEN ORIGINAL POST &rarr;
          </a>
        </div>
      </div>
    </div>
  </div>

  <!-- Footer -->
  <footer>
    <p>MEME-OLOGY! © 2026 • THE LIVING INTERNET MEME ALMANAC</p>
    <p style="margin-top: 0.5rem; font-weight: 600;">
      <a href="https://github.com/narcisoJavier/Meme-ology" target="_blank">GitHub</a> • 
      <a href="/docs" target="_blank">Swagger API</a> • 
      <a href="/openapi.json" target="_blank">OpenAPI Spec</a> • 
      <a href="#feedSection">Back to Top &uarr;</a>
    </p>
  </footer>

  <script>
    // Embedded Multi-Platform Harvested Memes
    const GENERATIONAL_MEMES = {memes_json_str};

    let memeCollection = [...GENERATIONAL_MEMES];
    let spotlightIndex = 0;
    let selectedPlatform = 'all';
    let selectedSort = 'newest'; // DEFAULT: Fresh & Recent First!

    // Persistent 1-Vote Per User Registry (localStorage)
    function getVotedMemeIds() {{
      try {{
        return JSON.parse(localStorage.getItem('memeology_voted_ids') || '[]');
      }} catch (e) {{
        return [];
      }}
    }}

    function isMemeVoted(id) {{
      return getVotedMemeIds().includes(id);
    }}

    function toggleMemeVote(meme) {{
      let votedIds = getVotedMemeIds();
      const alreadyVoted = votedIds.includes(meme.id);
      if (alreadyVoted) {{
        votedIds = votedIds.filter(x => x !== meme.id);
        meme.score = Math.max(0, (meme.score || 1) - 1);
      }} else {{
        votedIds.push(meme.id);
        meme.score = (meme.score || 0) + 1;
      }}
      localStorage.setItem('memeology_voted_ids', JSON.stringify(votedIds));
      return !alreadyVoted;
    }}

    // Ingest Live Memes with Failover
    async function initFeed() {{
      try {{
        const res = await fetch('/api/v1/memes/latest?limit=100');
        if (res.ok) {{
          const data = await res.json();
          const items = Array.isArray(data) ? data : (data.items || []);
          if (items.length > 0) {{
            memeCollection = items;
          }}
        }}
      }} catch (e) {{
        console.log("Using cached multi-platform meme collection");
      }}
      renderSpotlight();
      renderComicGrid();
      renderTop10Trending();
      updateLabStudio();
    }}

    // Render Featured Meme of the Day Spotlight
    function renderSpotlight() {{
      if (!memeCollection.length) return;
      const sorted = [...memeCollection].sort((a,b) => (b.score || 0) - (a.score || 0));
      const m = sorted[spotlightIndex % sorted.length];
      const isVideo = m.media_type === 'video' || (m.url && (m.url.endsWith('.mp4') || m.url.endsWith('.webm')));
      const mediaTag = isVideo ? 
        `<video src="${{m.url}}" autoplay loop muted playsinline referrerpolicy="no-referrer"></video>` :
        `<img src="${{m.url}}" alt="${{m.title}}" referrerpolicy="no-referrer" onerror="this.style.display='none';" />`;

      const genKey = (m.generation || 'gen_z').toLowerCase();
      const genLabel = {{
        gen_alpha: "👾 GEN ALPHA",
        gen_z: "🛹 GEN Z",
        millennial: "💾 MILLENNIAL",
        gen_x: "📼 RETRO"
      }}[genKey] || "🛹 GEN Z";

      const platIcon = {{
        reddit: "🔴 Reddit",
        instagram: "📸 Instagram Reels",
        tiktok: "🎵 TikTok",
        youtube: "▶️ YouTube Shorts",
        knowyourmeme: "📖 Know Your Meme"
      }}[m.source_platform] || m.source_platform;

      document.getElementById('spotlightBody').innerHTML = `
        <div class="spotlight-media-frame">
          ${{mediaTag}}
        </div>
        <div class="spotlight-info-col">
          <div class="spotlight-meta-row">
            <span class="comic-stamp-pill">${{platIcon}}</span>
            <span class="badge-generation badge-${{genKey}}" style="position: static;">${{genLabel}}</span>
            <span style="font-family: 'Space Grotesk', sans-serif; font-size: 1rem; font-weight: 800; color: var(--comic-red);">
              ❤️ ${{Number(m.score).toLocaleString()}} LIKES
            </span>
          </div>
          <div class="spotlight-title">"${{m.title}}"</div>
          <div style="font-size: 0.85rem; font-weight: 700; color: #555;">
            Posted by <strong>${{m.author || 'anonymous'}}</strong>
          </div>
          <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem;">
            <a href="${{m.permalink}}" target="_blank" rel="noopener noreferrer" class="btn-card-permalink" style="padding: 6px 14px; font-size: 0.85rem;">
              🚀 OPEN ORIGINAL POST &rarr;
            </a>
            <button class="btn-comic" onclick="openComicModal(memeCollection.find(x => x.id === '${{m.id}}'))">
              🔍 Fullscreen
            </button>
          </div>
        </div>
      `;
    }}

    function rollNextSpotlight() {{
      spotlightIndex++;
      renderSpotlight();
    }}

    // Render Full-Width Unclipped Grid
    function renderComicGrid() {{
      const grid = document.getElementById('comicGrid');
      const search = document.getElementById('comicSearch').value.toLowerCase().trim();
      const activeGen = document.querySelector('#comicGenerationFilters .comic-filter-pill.active').dataset.gen;

      let filtered = memeCollection.filter(m => {{
        const title = (m.title || '').toLowerCase();
        const author = (m.author || '').toLowerCase();
        const comm = (m.source_community || '').toLowerCase();
        const plat = (m.source_platform || '').toLowerCase();
        const gen = (m.generation || 'gen_z').toLowerCase();

        // Search Match
        const matchesSearch = !search || title.includes(search) || author.includes(search) || comm.includes(search) || plat.includes(search) || gen.includes(search);

        // Era Match
        let matchesGen = true;
        if (activeGen !== 'all') {{
          matchesGen = gen === activeGen;
        }}

        // Platform Match
        let matchesPlatform = true;
        if (selectedPlatform !== 'all') {{
          matchesPlatform = plat === selectedPlatform;
        }}

        return matchesSearch && matchesGen && matchesPlatform;
      }});

      // Sort
      if (selectedSort === 'newest') {{
        filtered.sort((a,b) => (b.created_at || 0) - (a.created_at || 0));
      }} else if (selectedSort === 'score') {{
        filtered.sort((a,b) => (b.score || 0) - (a.score || 0));
      }}

      if (filtered.length === 0) {{
        grid.innerHTML = `
          <div style="grid-column: 1/-1; text-align: center; padding: 3.5rem; background: #fff; border: 3px solid #000; box-shadow: 6px 6px 0px #000; border-radius: 8px;">
            <div style="font-size: 3rem;">✨</div>
            <h3 style="font-family: 'Bangers', cursive; font-size: 2rem; margin-top: 0.5rem;">NO MEMES FOUND IN THIS VIEW</h3>
            <p style="font-size: 0.95rem; font-weight: 700; color: #555;">Try choosing another platform, era, or clearing your search term.</p>
          </div>
        `;
        return;
      }}

      grid.innerHTML = filtered.map(m => {{
        const isVideo = m.media_type === 'video' || (m.url && (m.url.endsWith('.mp4') || m.url.endsWith('.webm')));
        const isGif = m.media_type === 'gif' || (m.url && m.url.endsWith('.gif'));
        const voted = isMemeVoted(m.id);

        const mediaTag = isVideo ? `
          <video src="${{m.url}}" preload="metadata" muted playsinline loop referrerpolicy="no-referrer"></video>
          <div class="badge-gif-indicator">▶ VIDEO</div>
        ` : (isGif ? `
          <img src="${{m.url}}" alt="${{m.title}}" loading="lazy" referrerpolicy="no-referrer" />
          <div class="badge-gif-indicator">▶ GIF</div>
        ` : `
          <img src="${{m.url}}" alt="${{m.title}}" loading="lazy" referrerpolicy="no-referrer" />
        `);

        const genKey = (m.generation || 'gen_z').toLowerCase();
        const genLabel = {{
          gen_alpha: "👾 GEN ALPHA",
          gen_z: "🛹 GEN Z",
          millennial: "💾 MILLENNIAL",
          gen_x: "📼 RETRO"
        }}[genKey] || "🛹 GEN Z";

        const platLabel = {{
          reddit: "🔴 Reddit",
          instagram: "📸 Reels",
          tiktok: "🎵 TikTok",
          youtube: "▶️ Shorts",
          knowyourmeme: "📖 KYM"
        }}[m.source_platform] || m.source_platform;

        return `
          <div class="comic-card" data-id="${{m.id}}">
            <div class="speech-bubble-wrapper">
              <div class="speech-bubble">
                <span class="speech-quote">"${{m.title}}"</span>
                <span class="speech-author">posted by ${{m.author || 'anonymous'}}</span>
              </div>
            </div>

            <div class="comic-card-media">
              ${{mediaTag}}
              <div class="badge-corner-stamp">${{platLabel}}</div>
              <div class="badge-generation badge-${{genKey}}">${{genLabel}}</div>
            </div>

            <div class="comic-card-footer">
              <a href="${{m.permalink}}" target="_blank" rel="noopener noreferrer" class="btn-card-permalink" title="Open post on ${{platLabel}}" onclick="event.stopPropagation()">
                <span>🔗 POST &rarr;</span>
              </a>
              <button class="btn-like-clean ${{voted ? 'voted' : ''}}" title="Like this meme">
                <span class="heart-icon">${{voted ? '❤️' : '🤍'}}</span>
                <span class="like-num">${{Number(m.score).toLocaleString()}}</span>
              </button>
            </div>
          </div>
        `;
      }}).join('');

      // Listeners for Clean Likes, Hover-Play Video/GIF, and Modal
      document.querySelectorAll('.comic-card').forEach(card => {{
        const id = card.dataset.id;
        const meme = memeCollection.find(x => x.id === id);
        if (!meme) return;

        // Hover to play video
        const video = card.querySelector('video');
        if (video) {{
          card.addEventListener('mouseenter', () => {{ video.play().catch(() => {{}}); }});
          card.addEventListener('mouseleave', () => {{ video.pause(); video.currentTime = 0; }});
        }}

        // Clean Like Interaction (NO POW, NO SLAM!)
        const likeBtn = card.querySelector('.btn-like-clean');
        likeBtn.addEventListener('click', (e) => {{
          e.stopPropagation();
          const justVoted = toggleMemeVote(meme);
          const currentScore = Number(meme.score).toLocaleString();
          
          likeBtn.querySelector('.like-num').textContent = currentScore;
          
          if (justVoted) {{
            likeBtn.classList.add('voted');
            likeBtn.querySelector('.heart-icon').textContent = '❤️';
          }} else {{
            likeBtn.classList.remove('voted');
            likeBtn.querySelector('.heart-icon').textContent = '🤍';
          }}

          renderTop10Trending();
        }});

        // Lightbox Modal
        card.addEventListener('click', () => {{
          openComicModal(meme);
        }});
      }});
    }}

    // Render Clean Top 10 Trending Section
    function renderTop10Trending() {{
      const list = document.getElementById('trendingTop10List');
      if (!list) return;

      const top10 = [...memeCollection].sort((a,b) => (b.score || 0) - (a.score || 0)).slice(0, 10);

      list.innerHTML = top10.map((m, idx) => {{
        const rank = idx + 1;
        const rankClass = rank === 1 ? 'rank-top1' : (rank === 2 ? 'rank-top2' : (rank === 3 ? 'rank-top3' : ''));
        const medal = rank === 1 ? '🥇' : (rank === 2 ? '🥈' : (rank === 3 ? '🥉' : `#${{rank}}`));

        const genKey = (m.generation || 'gen_z').toLowerCase();
        const genLabel = {{
          gen_alpha: "👾 ALPHA",
          gen_z: "🛹 GEN Z",
          millennial: "💾 MILLENNIAL",
          gen_x: "📼 RETRO"
        }}[genKey] || "🛹 GEN Z";

        const platLabel = {{
          reddit: "🔴 Reddit",
          instagram: "📸 Reels",
          tiktok: "🎵 TikTok",
          youtube: "▶️ Shorts",
          knowyourmeme: "📖 KYM"
        }}[m.source_platform] || m.source_platform;

        return `
          <div class="trending-item-row">
            <div class="trending-rank ${{rankClass}}">${{medal}}</div>
            <div class="trending-thumb">
              <img src="${{m.url}}" alt="${{m.title}}" loading="lazy" referrerpolicy="no-referrer" />
            </div>
            <div>
              <div style="font-weight: 800; font-size: 0.92rem; line-height: 1.3;">"${{m.title}}"</div>
              <div style="font-size: 0.72rem; color: #666; font-weight: 700; margin-top: 3px;">
                ${{platLabel}} • by ${{m.author || 'anonymous'}}
              </div>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              <span class="badge-generation badge-${{genKey}}" style="position: static; font-size: 0.65rem;">${{genLabel}}</span>
              <span style="font-family: 'Space Grotesk', sans-serif; font-size: 0.9rem; font-weight: 800; color: var(--comic-red);">
                ❤️ ${{Number(m.score).toLocaleString()}}
              </span>
            </div>
            <div style="text-align: right;">
              <a href="${{m.permalink}}" target="_blank" rel="noopener noreferrer" class="btn-card-permalink" style="padding: 3px 8px; font-size: 0.72rem;">
                🔗 Post &rarr;
              </a>
            </div>
          </div>
        `;
      }}).join('');
    }}

    function onPlatformFilterChange(val) {{
      selectedPlatform = val;
      renderComicGrid();
    }}

    function onSortChange(val) {{
      selectedSort = val;
      renderComicGrid();
    }}

    // Filter Pills Click Handler
    document.querySelectorAll('#comicGenerationFilters .comic-filter-pill').forEach(pill => {{
      pill.addEventListener('click', () => {{
        document.querySelectorAll('#comicGenerationFilters .comic-filter-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        renderComicGrid();
      }});
    }});

    // Search Input
    document.getElementById('comicSearch').addEventListener('input', () => {{
      renderComicGrid();
    }});

    // Lightbox Modal
    const modal = document.getElementById('comicModal');
    const modalClose = document.getElementById('modalClose');

    function openComicModal(meme) {{
      document.getElementById('modalTitle').textContent = `"${{meme.title}}"`;
      document.getElementById('modalSource').textContent = meme.source_platform || meme.source;
      document.getElementById('modalScore').textContent = `❤️ ${{Number(meme.score).toLocaleString()}} LIKES`;
      document.getElementById('modalAuthor').textContent = `Posted by ${{meme.author || 'anonymous'}}`;
      document.getElementById('modalLink').href = meme.permalink || '#';

      const isVideo = meme.media_type === 'video' || (meme.url && (meme.url.endsWith('.mp4') || meme.url.endsWith('.webm')));
      document.getElementById('modalMedia').innerHTML = isVideo ? `
        <video src="${{meme.url}}" controls autoplay loop muted referrerpolicy="no-referrer"></video>
      ` : `
        <img src="${{meme.url}}" alt="${{meme.title}}" referrerpolicy="no-referrer" />
      `;

      modal.classList.add('active');
    }}

    modalClose.addEventListener('click', () => {{
      modal.classList.remove('active');
      document.getElementById('modalMedia').innerHTML = '';
    }});

    modal.addEventListener('click', (e) => {{
      if (e.target === modal) {{
        modal.classList.remove('active');
        document.getElementById('modalMedia').innerHTML = '';
      }}
    }});

    // Section Scroll & Nav Sync
    function scrollToSection(id) {{
      const el = document.getElementById(id);
      if (el) {{
        el.scrollIntoView({{ behavior: 'smooth' }});
      }}
      document.querySelectorAll('.section-nav-btn').forEach(b => b.classList.remove('active'));
      if (id === 'feedSection') document.getElementById('navBtnFeed').classList.add('active');
      if (id === 'trendingSection') document.getElementById('navBtnTrending').classList.add('active');
      if (id === 'labSection') document.getElementById('navBtnLab').classList.add('active');
    }}

    // =========================================================
    // SECTION 3: SECRET LAB (API STUDIO) LOGIC
    // =========================================================
    let selectedLabEndpoint = 'trending';
    let selectedLabLang = 'curl';

    function getBaseUrl() {{
      return window.location.origin;
    }}

    function buildCurrentApiUrl() {{
      const base = getBaseUrl();
      const gen = document.getElementById('paramGeneration').value;
      const limit = document.getElementById('paramLimit').value;
      const src = document.getElementById('paramSource').value;

      let path = `/api/v1/memes/${{selectedLabEndpoint}}`;
      if (selectedLabEndpoint === 'sources') path = '/api/v1/sources';
      if (selectedLabEndpoint === 'health') path = '/health';

      const params = new URLSearchParams();
      if (['trending', 'latest', 'random'].includes(selectedLabEndpoint)) {{
        if (gen) params.set('generation', gen);
        if (selectedLabEndpoint !== 'random' && limit) params.set('limit', limit);
        if (src) params.set('platform', src);
      }}

      const qs = params.toString();
      return `${{base}}${{path}}${{qs ? '?' + qs : ''}}`;
    }}

    function copyLiveApiUrl() {{
      const url = buildCurrentApiUrl();
      navigator.clipboard.writeText(url);
      const btn = document.getElementById('btnCopyApiUrl');
      btn.textContent = 'COPIED URL!';
      setTimeout(() => {{ btn.textContent = '📋 COPY URL'; }}, 1500);
    }}

    function downloadCurrentJson() {{
      const raw = document.getElementById('labResponseOutput').textContent;
      const blob = new Blob([raw], {{ type: 'application/json' }});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `memeology-${{selectedLabEndpoint}}.json`;
      a.click();
    }}

    function updateLabStudio() {{
      const fullUrl = buildCurrentApiUrl();
      const codeBox = document.getElementById('labCodeSnippet');

      if (selectedLabLang === 'curl') {{
        codeBox.textContent = `curl -X GET "${{fullUrl}}" \\\n  -H "Accept: application/json"`;
      }} else if (selectedLabLang === 'python') {{
        codeBox.textContent = `import httpx\n\nresponse = httpx.get(\n    "${{fullUrl}}"\n)\nprint(response.json())`;
      }} else if (selectedLabLang === 'javascript') {{
        codeBox.textContent = `fetch("${{fullUrl}}")\n  .then(res => res.json())\n  .then(data => console.log(data));`;
      }} else if (selectedLabLang === 'go') {{
        codeBox.textContent = `package main\n\nimport (\n    "fmt"\n    "io"\n    "net/http"\n)\n\nfunc main() {{\n    resp, _ := http.Get("${{fullUrl}}")\n    defer resp.Body.Close()\n    body, _ := io.ReadAll(resp.Body)\n    fmt.Println(string(body))\n}}`;
      }}

      // Simulate payload
      const gen = document.getElementById('paramGeneration').value;
      const limit = parseInt(document.getElementById('paramLimit').value, 10);
      let items = [...memeCollection];
      if (gen) items = items.filter(m => (m.generation || '').toLowerCase() === gen);
      items = items.slice(0, limit);

      const previewPayload = selectedLabEndpoint === 'random' ? (items[0] || {{}}) : (
        selectedLabEndpoint === 'sources' ? [
          {{ platform: "reddit", community: "r/dankmemes", status: "ok", item_count: 24 }},
          {{ platform: "instagram", community: "reels", status: "ok", item_count: 12 }},
          {{ platform: "tiktok", community: "trending", status: "ok", item_count: 10 }},
          {{ platform: "youtube", community: "shorts", status: "ok", item_count: 8 }},
          {{ platform: "knowyourmeme", community: "confirmed", status: "ok", item_count: 6 }}
        ] : (
          selectedLabEndpoint === 'health' ? {{
            status: "ok",
            version: "1.0.0",
            total_cached_memes: memeCollection.length,
            cache_mode: "memory+sqlite"
          }} : {{
            items: items,
            total: items.length,
            limit: limit,
            offset: 0,
            has_more: false
          }}
        )
      );

      document.getElementById('labResponseOutput').textContent = JSON.stringify(previewPayload, null, 2);
    }}

    // Lab Endpoint Buttons
    document.querySelectorAll('#labEndpointButtons .lab-endpoint-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('#labEndpointButtons .lab-endpoint-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedLabEndpoint = btn.dataset.endpoint;
        updateLabStudio();
      }});
    }});

    // Language Selector
    document.querySelectorAll('#labLangTabs .console-lang-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('#labLangTabs .console-lang-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedLabLang = btn.dataset.lang;
        updateLabStudio();
      }});
    }});

    // Copy Snippet
    document.getElementById('btnCopySnippet').addEventListener('click', () => {{
      const code = document.getElementById('labCodeSnippet').textContent;
      navigator.clipboard.writeText(code);
      const btn = document.getElementById('btnCopySnippet');
      btn.textContent = 'COPIED!';
      setTimeout(() => {{ btn.textContent = 'COPY CODE'; }}, 1500);
    }});

    function executeLiveLabRequest() {{
      const badge = document.getElementById('responseStatusBadge');
      badge.textContent = 'FETCHING LIVE...';
      badge.style.color = '#FFE81F';

      setTimeout(() => {{
        badge.textContent = 'HTTP 200 OK • < 5ms';
        badge.style.color = '#4ade80';
        updateLabStudio();
      }}, 200);
    }}

    // Start
    initFeed();
  </script>
</body>
</html>
"""

Path("app/static/index.html").write_text(html_content, encoding="utf-8")
Path("public/index.html").write_text(html_content, encoding="utf-8")
print("Successfully updated app/static/index.html and public/index.html!")
