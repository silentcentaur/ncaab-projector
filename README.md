# NCAAB Madness — Full Stack Setup

**Architecture:** BartTorvik + ESPN → GitHub Actions (nightly) → Supabase → Streamlit

---

## Step 1 — Create a Supabase project

1. Go to **supabase.com** → Sign up (free)
2. Click **New Project** → give it a name (e.g. "ncaab-madness")
3. Wait ~2 min for it to provision
4. Go to **SQL Editor** → paste the entire contents of `schema.sql` → click **Run**
5. Go to **Project Settings → API** and copy:
   - **Project URL** → this is your `SUPABASE_URL`
   - **service_role** secret key → this is your `SUPABASE_KEY` (⚠️ keep this private)

---

## Step 2 — Set up the GitHub repo

1. Create a new repo on github.com (can be private)
2. Push this entire project folder to it:
```bash
cd ncaab_v2
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```
3. In your GitHub repo go to **Settings → Secrets and variables → Actions**
4. Add two secrets:
   - `SUPABASE_URL` — your Supabase project URL
   - `SUPABASE_KEY` — your Supabase service_role key

---

## Step 3 — Run the pipeline for the first time

Install pipeline dependencies:
```bash
cd pipeline
pip3 install -r requirements.txt
```

Create your local `.env` file:
```bash
cp .env.example .env
# Edit .env and fill in your real SUPABASE_URL and SUPABASE_KEY
```

Run the pipeline:
```bash
python3 fetch_and_store.py
```

This takes ~15-25 min for the full game log pull (one-time). After that, GitHub Actions runs it nightly automatically.

---

## Step 4 — Run the Streamlit app locally

```bash
cd app
pip3 install -r requirements.txt
```

Edit `.streamlit/secrets.toml` and fill in your Supabase credentials, then:
```bash
streamlit run app.py
```

---

## Step 5 — Deploy to Streamlit Community Cloud (free, shareable URL)

1. Go to **share.streamlit.io** → sign in with GitHub
2. Click **New app**
3. Select your repo, set **Main file path** to `app/app.py`
4. Click **Advanced settings → Secrets** and paste:
```toml
SUPABASE_URL = "https://YOUR_PROJECT_ID.supabase.co"
SUPABASE_KEY = "your_service_role_key_here"
```
5. Click **Deploy** — you'll get a public URL in ~2 minutes

Anyone with the link can now use the app. Data refreshes nightly via GitHub Actions automatically.

---

## Project Structure

```
ncaab_v2/
├── schema.sql                        ← Run once in Supabase SQL Editor
├── .gitignore
├── .github/
│   └── workflows/
│       └── nightly.yml               ← GitHub Actions nightly job
├── pipeline/
│   ├── fetch_and_store.py            ← Data fetch + Supabase upsert
│   ├── requirements.txt
│   └── .env.example                  ← Copy to .env and fill in credentials
└── app/
    ├── app.py                        ← Streamlit entry point (run this)
    ├── db.py                         ← All Supabase queries
    ├── requirements.txt
    ├── .streamlit/
    │   └── secrets.toml              ← Local credentials (never commit)
    └── pages/
        ├── overview.py
        ├── explorer.py
        ├── matchup.py
        ├── gamelog.py
        └── status.py
```
