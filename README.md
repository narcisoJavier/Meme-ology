<div align="center">

```
  __  __                         ___  _                      
 |  \/  | ___ _ __ ___   ___    / _ \| | ___   __ _ _   _    
 | |\/| |/ _ \ '_ ` _ \ / _ \  | | | | |/ _ \ / _` | | | |   
 | |  | |  __/ | | | | |  __/  | |_| | | (_) | (_| | |_| |_  
 |_|  |_|\___|_| |_| |_|\___|   \___/|_|\___/ \__, |\__, (_) 
                                               |___/ |___/   
```

### The Internet's Real-Time Meme Radar 

**A lightning-fast, serverless-ready API that continuously discovers, deduplicates, and ranks memes across Reddit and Know Your Meme before they get reposted on Facebook.**

<br/>

[![Dankness Level](https://img.shields.io/badge/Dankness-Over%209000-orange?style=for-the-badge&logo=reddit)](https://github.com/narcisoJavier/Meme-ology)
[![Freshness](https://img.shields.io/badge/Freshness-100%25%20Organic-brightgreen?style=for-the-badge)](https://github.com/narcisoJavier/Meme-ology)
[![Serverless](https://img.shields.io/badge/Serverless-Vercel%20%240%2Fmo-black?style=for-the-badge&logo=vercel)](https://vercel.com)
[![Tests](https://img.shields.io/badge/Tests-472%2F472%20Passed-blue?style=for-the-badge)](https://github.com/narcisoJavier/Meme-ology)
[![Coverage](https://img.shields.io/badge/Coverage-94%25-green?style=for-the-badge)](https://github.com/narcisoJavier/Meme-ology)
[![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)](LICENSE)

<br/>

[Web Explorer](#-live-web-explorer--documentation-portal) • [Quickstart](#-quickstart-in-30-seconds) • [Endpoints](#-api-reference) • [Deploy Free on Vercel](#-deploy-serverless-for-free-zero-servers-needed) • [The Science](#-the-science-behind-the-dankness)

</div>

---

## 💡 Why Meme-ology?

Stop refreshing Reddit feeds like it's 2012. 

Most meme scrapers break within 48 hours because of rate limits, malformed JSON, crossposts, and duplicate reposts across multiple subreddits.

**Meme-ology** is built like an enterprise-grade radar:
- 🏎️ **Sub-millisecond query latency (<0.1ms)** via dual-layer in-memory hot store and async SQLite Write-Ahead Logging (WAL).
- 🧼 **Zero Repost Spam**: Cryptographic SHA-256 canonical media hashing detects cross-posts across `r/memes` and `r/dankmemes`, merging upvotes instead of cluttering your feed.
- 📉 **Gravity Virality Decay**: Uses HackerNews-style time-decay algorithms so fresh breaking memes always outrank stale week-old viral posts.
- 🛡️ **Polite & Resilient**: Rotating User-Agent pool, per-domain rate limiting, exponential backoff with `Retry-After` support, and local offline fixture fallbacks.
- ☁️ **100% Serverless-Ready**: Zero servers to manage or pay for. Runs locally on your machine or deployed for **$0/month** on Vercel.

---

## ☁️ Deploy Serverless for Free (Zero Servers Needed)

You don't need to rent or maintain your own VPS. Meme-ology is pre-configured with `vercel.json` for Vercel's serverless Python runtime.

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2FnarcisoJavier%2FMeme-ology)

### 3-Step Free Deployment:
1. Fork or import this repository to your GitHub account: `https://github.com/narcisoJavier/Meme-ology`
2. Sign up at [Vercel.com](https://vercel.com) (free) using your GitHub account.
3. Click **"Add New Project"**, select **Meme-ology**, and click **Deploy**.

Vercel will give you a public HTTPS URL (e.g. `https://meme-ology.vercel.app`) with zero server configuration!

---

## 🌐 Live Web Explorer & Documentation Portal

Meme-ology includes a clean, high-contrast web dashboard and live API playground (inspired by `hyperframes.dev`) served directly by the API.

When the server is running, simply open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser:
- 🔍 **Live Search Bar**: Instant real-time keyword search across all meme titles, authors, and communities.
- 🏷️ **Filter Chips**: Instant filtering by `r/dankmemes`, `r/memes`, `r/me_irl`, `r/wholesomememes`, and `Know Your Meme`.
- ⏱️ **Time Windows**: Switch between 1 hour, 6 hours, 24 hours, or all-time trending.
- 💻 **Interactive Code Playground**: Copyable cURL, Python (`httpx`), and JavaScript (`fetch`) snippets with 1-click execution.

---

## ⚡ Quickstart in 30 Seconds

### 1. Run with cURL
```bash
# Get top 5 trending memes right now
curl -s "http://127.0.0.1:8000/api/v1/memes/trending?time_window=24h&limit=5"
```

### 2. Run with Python
```python
import httpx

response = httpx.get(
    "http://127.0.0.1:8000/api/v1/memes/trending",
    params={"time_window": "24h", "limit": 3}
)

for meme in response.json():
    print(f"🔥 [{meme['score']} upvotes] {meme['title']}")
    print(f"   Media: {meme['url']}\n")
```

### 3. Run with JavaScript
```javascript
const res = await fetch("http://127.0.0.1:8000/api/v1/memes/random");
const meme = await res.json();
console.log(`Random Meme: ${meme.title}`);
console.log(`Image: ${meme.url}`);
```

---

## 📡 API Reference

Interactive OpenAPI documentation is live at **`/docs`** (Swagger UI) and **`/redoc`**.

| Method | Endpoint | Query Parameters | Description |
|---|---|---|---|
| `GET` | `/api/v1/memes/trending` | `time_window` (1h/6h/24h/7d/all), `limit`, `offset`, `source`, `nsfw` | Top viral memes sorted by gravity virality score |
| `GET` | `/api/v1/memes/latest` | `limit`, `offset`, `source`, `nsfw` | Chronological feed of newest ingested memes |
| `GET` | `/api/v1/memes/random` | `source`, `nsfw` | Retrieve a single random meme matching filters |
| `GET` | `/api/v1/sources` | none | Health status, item counts, and sync latency per feed |
| `GET` | `/health` | none | System operational status, uptime, and cached counts |
| `GET` | `/docs` | none | Interactive Swagger UI playground |

### Sample Response Schema
```json
{
  "id": "reddit_dankmemes_1abcxyz",
  "title": "When you finally fix a bug with 1 line of code",
  "url": "https://i.redd.it/2z4yq945z8b81.jpg",
  "source": "reddit",
  "source_community": "r/dankmemes",
  "author": "DevWizard42",
  "score": 18450,
  "num_comments": 421,
  "trending_score": 94.25,
  "permalink": "https://reddit.com/r/dankmemes/comments/...",
  "created_at": "2026-09-02T13:40:46Z",
  "is_nsfw": false
}
```

---

## 🧠 The Science Behind The Dankness

### 1. Gravity Virality Formula
Memes age faster than milk. To prevent yesterday's viral post from clogging the top of the feed forever, Meme-ology applies an exponential velocity decay:

$$\text{Trending Score} = \frac{\max(0, \text{score}) + \max(0, \text{comments}) \times 1.5}{(\text{age\_in\_hours} + 2.0)^{1.5}}$$

- Upvotes and comments establish initial virality mass.
- Age (in hours) creates a gravity well that smoothly demotes older memes as newer memes surge.

### 2. Deduplication Hashing
When a meme is cross-posted across multiple communities:
1. URLs are canonicalized (query tracking parameters like `?utm_source` and `?ref` are stripped, image host aliases are normalized).
2. A deterministic SHA-256 content digest is produced.
3. The storage engine merges duplicate submissions, keeping the **highest score** and **freshest comment counts** while preserving chronological order.

---

## 🛠️ Local Development & Testing

```bash
# Clone the repository
git clone https://github.com/narcisoJavier/Meme-ology.git
cd Meme-ology

# Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Run the API server
uvicorn app.main:app --reload

# Run the automated test suite (472 tests)
pytest --cov=app --cov-report=term-missing -v
```

---

## 📜 License

MIT License. Crafted with ❤️ for internet meme connoisseurs.
