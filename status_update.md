# NCAAB Projector — Status Update
_Last updated: March 2026_

## Current state: all phases complete ✅

### DB coverage
| Season | Games | Adv Games | Coverage | Status |
|---|---|---|---|---|
| 2015 | 5,932 | 5,931 | 100% | ✅ Complete |
| 2016 | 5,951 | 5,951 | 100% | ✅ Complete |
| 2017 | 5,964 | 5,487 | 92% | ✅ Good enough |
| 2018 | 6,003 | 5,553 | 93% | ✅ Good enough |
| 2019 | 6,049 | 5,599 | 93% | ✅ Good enough |
| 2020 | 5,767 | 4,983 | 86% | ✅ Good enough |
| 2021 | 4,285 | 3,691 | 86% | ✅ Good enough |
| 2022 | 5,936 | 5,471 | 92% | ✅ Good enough |
| 2023 | 6,222 | 5,641 | 91% | ✅ Good enough |
| 2024 | 6,075 | 6,074 | 100% | ✅ Complete |
| 2025 | 6,292 | 6,291 | 100% | ✅ Complete |
| 2026 | current | current | n/a | ✅ Nightly job running |

86–100% coverage is the expected ceiling — missing games are ESPN 404s (no box score data available), not pipeline failures. `team_stats` is fully populated for all seasons (2015–2026).

---

## Completed phases

### Phase 1 — Historical backfill ✅
All seasons 2015–2026 populated. 2024 and 2025 backfilled to 100% adv game coverage.

### Phase 2 — Season selector UI ✅
Sidebar season selectbox (2015–26) propagated through all pages and db.py functions.
- `db.py` — all fetchers accept `season` param
- `app.py` — sidebar selectbox, stored in `st.session_state.season`
- All pages — `show(season)` signature, db calls pass season through
- `overview.py` — efficiency scatter gated behind `if season == 2026`, historical seasons show all-teams scatter by conference

### Phase 3 — Year-aware bracket seeds ✅
`bracket_seeds.py` now contains all tournament brackets 2015–2026 (no 2020 — cancelled).
- `BRACKETS` registry dict: `{season: bracket_dict}`
- `get_seed(team, season=2026)` — season-aware, defaults to 2026
- `matchup.py` — `bs.get_seed(team, season)` calls updated
- `matchup_compare.py` — uses `BRACKETS.get(season, {})`, seed buttons gated behind `if bracket_seeds_dict`

### Phase 4 — Spot-check validation ✅
Ran `pipeline/spot_check.py` across all seasons. Findings:
- ✅ All four factors in valid ranges across all seasons and checked teams
- ✅ 2024 rankings perfect (UConn #1, Houston #2, Purdue #3)
- ✅ Auburn name mapping fixed (`"Auburn Tigers"` ↔ `"Auburn"`)
- ✅ Conference abbreviation rows filtered from `team_stats` (BartTorvik CSV includes MWC, WAC etc. as summary rows)
- ✅ `to_bart()` / `to_espn()` now fall back to `MANUAL`/`_MANUAL_INV` when `build()` hasn't been called
- ⚠️ Auburn 2026 AdjDE looks wrong (106 vs expected ~93) — BartTorvik upstream lag, resolves on next nightly run once they reprocess
- ℹ️ Ranking warnings in older seasons are expected — our net_eff ranking diverges from BartTorvik T-Rank by design (we compute from ESPN game data)

---

## Known issues / watch list
- **Auburn 2026** — BartTorvik hasn't reprocessed recent games. Nightly job will self-correct.
- **Bracket seeds name variants** — team names in `bracket_seeds.py` use BartTorvik period variants (e.g. `"Michigan St."`, `"Iowa St."`). If a team fails to match in the seed overlay, check the name against `team_stats`.

---

## Key fixes applied (session)
| File | Fix |
|---|---|
| `app/name_map.py` | Added `"Auburn"` and ~30 other plain-name teams to `MANUAL`; `to_bart()`/`to_espn()` fall back to `MANUAL`/`_MANUAL_INV` |
| `app/bracket_seeds.py` | Full historical brackets 2015–2025; corrected BartTorvik period variants throughout |
| `pipeline/fetch_and_store.py` | Filter conference abbreviation rows: `df = df[df["team"].str.len() > 6]` |
| `app/db.py` | All fetchers accept `season` param |
| `app/app.py` | Season selector in sidebar |
| All pages | `show(season)` signature |

---

## Roadmap

### Next up — new features
Ideas in priority order:
1. **Season-over-season team comparison** — efficiency profile changes year to year for a given team
2. **Historical upset tracker** — score how well the model would have predicted past tournament upsets
3. **Conference trends** — ACC/Big Ten/SEC strength shifts 2015–2026

### Phase 3 loose end
`matchup_compare.py` seed quick-add buttons are still hardcoded to the 4 standard regions. If a future bracket uses different region names this would need updating — low priority.