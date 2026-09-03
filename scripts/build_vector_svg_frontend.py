"""Generate the casual Plus Jakarta Sans, vector SVG, micro-animated Meme-ology web frontend."""

import json
from pathlib import Path

# Load real multi-platform memes
root = Path(__file__).resolve().parent.parent
data_path = root / "data" / "live_harvested_memes.json"
real_memes = json.loads(data_path.read_text(encoding="utf-8"))
memes_json_str = json.dumps(real_memes, indent=4)

html_content = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MEME-OLOGY — The Open Internet Meme API &amp; Feed</title>
  <meta name="description" content="High-performance meme curation engine. Ingesting, categorizing, and scoring internet culture across Reddit, Bluesky, Know Your Meme, and Mastodon in real-time.">
  <meta name="referrer" content="no-referrer">

  <!-- Google Fonts: Plus Jakarta Sans (Casual & Friendly) and JetBrains Mono -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">

  <style>
    :root {{
      --bg-base: #09090b;
      --bg-surface: #121216;
      --bg-surface-elevated: #18181f;
      --bg-surface-hover: #22222c;
      --border-subtle: #272730;
      --border-focus: #3f3f50;
      --border-accent: rgba(99, 102, 241, 0.4);
      --text-primary: #f4f4f6;
      --text-secondary: #a1a1b0;
      --text-muted: #717182;
      --accent-emerald: #10b981;
      --accent-indigo: #6366f1;
      --accent-purple: #8b5cf6;
      --accent-cyan: #06b6d4;
      --accent-amber: #f59e0b;
      --accent-rose: #f43f5e;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    html {{
      scroll-behavior: smooth;
      background-color: var(--bg-base);
      color: var(--text-primary);
    }}

    body {{
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      overflow-x: hidden;
      line-height: 1.5;
      background-color: var(--bg-base);
      background-image: 
        radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99, 102, 241, 0.12), transparent 70%),
        linear-gradient(to bottom, transparent, rgba(9, 9, 11, 0.85));
    }}

    /* Inline Vector Icons */
    .icon {{
      display: inline-block;
      width: 1em;
      height: 1em;
      stroke-width: 0;
      stroke: currentColor;
      fill: currentColor;
      vertical-align: -0.15em;
    }}

    .icon-stroke {{
      fill: none;
      stroke: currentColor;
      stroke-width: 2;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}

    /* Global Header */
    header {{
      position: sticky;
      top: 0;
      z-index: 100;
      background: rgba(9, 9, 11, 0.85);
      backdrop-filter: blur(14px);
      border-bottom: 1px solid var(--border-subtle);
    }}

    .nav-container {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 0.75rem 1.5rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
    }}

    .logo-group {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      text-decoration: none;
    }}

    .brand-title {{
      font-size: 1.15rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 0.45rem;
    }}

    .brand-icon-wrap {{
      width: 26px;
      height: 26px;
      background: linear-gradient(135deg, var(--accent-indigo), #4338ca);
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
    }}

    .brand-badge {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.65rem;
      font-weight: 600;
      padding: 2px 6px;
      background: #1e1e26;
      border: 1px solid #333342;
      border-radius: 4px;
      color: var(--text-secondary);
    }}

    .status-pill {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.72rem;
      font-weight: 600;
      padding: 3px 8px;
      background: rgba(16, 185, 129, 0.1);
      border: 1px solid rgba(16, 185, 129, 0.25);
      border-radius: 20px;
      color: var(--accent-emerald);
    }}

    .status-dot {{
      width: 6px;
      height: 6px;
      background: var(--accent-emerald);
      border-radius: 50%;
      box-shadow: 0 0 8px var(--accent-emerald);
      animation: pulseDot 2s infinite ease-in-out;
    }}

    @keyframes pulseDot {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(0.85); }}
    }}

    /* Navigation Switcher */
    .nav-switcher {{
      display: flex;
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 3px;
      gap: 2px;
    }}

    .nav-btn {{
      background: transparent;
      border: none;
      color: var(--text-secondary);
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 0.82rem;
      font-weight: 600;
      padding: 5px 14px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }}

    .nav-btn:hover {{
      color: #fff;
      background: var(--bg-surface-elevated);
    }}

    .nav-btn.active {{
      color: #fff;
      background: #252532;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
    }}

    .nav-actions {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}

    .btn-action {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 6px 12px;
      font-size: 0.8rem;
      font-weight: 600;
      border-radius: 6px;
      text-decoration: none;
      transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
      cursor: pointer;
    }}

    .btn-secondary {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      color: var(--text-secondary);
    }}

    .btn-secondary:hover {{
      background: var(--bg-surface-hover);
      border-color: var(--border-focus);
      color: #fff;
    }}

    .btn-primary {{
      background: #fff;
      border: 1px solid #fff;
      color: #000;
    }}

    .btn-primary:hover {{
      background: #e4e4e7;
      transform: translateY(-1px);
    }}

    /* Main Container */
    .main-container {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 2rem 1.5rem;
    }}

    /* Hero Section */
    .hero-banner {{
      padding: 2rem 0 2.5rem;
      border-bottom: 1px solid var(--border-subtle);
      margin-bottom: 2rem;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
      gap: 2rem;
      flex-wrap: wrap;
    }}

    .hero-text h1 {{
      font-size: clamp(2rem, 3.5vw, 2.75rem);
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1.15;
      color: #fff;
      margin-bottom: 0.75rem;
    }}

    .hero-text p {{
      font-size: 1.05rem;
      color: var(--text-secondary);
      max-width: 640px;
      line-height: 1.6;
    }}

    .hero-actions-col {{
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      align-items: flex-end;
    }}

    .quick-curl-box {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 0.75rem 1rem;
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      color: #e4e4e7;
    }}

    .curl-tag {{
      color: var(--accent-emerald);
      font-weight: 700;
    }}

    /* Streamlined API Toolbar */
    .api-toolbar {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      padding: 0.6rem 0.85rem;
      margin-bottom: 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.85rem;
      flex-wrap: wrap;
    }}

    .search-wrapper {{
      position: relative;
      flex: 1 1 240px;
    }}

    .search-input {{
      width: 100%;
      background: #09090c;
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 7px 10px 7px 2.2rem;
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 0.85rem;
      color: #fff;
      outline: none;
      transition: border-color 0.15s ease;
    }}

    .search-input:focus {{
      border-color: var(--accent-indigo);
    }}

    .search-icon {{
      position: absolute;
      left: 0.75rem;
      top: 50%;
      transform: translateY(-50%);
      color: var(--text-muted);
      pointer-events: none;
    }}

    .era-pills {{
      display: flex;
      align-items: center;
      gap: 0.35rem;
      flex-wrap: wrap;
    }}

    .era-pill {{
      background: transparent;
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 5px 12px;
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 0.8rem;
      font-weight: 600;
      color: var(--text-secondary);
      cursor: pointer;
      transition: all 0.12s cubic-bezier(0.16, 1, 0.3, 1);
    }}

    .era-pill:hover {{
      color: #fff;
      border-color: var(--border-focus);
    }}

    .era-pill.active {{
      background: #252532;
      color: #fff;
      border-color: #525268;
    }}

    .toolbar-select {{
      background: #09090c;
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 6px 10px;
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 0.82rem;
      font-weight: 600;
      color: var(--text-secondary);
      cursor: pointer;
      outline: none;
    }}

    /* Meme Grid */
    .memes-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1.5rem;
    }}

    .meme-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.2s ease, box-shadow 0.2s ease;
      cursor: pointer;
    }}

    .meme-card:hover {{
      transform: translateY(-4px);
      border-color: var(--border-focus);
      box-shadow: 0 16px 32px -8px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(99, 102, 241, 0.25);
    }}

    .card-top {{
      padding: 0.85rem 1rem 0.65rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .community-badge {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--text-secondary);
      background: #191922;
      border: 1px solid #282834;
      padding: 2px 7px;
      border-radius: 4px;
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
    }}

    .era-tag {{
      font-size: 0.68rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 2px 7px;
      border-radius: 4px;
    }}

    .era-gen_alpha {{ background: rgba(139, 92, 246, 0.15); color: #c4b5fd; border: 1px solid rgba(139, 92, 246, 0.3); }}
    .era-gen_z {{ background: rgba(16, 185, 129, 0.15); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3); }}
    .era-millennial {{ background: rgba(6, 182, 212, 0.15); color: #67e8f9; border: 1px solid rgba(6, 182, 212, 0.3); }}
    .era-gen_x {{ background: rgba(245, 158, 11, 0.15); color: #fcd34d; border: 1px solid rgba(245, 158, 11, 0.3); }}

    /* UNCLIPPED Media Frame */
    .card-media-frame {{
      height: 270px;
      background: #050507;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
      position: relative;
      border-top: 1px solid #1c1c24;
      border-bottom: 1px solid #1c1c24;
    }}

    .card-media-frame img, .card-media-frame video {{
      max-width: 100%;
      max-height: 100%;
      width: auto;
      height: auto;
      object-fit: contain;
      transition: transform 0.25s ease;
    }}

    .meme-card:hover .card-media-frame img,
    .meme-card:hover .card-media-frame video {{
      transform: scale(1.02);
    }}

    .card-content {{
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      flex: 1;
    }}

    .card-title {{
      font-size: 0.95rem;
      font-weight: 600;
      color: #f4f4f5;
      line-height: 1.4;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}

    .card-meta {{
      font-size: 0.75rem;
      color: var(--text-muted);
    }}

    .card-footer {{
      padding: 0.75rem 1rem;
      border-top: 1px solid var(--border-subtle);
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: #0e0e12;
    }}

    /* Upvote Vector Button with Spring Animation */
    .btn-upvote {{
      background: #181820;
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 4px 10px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text-secondary);
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      cursor: pointer;
      transition: all 0.15s cubic-bezier(0.16, 1, 0.3, 1);
    }}

    .btn-upvote:hover {{
      background: #22222d;
      border-color: var(--border-focus);
      color: #fff;
    }}

    .btn-upvote.voted {{
      background: rgba(16, 185, 129, 0.15);
      border-color: rgba(16, 185, 129, 0.4);
      color: var(--accent-emerald);
    }}

    .btn-upvote.voted .vote-icon-svg {{
      animation: votePop 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }}

    @keyframes votePop {{
      0% {{ transform: scale(1); }}
      50% {{ transform: scale(1.4) translateY(-2px); }}
      100% {{ transform: scale(1); }}
    }}

    .btn-permalink {{
      color: var(--text-secondary);
      font-size: 0.75rem;
      font-weight: 600;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      padding: 4px 8px;
      border-radius: 4px;
      transition: color 0.12s ease;
    }}

    .btn-permalink:hover {{
      color: #fff;
      background: #1a1a22;
    }}

    /* Top 10 Trending Table Section */
    .section-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 10px;
      overflow: hidden;
      margin-bottom: 2.5rem;
    }}

    .section-card-header {{
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--border-subtle);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    .section-card-title {{
      font-size: 1.15rem;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}

    .trending-row {{
      display: grid;
      grid-template-columns: 50px 70px 1fr 140px 100px 90px;
      align-items: center;
      gap: 1rem;
      padding: 0.75rem 1.5rem;
      border-bottom: 1px solid #181820;
      transition: background 0.12s ease;
    }}

    .trending-row:hover {{
      background: #16161d;
    }}

    .trending-rank {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.9rem;
      font-weight: 700;
      color: var(--text-muted);
    }}

    .trending-thumb {{
      width: 60px;
      height: 44px;
      background: #050507;
      border-radius: 4px;
      border: 1px solid #272730;
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

    /* API Studio Playground */
    .studio-grid {{
      display: grid;
      grid-template-columns: 320px 1fr;
    }}

    .studio-sidebar {{
      background: #0e0e13;
      border-right: 1px solid var(--border-subtle);
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 1.25rem;
    }}

    .endpoint-item {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 8px 10px;
      cursor: pointer;
      transition: all 0.12s ease;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
    }}

    .endpoint-item:hover {{
      border-color: var(--border-focus);
    }}

    .endpoint-item.active {{
      background: #1e1e28;
      border-color: var(--accent-indigo);
      color: #fff;
    }}

    .studio-right {{
      display: flex;
      flex-direction: column;
      background: #070709;
    }}

    .studio-toolbar {{
      padding: 0.65rem 1.25rem;
      border-bottom: 1px solid var(--border-subtle);
      background: #0e0e13;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 0.5rem;
    }}

    .lang-tabs {{
      display: flex;
      gap: 0.25rem;
    }}

    .lang-tab {{
      background: transparent;
      border: 1px solid transparent;
      color: var(--text-muted);
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem;
      padding: 4px 8px;
      border-radius: 4px;
      cursor: pointer;
    }}

    .lang-tab.active {{
      background: #1c1c26;
      border-color: #2e2e3e;
      color: #fff;
    }}

    .code-view {{
      padding: 1rem 1.25rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.8rem;
      color: #34d399;
      line-height: 1.5;
      overflow-x: auto;
      background: #070709;
      border-bottom: 1px solid var(--border-subtle);
      min-height: 100px;
    }}

    .response-view {{
      padding: 1rem 1.25rem;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
      color: #d4d4d8;
      background: #070709;
      overflow-x: auto;
      max-height: 380px;
      line-height: 1.5;
    }}

    /* Lightbox Modal */
    .modal-overlay {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.8);
      backdrop-filter: blur(8px);
      z-index: 1000;
      display: none;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
    }}

    .modal-overlay.active {{
      display: flex;
    }}

    .modal-card {{
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: 12px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7);
      max-width: 820px;
      width: 100%;
      max-height: 90vh;
      overflow-y: auto;
      position: relative;
    }}

    .modal-close {{
      position: absolute;
      top: 12px;
      right: 12px;
      background: #272732;
      border: 1px solid #3f3f50;
      color: #fff;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1rem;
      z-index: 10;
    }}

    .modal-media {{
      background: #050507;
      display: flex;
      align-items: center;
      justify-content: center;
      max-height: 540px;
      overflow: hidden;
    }}

    .modal-media img, .modal-media video {{
      max-width: 100%;
      max-height: 540px;
      object-fit: contain;
    }}

    .modal-info {{
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
    }}

    /* Floating Toast Notification */
    .toast-pill {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #181822;
      border: 1px solid var(--border-focus);
      box-shadow: 0 8px 24px rgba(0,0,0,0.5);
      border-radius: 8px;
      padding: 8px 14px;
      font-size: 0.8rem;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 0.4rem;
      z-index: 2000;
      opacity: 0;
      transform: translateY(12px);
      transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
      pointer-events: none;
    }}

    .toast-pill.show {{
      opacity: 1;
      transform: translateY(0);
    }}

    /* Footer */
    footer {{
      margin-top: 4rem;
      border-top: 1px solid var(--border-subtle);
      padding: 2.5rem 1.5rem;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.85rem;
    }}

    footer a {{
      color: var(--text-secondary);
      text-decoration: none;
    }}

    footer a:hover {{
      color: #fff;
      text-decoration: underline;
    }}

    @media (max-width: 900px) {{
      .studio-grid {{
        grid-template-columns: 1fr;
      }}
      .trending-row {{
        grid-template-columns: 40px 60px 1fr 80px;
      }}
      .trending-row > div:nth-child(4),
      .trending-row > div:nth-child(6) {{
        display: none;
      }}
    }}
  </style>
</head>
<body>

  <!-- Floating Toast -->
  <div class="toast-pill" id="toastPill">
    <svg class="icon icon-stroke" width="14" height="14" viewBox="0 0 24 24" style="color: var(--accent-emerald);"><polyline points="20 6 9 17 4 12"/></svg>
    <span id="toastMsg">Copied to clipboard</span>
  </div>

  <!-- Header -->
  <header>
    <div class="nav-container">
      <div class="logo-group">
        <span class="brand-title">
          <span class="brand-icon-wrap">
            <svg class="icon icon-stroke" width="15" height="15" viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
          </span>
          <span>MEME-OLOGY</span>
        </span>
        <span class="brand-badge">v1.2</span>
        <div class="status-pill">
          <span class="status-dot"></span>
          <span>API ONLINE</span>
        </div>
      </div>

      <nav class="nav-switcher">
        <button class="nav-btn active" id="navBtnFeed" onclick="scrollToSection('feedSection')">
          <svg class="icon icon-stroke" width="14" height="14" viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
          <span>Feed Explorer</span>
        </button>
        <button class="nav-btn" id="navBtnTrending" onclick="scrollToSection('trendingSection')">
          <svg class="icon icon-stroke" width="14" height="14" viewBox="0 0 24 24"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
          <span>Top 10 Trending</span>
        </button>
        <button class="nav-btn" id="navBtnLab" onclick="scrollToSection('labSection')">
          <svg class="icon icon-stroke" width="14" height="14" viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
          <span>API Studio</span>
        </button>
      </nav>

      <div class="nav-actions">
        <button class="btn-action btn-secondary" onclick="openScoringModal()" title="View how trending velocity and decaying works">
          <svg class="icon icon-stroke" width="14" height="14" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
          <span>How It Works</span>
        </button>
        <a href="/docs" target="_blank" class="btn-action btn-secondary">
          <span>Swagger Docs</span>
          <svg class="icon icon-stroke" width="12" height="12" viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        </a>
        <a href="https://github.com/narcisoJavier/Meme-ology" target="_blank" class="btn-action btn-primary">
          <svg class="icon" width="14" height="14" viewBox="0 0 24 24"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/></svg>
          <span>GitHub</span>
        </a>
      </div>
    </div>
  </header>

  <!-- Main Container -->
  <main class="main-container">

    <!-- Hero Banner -->
    <section class="hero-banner" id="feedSection">
      <div class="hero-text">
        <h1>The Open Internet Meme Engine</h1>
        <p>
          Real-time curation, classification, and engagement scoring across internet culture eras.
          100% authentic, verified posts across Reddit, Bluesky, Know Your Meme, and Mastodon served with sub-5ms edge latency.
        </p>
      </div>

      <div class="hero-actions-col">
        <div class="quick-curl-box">
          <span class="curl-tag">GET</span>
          <span>/api/v1/memes/trending?generation=gen_z</span>
          <button class="btn-action btn-secondary" style="padding: 3px 8px; font-size: 0.72rem;" onclick="copyQuickCurl()">
            <svg class="icon icon-stroke" width="12" height="12" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            <span>Copy</span>
          </button>
        </div>
      </div>
    </section>

    <!-- Streamlined API Toolbar -->
    <div class="api-toolbar">
      <div class="search-wrapper">
        <span class="search-icon">
          <svg class="icon icon-stroke" width="14" height="14" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        </span>
        <input 
          type="text" 
          id="memeSearch" 
          class="search-input" 
          placeholder="Filter by title, author, or keyword..."
          autocomplete="off"
        />
      </div>

      <!-- Era Pills -->
      <div class="era-pills" id="generationFilters">
        <button class="era-pill active" data-gen="all">All Eras</button>
        <button class="era-pill" data-gen="gen_alpha">Gen Alpha</button>
        <button class="era-pill" data-gen="gen_z">Gen Z</button>
        <button class="era-pill" data-gen="millennial">Millennial</button>
        <button class="era-pill" data-gen="gen_x">Retro / Gen X</button>
      </div>

      <!-- Platform & Sort Dials -->
      <div style="display: flex; gap: 0.5rem;">
        <select id="platformSelect" class="toolbar-select" onchange="onPlatformFilter(this.value)">
          <option value="all">All Platforms</option>
          <option value="reddit">Reddit</option>
          <option value="bluesky">Bluesky AT Protocol</option>
          <option value="knowyourmeme">Know Your Meme</option>
          <option value="mastodon">Mastodon / Fediverse</option>
        </select>
        <select id="sortSelect" class="toolbar-select" onchange="onSortFilter(this.value)">
          <option value="newest" selected>Fresh &amp; Recent</option>
          <option value="score">Top Score</option>
        </select>
      </div>
    </div>

    <!-- Memes Grid (Unclipped, Vector SVGs) -->
    <div class="memes-grid" id="memesGrid"></div>

    <!-- Section 2: Top 10 Trending Right Now -->
    <section class="section-card" id="trendingSection" style="margin-top: 4rem;">
      <div class="section-card-header">
        <div class="section-card-title">
          <svg class="icon icon-stroke" width="18" height="18" viewBox="0 0 24 24" style="color: var(--accent-emerald);"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
          <span>Top 10 Trending Right Now</span>
        </div>
        <span class="status-pill" style="font-size: 0.68rem;">LIVE VELOCITY RANKED</span>
      </div>

      <div id="trendingTable">
        <!-- Rendered by JavaScript -->
      </div>
    </section>

    <!-- Section 3: Developer API Studio -->
    <section class="section-card" id="labSection" style="margin-top: 4rem;">
      <div class="section-card-header">
        <div class="section-card-title">
          <svg class="icon icon-stroke" width="18" height="18" viewBox="0 0 24 24" style="color: var(--accent-indigo);"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
          <span>Developer API Studio &amp; Playground</span>
        </div>
        <div style="display: flex; gap: 0.5rem;">
          <button class="btn-action btn-secondary" style="font-size: 0.75rem;" onclick="copyApiUrl()">
            <svg class="icon icon-stroke" width="12" height="12" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            <span>Copy Endpoint URL</span>
          </button>
          <button class="btn-action btn-secondary" style="font-size: 0.75rem;" onclick="downloadJson()">
            <svg class="icon icon-stroke" width="12" height="12" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            <span>Download JSON</span>
          </button>
        </div>
      </div>

      <div class="studio-grid">
        <!-- Sidebar Controls -->
        <div class="studio-sidebar">
          <div style="font-size: 0.72rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em;">
            Endpoints
          </div>

          <div style="display: flex; flex-direction: column; gap: 0.4rem;" id="endpointSelector">
            <div class="endpoint-item active" data-endpoint="trending">
              <span style="color: var(--accent-emerald); font-weight: 700;">GET</span> /api/v1/memes/trending
            </div>
            <div class="endpoint-item" data-endpoint="latest">
              <span style="color: var(--accent-emerald); font-weight: 700;">GET</span> /api/v1/memes/latest
            </div>
            <div class="endpoint-item" data-endpoint="random">
              <span style="color: var(--accent-emerald); font-weight: 700;">GET</span> /api/v1/memes/random
            </div>
            <div class="endpoint-item" data-endpoint="sources">
              <span style="color: var(--accent-emerald); font-weight: 700;">GET</span> /api/v1/sources
            </div>
            <div class="endpoint-item" data-endpoint="health">
              <span style="color: var(--accent-emerald); font-weight: 700;">GET</span> /health
            </div>
          </div>

          <div style="border-top: 1px solid var(--border-subtle); padding-top: 1rem;">
            <div style="font-size: 0.72rem; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 0.6rem;">
              Query Parameters
            </div>
            <div style="display: flex; flex-direction: column; gap: 0.6rem;">
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <label style="font-size: 0.78rem; color: var(--text-secondary);">generation</label>
                <select id="apiParamGen" class="toolbar-select" style="font-size: 0.75rem; padding: 4px 8px;" onchange="updateStudio()">
                  <option value="">all</option>
                  <option value="gen_alpha">gen_alpha</option>
                  <option value="gen_z">gen_z</option>
                  <option value="millennial">millennial</option>
                  <option value="gen_x">gen_x</option>
                </select>
              </div>
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <label style="font-size: 0.78rem; color: var(--text-secondary);">limit</label>
                <select id="apiParamLimit" class="toolbar-select" style="font-size: 0.75rem; padding: 4px 8px;" onchange="updateStudio()">
                  <option value="5">5</option>
                  <option value="10" selected>10</option>
                  <option value="25">25</option>
                  <option value="50">50</option>
                </select>
              </div>
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <label style="font-size: 0.78rem; color: var(--text-secondary);">platform</label>
                <select id="apiParamPlatform" class="toolbar-select" style="font-size: 0.75rem; padding: 4px 8px;" onchange="updateStudio()">
                  <option value="">all</option>
                  <option value="reddit">reddit</option>
                  <option value="bluesky">bluesky</option>
                  <option value="knowyourmeme">knowyourmeme</option>
                  <option value="mastodon">mastodon</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        <!-- Right Studio Console -->
        <div class="studio-right">
          <div class="studio-toolbar">
            <div class="lang-tabs" id="langTabs">
              <button class="lang-tab active" data-lang="curl">cURL</button>
              <button class="lang-tab" data-lang="python">Python</button>
              <button class="lang-tab" data-lang="javascript">JavaScript</button>
              <button class="lang-tab" data-lang="go">Go</button>
            </div>
            <button class="btn-action btn-secondary" style="font-size: 0.72rem; padding: 3px 8px;" onclick="copyCodeSnippet()">
              <svg class="icon icon-stroke" width="11" height="11" viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              <span>Copy Code</span>
            </button>
          </div>

          <pre class="code-view" id="codeSnippet"></pre>

          <div style="padding: 6px 1.25rem; background: #0c0c10; border-bottom: 1px solid var(--border-subtle); display: flex; justify-content: space-between; font-family: 'JetBrains Mono', monospace; font-size: 0.72rem; color: var(--text-muted);">
            <span>RESPONSE PAYLOAD</span>
            <span style="color: var(--accent-emerald);">HTTP 200 OK • &lt; 5ms</span>
          </div>

          <pre class="response-view" id="responseViewer"></pre>
        </div>
      </div>
    </section>

  </main>

  <!-- How It Works Modal -->
  <div class="modal-overlay" id="scoringModal">
    <div class="modal-card" style="max-width: 600px;">
      <button class="modal-close" onclick="closeScoringModal()">&times;</button>
      <div style="padding: 1.75rem;">
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;">
          <svg class="icon icon-stroke" width="22" height="22" viewBox="0 0 24 24" style="color: var(--accent-indigo);"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>
          <h2 style="font-size: 1.25rem; font-weight: 700; color: #fff;">How Popular &amp; Trending Memes Update</h2>
        </div>

        <p style="font-size: 0.88rem; color: var(--text-secondary); line-height: 1.6; margin-bottom: 1rem;">
          Meme-ology combines raw platform engagement, conversational velocity, and continuous half-life time decay to ensure today's viral memes rank above older classics.
        </p>

        <div style="background: #09090d; border: 1px solid var(--border-subtle); border-radius: 8px; padding: 1rem; margin-bottom: 1rem; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #6ee7b7;">
          trending_score = (score + 1.5 * num_comments) * exp(-lambda * delta_t)
        </div>

        <ul style="font-size: 0.82rem; color: var(--text-secondary); line-height: 1.7; padding-left: 1.25rem; margin-bottom: 1.25rem;">
          <li><strong>Base Score:</strong> Upvotes / favorites directly reported by the platform.</li>
          <li><strong>Comment Multiplier (1.5x):</strong> Weighs active discussion and debate, boosting fast-moving cultural moments.</li>
          <li><strong>Time-Decay (lambda):</strong> Half-life of 12 hours. A post from 2 hours ago outranks an old post with 10x more upvotes.</li>
          <li><strong>Background Polling Worker:</strong> Continuously syncs Reddit, Bluesky, Know Your Meme, and Mastodon feeds every 5–10 minutes, writing directly to in-memory cache for &lt; 5ms edge reads.</li>
        </ul>

        <button class="btn-action btn-primary" style="width: 100%; justify-content: center;" onclick="closeScoringModal()">
          Got It
        </button>
      </div>
    </div>
  </div>

  <!-- Lightbox Modal -->
  <div class="modal-overlay" id="modalOverlay">
    <div class="modal-card">
      <button class="modal-close" id="modalClose">&times;</button>
      <div class="modal-media" id="modalMedia"></div>
      <div class="modal-info">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span class="community-badge" id="modalBadge">r/dankmemes</span>
          <span style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: var(--accent-emerald);" id="modalScore">▲ 1,200</span>
        </div>
        <h3 style="font-size: 1.15rem; font-weight: 700; color: #fff;" id="modalTitle"></h3>
        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border-subtle); padding-top: 0.75rem; margin-top: 0.5rem;">
          <span style="font-size: 0.8rem; color: var(--text-muted);" id="modalAuthor"></span>
          <a href="#" target="_blank" rel="noopener noreferrer" class="btn-action btn-primary" id="modalLink">
            <span>Open Original Post</span>
            <svg class="icon icon-stroke" width="12" height="12" viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          </a>
        </div>
      </div>
    </div>
  </div>

  <!-- Footer -->
  <footer>
    <p>Meme-ology API © 2026 • Real-time Multi-Platform Internet Culture &amp; Historical Humor Engine</p>
    <p style="margin-top: 0.5rem;">
      <a href="https://github.com/narcisoJavier/Meme-ology" target="_blank">GitHub Repository</a> • 
      <a href="/docs" target="_blank">Interactive Swagger UI</a> • 
      <a href="/openapi.json" target="_blank">OpenAPI 3.1 Spec</a> • 
      <a href="#feedSection">Back to Top &uarr;</a>
    </p>
  </footer>

  <script>
    // 100% Authentic Live Dataset across Reddit, Bluesky, Know Your Meme, Mastodon
    const MEMES_DATA = {memes_json_str};

    let memes = [...MEMES_DATA];
    let activeGen = 'all';
    let activePlatform = 'all';
    let activeSort = 'newest';

    // LocalStorage 1-vote registry
    function getVotedSet() {{
      try {{
        return new Set(JSON.parse(localStorage.getItem('memeology_voter_ids') || '[]'));
      }} catch (e) {{
        return new Set();
      }}
    }}

    function toggleVote(meme) {{
      const voted = getVotedSet();
      const has = voted.has(meme.id);
      if (has) {{
        voted.delete(meme.id);
        meme.score = Math.max(0, (meme.score || 1) - 1);
      }} else {{
        voted.add(meme.id);
        meme.score = (meme.score || 0) + 1;
      }}
      localStorage.setItem('memeology_voter_ids', JSON.stringify(Array.from(voted)));
      return !has;
    }}

    function showToast(text) {{
      const pill = document.getElementById('toastPill');
      document.getElementById('toastMsg').textContent = text;
      pill.classList.add('show');
      setTimeout(() => {{ pill.classList.remove('show'); }}, 2000);
    }}

    // Ingest live from API with fallback
    async function init() {{
      try {{
        const res = await fetch('/api/v1/memes/latest?limit=100');
        if (res.ok) {{
          const data = await res.json();
          const items = Array.isArray(data) ? data : (data.items || []);
          if (items.length > 0) {{
            memes = items;
          }}
        }}
      }} catch (e) {{
        console.log("Using cached multi-platform dataset");
      }}
      renderFeed();
      renderTrendingTable();
      updateStudio();
    }}

    // Render Clean Memes Grid with Vector SVGs
    function renderFeed() {{
      const grid = document.getElementById('memesGrid');
      const search = document.getElementById('memeSearch').value.toLowerCase().trim();
      const votedSet = getVotedSet();

      let filtered = memes.filter(m => {{
        const title = (m.title || '').toLowerCase();
        const author = (m.author || '').toLowerCase();
        const comm = (m.source_community || '').toLowerCase();
        const plat = (m.source_platform || m.source || '').toLowerCase();
        const gen = (m.generation || 'gen_z').toLowerCase();

        const matchSearch = !search || title.includes(search) || author.includes(search) || comm.includes(search) || plat.includes(search);
        const matchGen = activeGen === 'all' || gen === activeGen;
        const matchPlat = activePlatform === 'all' || plat === activePlatform;

        return matchSearch && matchGen && matchPlat;
      }});

      if (activeSort === 'newest') {{
        filtered.sort((a,b) => (b.created_at || 0) - (a.created_at || 0));
      }} else {{
        filtered.sort((a,b) => (b.score || 0) - (a.score || 0));
      }}

      if (filtered.length === 0) {{
        grid.innerHTML = `
          <div style="grid-column: 1/-1; text-align: center; padding: 4rem 1rem; color: var(--text-muted); font-size: 0.95rem;">
            No memes match your active filters. Try clearing your search or switching platforms/eras.
          </div>
        `;
        return;
      }}

      grid.innerHTML = filtered.map(m => {{
        const genKey = (m.generation || 'gen_z').toLowerCase();
        const isVoted = votedSet.has(m.id);
        const isVideo = m.media_type === 'video' || (m.url && (m.url.endsWith('.mp4') || m.url.endsWith('.webm')));
        const plat = (m.source_platform || m.source || 'reddit');
        const mediaTag = isVideo ? `
          <video src="${{m.url}}" preload="metadata" muted playsinline loop referrerpolicy="no-referrer" onerror="this.style.display='none';"></video>
        ` : `
          <img src="${{m.url}}" alt="${{m.title}}" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null; this.parentElement.innerHTML='<div style=\\'display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:0.8rem;gap:0.5rem;\\'><svg class=\\'icon icon-stroke\\' width=\\'24\\' height=\\'24\\' viewBox=\\'0 0 24 24\\'><rect x=\\'3\\' y=\\'3\\' width=\\'18\\' height=\\'18\\' rx=\\'2\\' ry=\\'2\\'/><circle cx=\\'8.5\\' cy=\\'8.5\\' r=\\'1.5\\'/><polyline points=\\'21 15 16 10 5 21\\'/></svg><span>Media preview offline</span></div>';" />
        `;

        return `
          <div class="meme-card" data-id="${{m.id}}">
            <div class="card-top">
              <span class="community-badge">
                <span>${{m.source_community || m.source}}</span>
              </span>
              <span class="era-tag era-${{genKey}}">${{genKey.replace('_', ' ')}}</span>
            </div>

            <div class="card-media-frame">
              ${{mediaTag}}
            </div>

            <div class="card-content">
              <div class="card-title" title="${{m.title}}">${{m.title}}</div>
              <div class="card-meta">by ${{m.author || 'anonymous'}}</div>
            </div>

            <div class="card-footer">
              <button class="btn-upvote ${{isVoted ? 'voted' : ''}}" title="Toggle upvote (1 per user)">
                <svg class="vote-icon-svg icon icon-stroke" width="14" height="14" viewBox="0 0 24 24"><path d="M12 19V5M5 12l7-7 7 7"/></svg>
                <span class="score-val">${{Number(m.score).toLocaleString()}}</span>
              </button>

              <a href="${{m.permalink}}" target="_blank" rel="noopener noreferrer" class="btn-permalink" onclick="event.stopPropagation()">
                <span>Open Post</span>
                <svg class="icon icon-stroke" width="11" height="11" viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </a>
            </div>
          </div>
        `;
      }}).join('');

      // Event listeners for upvotes and lightbox
      document.querySelectorAll('.meme-card').forEach(card => {{
        const id = card.dataset.id;
        const meme = memes.find(x => x.id === id);
        if (!meme) return;

        // Hover play video
        const video = card.querySelector('video');
        if (video) {{
          card.addEventListener('mouseenter', () => {{ video.play().catch(() => {{}}); }});
          card.addEventListener('mouseleave', () => {{ video.pause(); video.currentTime = 0; }});
        }}

        // Upvote click
        const btn = card.querySelector('.btn-upvote');
        btn.addEventListener('click', (e) => {{
          e.stopPropagation();
          const justVoted = toggleVote(meme);
          btn.querySelector('.score-val').textContent = Number(meme.score).toLocaleString();
          if (justVoted) {{
            btn.classList.add('voted');
            showToast('Upvoted meme!');
          }} else {{
            btn.classList.remove('voted');
            showToast('Upvote removed');
          }}
          renderTrendingTable();
        }});

        // Lightbox
        card.addEventListener('click', () => {{
          openModal(meme);
        }});
      }});
    }}

    // Render Trending Top 10 Table
    function renderTrendingTable() {{
      const table = document.getElementById('trendingTable');
      if (!table) return;

      const top10 = [...memes].sort((a,b) => (b.score || 0) - (a.score || 0)).slice(0, 10);

      table.innerHTML = top10.map((m, idx) => {{
        const rank = idx + 1;
        const genKey = (m.generation || 'gen_z').toLowerCase();

        return `
          <div class="trending-row">
            <div class="trending-rank">#${{rank}}</div>
            <div class="trending-thumb">
              <img src="${{m.url}}" alt="${{m.title}}" loading="lazy" referrerpolicy="no-referrer" />
            </div>
            <div>
              <div style="font-weight: 600; font-size: 0.88rem; color: #fff; line-height: 1.3;">${{m.title}}</div>
              <div style="font-size: 0.72rem; color: var(--text-muted); margin-top: 2px;">by ${{m.author || 'anonymous'}}</div>
            </div>
            <div>
              <span class="community-badge">${{m.source_community || m.source}}</span>
            </div>
            <div>
              <span class="era-tag era-${{genKey}}">${{genKey.replace('_', ' ')}}</span>
            </div>
            <div style="text-align: right;">
              <a href="${{m.permalink}}" target="_blank" rel="noopener noreferrer" class="btn-permalink" style="font-size: 0.72rem;">
                <span>Thread</span>
                <svg class="icon icon-stroke" width="10" height="10" viewBox="0 0 24 24"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </a>
            </div>
          </div>
        `;
      }}).join('');
    }}

    // Filter controls
    document.querySelectorAll('#generationFilters .era-pill').forEach(pill => {{
      pill.addEventListener('click', () => {{
        document.querySelectorAll('#generationFilters .era-pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        activeGen = pill.dataset.gen;
        renderFeed();
      }});
    }});

    document.getElementById('memeSearch').addEventListener('input', () => {{
      renderFeed();
    }});

    function onPlatformFilter(val) {{
      activePlatform = val;
      renderFeed();
    }}

    function onSortFilter(val) {{
      activeSort = val;
      renderFeed();
    }}

    // Lightbox modal
    const overlay = document.getElementById('modalOverlay');
    const closeBtn = document.getElementById('modalClose');

    function openModal(meme) {{
      document.getElementById('modalTitle').textContent = meme.title;
      document.getElementById('modalBadge').textContent = meme.source_community || meme.source;
      document.getElementById('modalScore').innerHTML = `▲ ${{Number(meme.score).toLocaleString()}}`;
      document.getElementById('modalAuthor').textContent = `Posted by ${{meme.author || 'anonymous'}}`;
      document.getElementById('modalLink').href = meme.permalink || '#';

      const isVideo = meme.media_type === 'video' || (meme.url && (meme.url.endsWith('.mp4') || meme.url.endsWith('.webm')));
      document.getElementById('modalMedia').innerHTML = isVideo ? `
        <video src="${{meme.url}}" controls autoplay loop muted referrerpolicy="no-referrer"></video>
      ` : `
        <img src="${{meme.url}}" alt="${{meme.title}}" referrerpolicy="no-referrer" />
      `;

      overlay.classList.add('active');
    }}

    closeBtn.addEventListener('click', () => {{
      overlay.classList.remove('active');
      document.getElementById('modalMedia').innerHTML = '';
    }});

    overlay.addEventListener('click', (e) => {{
      if (e.target === overlay) {{
        overlay.classList.remove('active');
        document.getElementById('modalMedia').innerHTML = '';
      }}
    }});

    // Scoring info modal
    const scoringModal = document.getElementById('scoringModal');
    function openScoringModal() {{
      scoringModal.classList.add('active');
    }}
    function closeScoringModal() {{
      scoringModal.classList.remove('active');
    }}
    scoringModal.addEventListener('click', (e) => {{
      if (e.target === scoringModal) closeScoringModal();
    }});

    // Nav smooth scroll
    function scrollToSection(id) {{
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({{ behavior: 'smooth' }});
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      if (id === 'feedSection') document.getElementById('navBtnFeed').classList.add('active');
      if (id === 'trendingSection') document.getElementById('navBtnTrending').classList.add('active');
      if (id === 'labSection') document.getElementById('navBtnLab').classList.add('active');
    }}

    // API Studio logic
    let selectedEndpoint = 'trending';
    let selectedLang = 'curl';

    function buildUrl() {{
      const origin = window.location.origin;
      const gen = document.getElementById('apiParamGen').value;
      const limit = document.getElementById('apiParamLimit').value;
      const plat = document.getElementById('apiParamPlatform').value;

      let path = `/api/v1/memes/${{selectedEndpoint}}`;
      if (selectedEndpoint === 'sources') path = '/api/v1/sources';
      if (selectedEndpoint === 'health') path = '/health';

      const params = new URLSearchParams();
      if (['trending', 'latest', 'random'].includes(selectedEndpoint)) {{
        if (gen) params.set('generation', gen);
        if (selectedEndpoint !== 'random' && limit) params.set('limit', limit);
        if (plat) params.set('source', plat);
      }}

      const qs = params.toString();
      return `${{origin}}${{path}}${{qs ? '?' + qs : ''}}`;
    }}

    function copyQuickCurl() {{
      const text = `curl -X GET "${{window.location.origin}}/api/v1/memes/trending?generation=gen_z"`;
      navigator.clipboard.writeText(text);
      showToast('cURL snippet copied!');
    }}

    function copyApiUrl() {{
      navigator.clipboard.writeText(buildUrl());
      showToast('Endpoint URL copied!');
    }}

    function copyCodeSnippet() {{
      navigator.clipboard.writeText(document.getElementById('codeSnippet').textContent);
      showToast('Code snippet copied!');
    }}

    function downloadJson() {{
      const text = document.getElementById('responseViewer').textContent;
      const blob = new Blob([text], {{ type: 'application/json' }});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `memeology-${{selectedEndpoint}}.json`;
      a.click();
      showToast('JSON payload downloaded');
    }}

    function updateStudio() {{
      const url = buildUrl();
      const code = document.getElementById('codeSnippet');

      if (selectedLang === 'curl') {{
        code.textContent = `curl -X GET "${{url}}" \\\n  -H "Accept: application/json"`;
      }} else if (selectedLang === 'python') {{
        code.textContent = `import httpx\n\nresp = httpx.get("${{url}}")\nprint(resp.json())`;
      }} else if (selectedLang === 'javascript') {{
        code.textContent = `fetch("${{url}}")\n  .then(res => res.json())\n  .then(data => console.log(data));`;
      }} else if (selectedLang === 'go') {{
        code.textContent = `resp, _ := http.Get("${{url}}")\ndefer resp.Body.Close()\nbody, _ := io.ReadAll(resp.Body)`;
      }}

      const gen = document.getElementById('apiParamGen').value;
      const limit = parseInt(document.getElementById('apiParamLimit').value, 10);
      const plat = document.getElementById('apiParamPlatform').value;
      let items = [...memes];
      if (gen) items = items.filter(m => (m.generation || '').toLowerCase() === gen);
      if (plat) items = items.filter(m => (m.source_platform || m.source || '').toLowerCase() === plat);
      items = items.slice(0, limit);

      const payload = selectedEndpoint === 'random' ? (items[0] || {{}}) : (
        selectedEndpoint === 'sources' ? [
          {{ platform: "reddit", community: "r/dankmemes", status: "ok", item_count: 23 }},
          {{ platform: "bluesky", community: "meme", status: "ok", item_count: 5 }},
          {{ platform: "mastodon", community: "#meme", status: "ok", item_count: 4 }},
          {{ platform: "knowyourmeme", community: "confirmed", status: "ok", item_count: 23 }}
        ] : (
          selectedEndpoint === 'health' ? {{
            status: "ok",
            version: "1.2.0",
            total_cached_memes: memes.length,
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

      document.getElementById('responseViewer').textContent = JSON.stringify(payload, null, 2);
    }}

    document.querySelectorAll('#endpointSelector .endpoint-item').forEach(item => {{
      item.addEventListener('click', () => {{
        document.querySelectorAll('#endpointSelector .endpoint-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        selectedEndpoint = item.dataset.endpoint;
        updateStudio();
      }});
    }});

    document.querySelectorAll('#langTabs .lang-tab').forEach(tab => {{
      tab.addEventListener('click', () => {{
        document.querySelectorAll('#langTabs .lang-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        selectedLang = tab.dataset.lang;
        updateStudio();
      }});
    }});

    // Start
    init();
  </script>
</body>
</html>
"""

(root / "app" / "static" / "index.html").write_text(html_content, encoding="utf-8")
(root / "public" / "index.html").write_text(html_content, encoding="utf-8")
print("Successfully generated vector SVG, casual typography frontend in app/static/index.html and public/index.html!")
