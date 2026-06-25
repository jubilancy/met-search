# Met Open Access — Collection Search

A fast, searchable frontend for the Metropolitan Museum of Art's open access collection. ~180,000 public domain artworks with images, full-text search, and filters by department, culture, medium, and date range.

**Live site:** `https://YOUR-USERNAME.github.io/met-search/`

---

## How it works

```
MetObjects.csv (470k rows, GitHub LFS)
        ↓  scripts/build.py  (filter public domain + fetch images from Met API)
data/artworks.json  (~180k records, ~150MB)
        ↓  index.html  (Lunr.js in-browser search, no server needed)
GitHub Pages
```

The build script runs weekly via GitHub Actions and commits an updated `artworks.json`. The frontend loads it once and does all search and filtering client-side using [Lunr.js](https://lunrjs.com/).

---

## Setup

### 1. Clone and install nothing

```bash
git clone https://github.com/YOUR-USERNAME/met-search
cd met-search
```

No npm, no build tools required for the frontend. Python 3.10+ for the build script.

### 2. Build the data

First run takes 3–5 hours (it's fetching ~180k API calls at a polite rate). Subsequent runs are incremental — only new objects are fetched.

```bash
python scripts/build.py
```

This creates `data/artworks.json`. You can also run with `--no-api` to build from the CSV only (no images, much faster, useful for testing):

```bash
python scripts/build.py --no-api
```

### 3. Serve locally

Any static server works:

```bash
python -m http.server 8000
# → open http://localhost:8000
```

### 4. Deploy to GitHub Pages

1. Push the repo to GitHub (including `data/artworks.json`)
2. Go to Settings → Pages → set source to **Deploy from a branch** → `main` / `root`
3. The weekly workflow will keep the index fresh automatically

> **Note:** `data/artworks.json` is large (~150MB). GitHub Pages serves files up to 100MB. If you hit the limit, consider hosting the JSON on a CDN (Cloudflare R2, Backblaze B2) and updating `DATA_URL` in `index.html`.

---

## File structure

```
met-search/
├── index.html                  # Frontend (self-contained, no framework)
├── data/
│   └── artworks.json           # Pre-built artwork index (generated)
├── scripts/
│   └── build.py                # Data pipeline
├── .github/workflows/
│   └── build.yml               # Weekly rebuild workflow
└── README.md
```

---

## Data fields

Each record in `artworks.json`:

| Field | Source |
|---|---|
| `id` | Object ID (Met API) |
| `title` | CSV |
| `artist`, `artistBio` | CSV |
| `date`, `dateBegin`, `dateEnd` | CSV |
| `medium`, `dimensions` | CSV |
| `culture`, `period`, `dynasty` | CSV |
| `department`, `classification` | CSV |
| `creditLine`, `country`, `city` | CSV |
| `tags` | CSV |
| `isHighlight` | CSV |
| `url` | CSV (Link Resource) |
| `image` | Met Collection API (`primaryImageSmall`) |

---

## Search

The frontend uses [Lunr.js](https://lunrjs.com/) for in-browser full-text search with field boosting:

- Title (10×), Artist (6×), Culture (4×), Medium (3×), Department (2×), Tags (2×)
- Trailing wildcard is applied automatically (so "monet" matches "Monet")
- Stemming is disabled for better proper-noun matching

---

## Data source & license

- **Metadata:** [metmuseum/openaccess](https://github.com/metmuseum/openaccess) — CC0
- **Images:** Met Collection API — CC0 (public domain works only)
- **This repo:** MIT
