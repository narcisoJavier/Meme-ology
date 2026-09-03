<div align="center">

<p align="center">
  <img src="docs/banner.svg" alt="MEME-OLOGY — The Open Internet Meme API" width="100%">
</p>

### The Open Internet Meme API & Real-Time Curation Engine

**A lightning-fast, high-concurrency API that discovers, ranks, and categorizes memes across Reddit, Bluesky, Know Your Meme, and Mastodon with sub-5ms edge latency.**

<br/>

[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Networks](https://img.shields.io/badge/Networks-Reddit%20%7C%20Bluesky%20%7C%20KYM%20%7C%20Mastodon-6366f1?style=for-the-badge)](https://github.com/narcisoJavier/Meme-ology)
[![Tests](https://img.shields.io/badge/Tests-629%20Passed-10b981?style=for-the-badge)](https://github.com/narcisoJavier/Meme-ology)
[![Coverage](https://img.shields.io/badge/Coverage-94%25-green?style=for-the-badge)](https://github.com/narcisoJavier/Meme-ology)
[![License](https://img.shields.io/badge/License-MIT-8b5cf6?style=for-the-badge)](LICENSE)

<br/>

[Web Explorer](#-live-web-explorer--documentation-portal) • [Quickstart](#-quickstart-in-30-seconds) • [Endpoints](#-api-reference) • [Deploy Free on Vercel](#-deploy-serverless-for-free-zero-servers-needed) • [Trending Science](#-how-trending-ranking-works)

</div>

---

## 💡 Why Meme-ology?

Most meme scrapers break within 48 hours because of rate limits, malformed payloads, crossposts, and duplicate reposts across multiple platforms.

**Meme-ology** is built as a high-performance open internet culture engine:
- 🏎️ **Sub-5ms query latency** via dual-layer in-memory cache and persistent async SQLite Write-Ahead Logging (WAL).
- 🌐 **Multi-Network Coverage**: Ingests authentic posts from Reddit (`r/dankmemes`, `r/memes`, `r/GenAlpha`), Bluesky (AT Protocol XRPC), Know Your Meme, and Mastodon (ActivityPub).
- 🧼 **Zero Repost Spam**: Cryptographic SHA-256 canonical media hashing detects cross-posts across communities, merging engagement instead of cluttering your feed.
- 📉 **Gravity Virality Decay**: HackerNews-style half-life exponential time-decay so fresh viral memes always outrank stale week-old posts.
- 🛡️ **Polite & Resilient**: Rotating User-Agent pool, per-domain rate limiting, exponential backoff with `Retry-After` handling, and offline fixture fallbacks.
- ☁️ **100% Serverless-Ready**: Runs locally on your machine or deploys for **$0/month** on Vercel.

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

## 🧠 How Trending Ranking Works

### 1. Gravity Virality Formula
Memes move fast. To ensure today's viral cultural moments rank above older historical posts, Meme-ology applies an exponential velocity decay:

$$\text{Trending Score} = (\text{score} + 1.5 \times \text{num\_comments}) \times e^{-\lambda \Delta t}$$

- **Base Score & Comments:** Upvotes and discussion volume establish raw community engagement.
- **Half-Life Decay ($\lambda = \ln(2)/12$):** With a 12-hour exponential half-life, breaking memes naturally outrank yesterday's viral posts.

### 2. Content Deduplication & Canonical Hashing
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

# Run the automated test suite (629 tests)
pytest --cov=app --cov-report=term-missing -v
```

---

## 📜 License

MIT License. Crafted with ❤️ for internet meme connoisseurs.
