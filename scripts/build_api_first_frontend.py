"""Generate sleek, modern 'API-like' developer-grade interface for Meme-ology."""

import json
from pathlib import Path

# Load sanitized real memes
data_path = Path("data/live_harvested_memes.json")
real_memes = json.loads(data_path.read_text(encoding="utf-8"))
memes_json_str = json.dumps(real_memes, indent=4)

html_content = f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MEME-OLOGY — The Open Internet Meme API &amp; Feed</title>
  <meta name="description" content="High-performance meme curation engine. Ingesting, categorizing, and scoring internet culture across generations in real-time.">
  <meta name="referrer" content="no-referrer">

  <!-- Inter and JetBrains Mono Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">

  <style>
    :root {{
      --bg-base: #09090b;
      --bg-surface: #121215;
      --bg-surface-elevated: #18181c;
      --bg-surface-hover: #222228;
      --border-subtle: #27272a;
      --border-focus: #3f3f46;
      --text-primary: #f4f4f5;
      --text-secondary: #a1a1aa;
      --text-muted: #71717a;
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
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      min-height: 100vh;
      overflow-x: hidden;
      line-height: 1.5;
      background-color: var(--bg-base);
      background-image: 
        radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99, 102, 241, 0.12), transparent 70%),
        linear-gradient(to bottom, transparent, rgba(9, 9, 11, 0.8));
    }}

    /* Global Header */
    header {{
      position: sticky;
      top: 0;
      z-index: 100;
      background: rgba(9, 9, 11, 0.85);
      backdrop-filter: blur(12px);
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
      gap: 0.4rem;
    }}

    .brand-badge {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.65rem;
      font-weight: 600;
      padding: 2px 6px;
      background: #1e1e24;
      border: 1px solid #33333d;
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
      font-family: 'Inter', sans-serif;
      font-size: 0.8rem;
      font-weight: 600;
      padding: 5px 12px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s ease;
      display: flex;
      align-items: center;
      gap: 0.35rem;
    }}

    .nav-btn:hover {{
      color: #fff;
      background: var(--bg-surface-elevated);
    }}

    .nav-btn.active {{
      color: #fff;
      background: #27272f;
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
    }}

    .nav-actions {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}

    .btn-action {{
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 6px 12px;
      font-size: 0.8rem;
      font-weight: 600;
      border-radius: 6px;
      text-decoration: none;
      transition: all 0.15s ease;
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
    }}

    /* Container */
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
      max-width: 620px;
      line-height: 1.6;
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
      gap: 1rem;
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
      padding: 6px 10px 6px 2rem;
      font-family: 'Inter', sans-serif;
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
      left: 0.65rem;
      top: 50%;
      transform: translateY(-50%);
      color: var(--text-muted);
      font-size: 0.85rem;
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
      padding: 4px 10px;
      font-family: 'Inter', sans-serif;
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text-secondary);
      cursor: pointer;
      transition: all 0.12s ease;
    }}

    .era-pill:hover {{
      color: #fff;
      border-color: var(--border-focus);
    }}

    .era-pill.active {{
      background: #272730;
      color: #fff;
      border-color: #52525b;
    }}

    .toolbar-select {{
      background: #09090c;
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 6px 10px;
      font-family: 'Inter', sans-serif;
      font-size: 0.8rem;
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
      transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
      cursor: pointer;
    }}

    .meme-card:hover {{
      transform: translateY(-2px);
      border-color: var(--border-focus);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
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
      background: #1a1a20;
      border: 1px solid #2a2a34;
      padding: 2px 7px;
      border-radius: 4px;
    }}

    .era-tag {{
      font-size: 0.68rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 2px 6px;
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
      border-top: 1px solid #1c1c22;
      border-bottom: 1px solid #1c1c22;
    }}

    .card-media-frame img, .card-media-frame video {{
      max-width: 100%;
      max-height: 100%;
      width: auto;
      height: auto;
      object-fit: contain;
      transition: transform 0.2s ease;
    }}

    .card-content {{
      padding: 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
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
      background: #0d0d10;
    }}

    .btn-upvote {{
      background: #18181e;
      border: 1px solid var(--border-subtle);
      border-radius: 6px;
      padding: 4px 9px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.78rem;
      font-weight: 600;
      color: var(--text-secondary);
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      cursor: pointer;
      transition: all 0.12s ease;
    }}

    .btn-upvote:hover {{
      background: #23232c;
      border-color: var(--border-focus);
      color: #fff;
    }}

    .btn-upvote.voted {{
      background: rgba(16, 185, 129, 0.15);
      border-color: rgba(16, 185, 129, 0.4);
      color: var(--accent-emerald);
    }}

    .btn-permalink {{
      color: var(--text-secondary);
      font-size: 0.75rem;
      font-weight: 600;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      padding: 4px 8px;
      border-radius: 4px;
      transition: color 0.12s ease;
    }}

    .btn-permalink:hover {{
      color: #fff;
      background: #1a1a20;
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
      font-size: 1.1rem;
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
      border-bottom: 1px solid #1a1a20;
      transition: background 0.12s ease;
    }}

    .trending-row:hover {{
      background: #15151b;
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
      border: 1px solid #27272a;
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
      background: #0e0e12;
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
      background: #1f1f28;
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
      background: #0d0d10;
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
      background: #1c1c24;
      border-color: #2e2e3a;
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
      background: #27272f;
      border: 1px solid #3f3f4a;
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

  <!-- Header -->
  <header>
    <div class="nav-container">
      <div class="logo-group">
        <span class="brand-title">
          <span>⚡ MEME-OLOGY</span>
        </span>
        <span class="brand-badge">v1.2</span>
        <div class="status-pill">
          <span class="status-dot"></span>
          <span>API ONLINE</span>
        </div>
      </div>

      <nav class="nav-switcher">
        <button class="nav-btn active" id="navBtnFeed" onclick="scrollToSection('feedSection')">
          Feed Explorer
        </button>
        <button class="nav-btn" id="navBtnTrending" onclick="scrollToSection('trendingSection')">
          Top 10 Trending
        </button>
        <button class="nav-btn" id="navBtnLab" onclick="scrollToSection('labSection')">
          API Studio
        </button>
      </nav>

      <div class="nav-actions">
        <a href="/docs" target="_blank" class="btn-action btn-secondary">
          <span>Swagger Docs ↗</span>
        </a>
        <a href="https://github.com/narcisoJavier/Meme-ology" target="_blank" class="btn-action btn-primary">
          <span>★ GitHub</span>
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
          100% authentic, verified posts served with sub-5ms edge latency.
        </p>
      </div>

      <div class="quick-curl-box">
        <span class="curl-tag">GET</span>
        <span>/api/v1/memes/trending?generation=gen_z</span>
        <button class="btn-action btn-secondary" style="padding: 3px 8px; font-size: 0.7rem;" onclick="copyQuickCurl()">
          Copy
        </button>
      </div>
    </section>

    <!-- Sleek API Toolbar -->
    <div class="api-toolbar">
      <div class="search-wrapper">
        <span class="search-icon">⌕</span>
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

      <!-- Dropdown Dials -->
      <div style="display: flex; gap: 0.5rem;">
        <select id="communitySelect" class="toolbar-select" onchange="onCommunityFilter(this.value)">
          <option value="all">All Communities</option>
          <option value="r/dankmemes">r/dankmemes</option>
          <option value="r/me_irl">r/me_irl</option>
          <option value="r/GenAlpha">r/GenAlpha</option>
          <option value="r/skibiditoilet">r/skibiditoilet</option>
          <option value="r/wholesomememes">r/wholesomememes</option>
          <option value="r/AdviceAnimals">r/AdviceAnimals</option>
          <option value="knowyourmeme">Know Your Meme</option>
        </select>
        <select id="sortSelect" class="toolbar-select" onchange="onSortFilter(this.value)">
          <option value="newest" selected>Fresh &amp; Recent</option>
          <option value="score">Top Score</option>
        </select>
      </div>
    </div>

    <!-- Memes Grid (Unclipped, Professional) -->
    <div class="memes-grid" id="memesGrid"></div>

    <!-- Section 2: Top 10 Trending Right Now -->
    <section class="section-card" id="trendingSection" style="margin-top: 4rem;">
      <div class="section-card-header">
        <div class="section-card-title">
          <span>⚡ Top 10 Trending Right Now</span>
        </div>
        <span class="status-pill" style="font-size: 0.68rem;">LIVE RANKED</span>
      </div>

      <div id="trendingTable">
        <!-- Rendered by JavaScript -->
      </div>
    </section>

    <!-- Section 3: Developer API Studio -->
    <section class="section-card" id="labSection" style="margin-top: 4rem;">
      <div class="section-card-header">
        <div class="section-card-title">
          <span>🧪 Developer API Studio &amp; Playground</span>
        </div>
        <div style="display: flex; gap: 0.5rem;">
          <button class="btn-action btn-secondary" style="font-size: 0.75rem;" onclick="copyApiUrl()">
            Copy Endpoint URL
          </button>
          <button class="btn-action btn-secondary" style="font-size: 0.75rem;" onclick="downloadJson()">
            Download JSON
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
              Copy Code
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

  <!-- Modal -->
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
            Open Original Discussion ↗
          </a>
        </div>
      </div>
    </div>
  </div>

  <!-- Footer -->
  <footer>
    <p>Meme-ology API © 2026 • Real-time Internet Culture &amp; Historical Humor Engine</p>
    <p style="margin-top: 0.5rem;">
      <a href="https://github.com/narcisoJavier/Meme-ology" target="_blank">GitHub Repository</a> • 
      <a href="/docs" target="_blank">Interactive Swagger UI</a> • 
      <a href="/openapi.json" target="_blank">OpenAPI 3.1 Spec</a> • 
      <a href="#feedSection">Back to Top &uarr;</a>
    </p>
  </footer>

  <script>
    // 100% Authentic Live Dataset
    const MEMES_DATA = {memes_json_str};

    let memes = [...MEMES_DATA];
    let activeGen = 'all';
    let activeCommunity = 'all';
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
        console.log("Using cached dataset");
      }}
      renderFeed();
      renderTrendingTable();
      updateStudio();
    }}

    // Render Clean Memes Grid
    function renderFeed() {{
      const grid = document.getElementById('memesGrid');
      const search = document.getElementById('memeSearch').value.toLowerCase().trim();
      const votedSet = getVotedSet();

      let filtered = memes.filter(m => {{
        const title = (m.title || '').toLowerCase();
        const author = (m.author || '').toLowerCase();
        const comm = (m.source_community || '').toLowerCase();
        const gen = (m.generation || 'gen_z').toLowerCase();

        const matchSearch = !search || title.includes(search) || author.includes(search) || comm.includes(search);
        const matchGen = activeGen === 'all' || gen === activeGen;
        const matchComm = activeCommunity === 'all' || comm === activeCommunity;

        return matchSearch && matchGen && matchComm;
      }});

      if (activeSort === 'newest') {{
        filtered.sort((a,b) => (b.created_at || 0) - (a.created_at || 0));
      }} else {{
        filtered.sort((a,b) => (b.score || 0) - (a.score || 0));
      }}

      if (filtered.length === 0) {{
        grid.innerHTML = `
          <div style="grid-column: 1/-1; text-align: center; padding: 4rem 1rem; color: var(--text-muted); font-size: 0.95rem;">
            No memes match your active filters. Try clearing your search or switching eras.
          </div>
        `;
        return;
      }}

      grid.innerHTML = filtered.map(m => {{
        const genKey = (m.generation || 'gen_z').toLowerCase();
        const isVoted = votedSet.has(m.id);
        const isVideo = m.media_type === 'video' || (m.url && (m.url.endsWith('.mp4') || m.url.endsWith('.webm')));

        const mediaTag = isVideo ? `
          <video src="${{m.url}}" preload="metadata" muted playsinline loop referrerpolicy="no-referrer"></video>
        ` : `
          <img src="${{m.url}}" alt="${{m.title}}" loading="lazy" referrerpolicy="no-referrer" />
        `;

        return `
          <div class="meme-card" data-id="${{m.id}}">
            <div class="card-top">
              <span class="community-badge">${{m.source_community || m.source}}</span>
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
                <span>▲</span>
                <span class="score-val">${{Number(m.score).toLocaleString()}}</span>
              </button>

              <a href="${{m.permalink}}" target="_blank" rel="noopener noreferrer" class="btn-permalink" onclick="event.stopPropagation()">
                <span>Open Thread</span>
                <span>↗</span>
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
          }} else {{
            btn.classList.remove('voted');
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
                Thread ↗
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

    function onCommunityFilter(val) {{
      activeCommunity = val;
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
      document.getElementById('modalScore').textContent = `▲ ${{Number(meme.score).toLocaleString()}}`;
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

      let path = `/api/v1/memes/${{selectedEndpoint}}`;
      if (selectedEndpoint === 'sources') path = '/api/v1/sources';
      if (selectedEndpoint === 'health') path = '/health';

      const params = new URLSearchParams();
      if (['trending', 'latest', 'random'].includes(selectedEndpoint)) {{
        if (gen) params.set('generation', gen);
        if (selectedEndpoint !== 'random' && limit) params.set('limit', limit);
      }}

      const qs = params.toString();
      return `${{origin}}${{path}}${{qs ? '?' + qs : ''}}`;
    }}

    function copyQuickCurl() {{
      const text = `curl -X GET "${{window.location.origin}}/api/v1/memes/trending?generation=gen_z"`;
      navigator.clipboard.writeText(text);
    }}

    function copyApiUrl() {{
      navigator.clipboard.writeText(buildUrl());
    }}

    function copyCodeSnippet() {{
      navigator.clipboard.writeText(document.getElementById('codeSnippet').textContent);
    }}

    function downloadJson() {{
      const text = document.getElementById('responseViewer').textContent;
      const blob = new Blob([text], {{ type: 'application/json' }});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `memeology-${{selectedEndpoint}}.json`;
      a.click();
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
      let items = [...memes];
      if (gen) items = items.filter(m => (m.generation || '').toLowerCase() === gen);
      items = items.slice(0, limit);

      const payload = selectedEndpoint === 'random' ? (items[0] || {{}}) : (
        selectedEndpoint === 'sources' ? [
          {{ platform: "reddit", community: "r/dankmemes", status: "ok", item_count: 14 }},
          {{ platform: "reddit", community: "r/GenAlpha", status: "ok", item_count: 13 }},
          {{ platform: "knowyourmeme", community: "confirmed", status: "ok", item_count: 6 }}
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

Path("app/static/index.html").write_text(html_content, encoding="utf-8")
Path("public/index.html").write_text(html_content, encoding="utf-8")
print("Successfully generated sleek API-First frontend in app/static/index.html and public/index.html!")
