"""
name_map.py
===========
Bidirectional fuzzy team name mapping between BartTorvik short names
and ESPN full names (e.g. "Gonzaga" <-> "Gonzaga Bulldogs").

Usage:
    from name_map import to_espn, to_bart, normalize

    to_espn("Gonzaga")            -> "Gonzaga Bulldogs"
    to_bart("Gonzaga Bulldogs")   -> "Gonzaga"
    normalize(game_df, team_df)   -> merges on best-match name
"""

import re
import pandas as pd

# ── Manual overrides for tricky cases ────────────────────────────────────────
# Format: BartTorvik name -> ESPN full name
MANUAL = {
    "UConn":              "Connecticut Huskies",
    "UCF":                "UCF Knights",
    "UAB":                "UAB Blazers",
    "UTEP":               "UTEP Miners",
    "UTSA":               "UTSA Roadrunners",
    "VCU":                "VCU Rams",
    "SMU":                "SMU Mustangs",
    "LSU":                "LSU Tigers",
    "TCU":                "TCU Horned Frogs",
    "BYU":                "BYU Cougars",
    "USC":                "USC Trojans",
    "UCLA":               "UCLA Bruins",
    "UNLV":               "UNLV Rebels",
    "UMBC":               "UMBC Retrievers",
    "UIC":                "UIC Flames",
    "UMass":              "Massachusetts Minutemen",
    "UNC":                "North Carolina Tar Heels",
    "North Carolina":     "North Carolina Tar Heels",
    "NC State":           "NC State Wolfpack",
    "Miami FL":           "Miami Hurricanes",
    "Miami OH":           "Miami (OH) RedHawks",
    "Ole Miss":           "Ole Miss Rebels",
    "Mississippi St":     "Mississippi State Bulldogs",
    "Penn St":            "Penn State Nittany Lions",
    "Ohio St":            "Ohio State Buckeyes",
    "Michigan St":        "Michigan State Spartans",
    "Michigan":           "Michigan Wolverines",
    "Florida St":         "Florida State Seminoles",
    "Georgia Tech":       "Georgia Tech Yellow Jackets",
    "Wake Forest":        "Wake Forest Demon Deacons",
    "Boston College":     "Boston College Eagles",
    "Notre Dame":         "Notre Dame Fighting Irish",
    "Pittsburgh":         "Pittsburgh Panthers",
    "Virginia Tech":      "Virginia Tech Hokies",
    "West Virginia":      "West Virginia Mountaineers",
    "Iowa St":            "Iowa State Cyclones",
    "Kansas St":          "Kansas State Wildcats",
    "Oklahoma St":        "Oklahoma State Cowboys",
    "Texas Tech":         "Texas Tech Red Raiders",
    "Texas A&M":          "Texas A&M Aggies",
    "New Mexico":         "New Mexico Lobos",
    "Boise St":           "Boise State Broncos",
    "Colorado St":        "Colorado State Rams",
    "San Diego St":       "San Diego State Aztecs",
    "Utah St":            "Utah State Aggies",
    "Nevada":             "Nevada Wolf Pack",
    "Fresno St":          "Fresno State Bulldogs",
    "Washington St":      "Washington State Cougars",
    "Oregon St":          "Oregon State Beavers",
    "Arizona St":         "Arizona State Sun Devils",
    "Sacramento St":      "Sacramento State Hornets",
    "Cal Poly":           "Cal Poly Mustangs",
    "Long Beach St":      "Long Beach State Beach",
    "CSUN":               "Cal State Northridge Matadors",
    "CSUF":               "Cal State Fullerton Titans",
    "UC Davis":           "UC Davis Aggies",
    "UC Irvine":          "UC Irvine Anteaters",
    "UC Riverside":       "UC Riverside Highlanders",
    "UC Santa Barbara":   "UC Santa Barbara Gauchos",
    "App State":          "Appalachian State Mountaineers",
    "Coastal Carolina":   "Coastal Carolina Chanticleers",
    "GA Southern":        "Georgia Southern Eagles",
    "South Alabama":      "South Alabama Jaguars",
    "La.-Monroe":         "Louisiana Monroe Warhawks",
    "Louisiana":          "Louisiana Ragin' Cajuns",
    "Ark.-Pine Bluff":    "Arkansas-Pine Bluff Golden Lions",
    "MVSU":               "Mississippi Valley State Delta Devils",
    "SIU Edwardsville":   "SIU Edwardsville Cougars",
    "UT Arlington":       "UT Arlington Mavericks",
    "UALR":               "Little Rock Trojans",
    "SFA":                "Stephen F. Austin Lumberjacks",
    "SE Louisiana":       "Southeastern Louisiana Lions",
    "McNeese St":         "McNeese Cowboys",
    "Nicholls St":        "Nicholls Colonels",
    "Northwestern St":    "Northwestern State Demons",
    "Sam Houston St":     "Sam Houston Bearkats",
    "Stetson":            "Stetson Hatters",
    "North Florida":      "North Florida Ospreys",
    "Kennesaw St":        "Kennesaw State Owls",
    "Queens":             "Queens Royals",
    # Auto-generated from check_name_mapping.py diagnostic
    "UConn":              "UConn Huskies",
    "Alabama":            "Alabama Crimson Tide",
    "Illinois":           "Illinois Fighting Illini",
    "Tennessee":          "Tennessee Volunteers",
    "Kansas":             "Kansas Jayhawks",
    "Vanderbilt":         "Vanderbilt Commodores",
    "Nebraska":           "Nebraska Cornhuskers",
    "Oakland":            "Oakland Golden Grizzlies",
    "Green Bay":          "Green Bay Phoenix",
    "Jackson St":         "Jackson State Tigers",
    "Campbell":           "Campbell Fighting Camels",
    "Creighton":          "Creighton Bluejays",
    "Grambling St":       "Grambling Tigers",
    "Merrimack":          "Merrimack Warriors",
    "Minnesota":          "Minnesota Golden Gophers",
    "North Dakota":       "North Dakota Fighting Hawks",
    "Rutgers":            "Rutgers Scarlet Knights",
    "South Dakota St":    "South Dakota State Jackrabbits",
    "Southern":           "Southern Jaguars",
    "Stanford":           "Stanford Cardinal",
    "Bethune-Cookman":    "Bethune-Cookman Wildcats",
    "Cal St. Bakersfield":"Cal State Bakersfield Roadrunners",
    "Cal Baptist":        "California Baptist Lancers",
    "California":         "California Golden Bears",
    "Colgate":            "Colgate Raiders",
    "Dartmouth":          "Dartmouth Big Green",
    "DePaul":             "DePaul Blue Demons",
    "Evansville":         "Evansville Purple Aces",
    "Hawaii":             "Hawai'i Rainbow Warriors",
    "Howard":             "Howard Bison",
    "Lipscomb":           "Lipscomb Bisons",
    "Marquette":          "Marquette Golden Eagles",
    "Middle Tennessee":   "Middle Tennessee Blue Raiders",
    "New Orleans":        "New Orleans Privateers",
    "Niagara":            "Niagara Purple Eagles",
    "Northern Kentucky":  "Northern Kentucky Norse",
    "Rider":              "Rider Broncs",
    "South Carolina":     "South Carolina Gamecocks",
    "South Carolina St":  "South Carolina State Bulldogs",
    "Southern Miss":      "Southern Miss Golden Eagles",
    "Toledo":             "Toledo Rockets",
    "Utah Tech":          "Utah Tech Trailblazers",
    "Akron":              "Akron Zips",
    "American":           "American University Eagles",
    "Army":               "Army Black Knights",
    "Bellarmine":         "Bellarmine Knights",
    "Charleston Southern":"Charleston Southern Buccaneers",
    "Chattanooga":        "Chattanooga Mocs",
    "Colorado":           "Colorado Buffaloes",
    "Cornell":            "Cornell Big Red",
    "Delaware":           "Delaware Blue Hens",
    "Denver":             "Denver Pioneers",
    "Detroit Mercy":      "Detroit Mercy Titans",
    "East Carolina":      "East Carolina Pirates",
    "Fairleigh Dickinson":"Fairleigh Dickinson Knights",
    "Gardner-Webb":       "Gardner-Webb Runnin' Bulldogs",
    "Harvard":            "Harvard Crimson",
    "IU Indy":            "IU Indianapolis Jaguars",
    "Idaho St":           "Idaho State Bengals",
    "Illinois St":        "Illinois State Redbirds",
    "Indiana St":         "Indiana State Sycamores",
    "Lehigh":             "Lehigh Mountain Hawks",
    "LIU":                "Long Island University Sharks",
    "Manhattan":          "Manhattan Jaspers",
    "Marist":             "Marist Red Foxes",
    "Montana":            "Montana Grizzlies",
    "Montana St":         "Montana State Bobcats",
    "Morehead St":        "Morehead State Eagles",
    "Morgan St":          "Morgan State Bears",
    "Nebraska Omaha":     "Omaha Mavericks",
    "Pennsylvania":       "Pennsylvania Quakers",
    "Providence":         "Providence Friars",
    "Purdue Fort Wayne":  "Purdue Fort Wayne Mastodons",
    "Queens":             "Queens University Royals",
    "Seton Hall":         "Seton Hall Pirates",
    "South Dakota":       "South Dakota Coyotes",
    "South Florida":      "South Florida Bulls",
    "Southern Utah":      "Southern Utah Thunderbirds",
    "Tarleton St":        "Tarleton State Texans",
    "Tennessee Tech":     "Tennessee Tech Golden Eagles",
    "UMass Lowell":       "UMass Lowell River Hawks",
    "UT Martin":          "UT Martin Skyhawks",
    "Utah":               "Utah Utes",
    "VMI":                "VMI Keydets",
    "Valparaiso":         "Valparaiso Beacons",
    "Western Carolina":   "Western Carolina Catamounts",
    "Western Kentucky":   "Western Kentucky Hilltoppers",
    "Wofford":            "Wofford Terriers",
    "Wright St":          "Wright State Raiders",
    "Youngstown St":      "Youngstown State Penguins",
    "Alcorn St":          "Alcorn State Braves",
    "App State":          "App State Mountaineers",
    "Austin Peay":        "Austin Peay Governors",
    "Ball St":            "Ball State Cardinals",
    "Bradley":            "Bradley Braves",
    "Bucknell":           "Bucknell Bison",
    "Canisius":           "Canisius Golden Griffins",
    "Chicago St":         "Chicago State Cougars",
    "Cleveland St":       "Cleveland State Vikings",
    "Coppin St":          "Coppin State Eagles",
    "Delaware St":        "Delaware State Hornets",
    "ETSU":               "East Tennessee State Buccaneers",
    "Fairfield":          "Fairfield Stags",
    "Florida A&M":        "Florida A&M Rattlers",
    "George Washington":  "George Washington Revolutionaries",
    "Georgetown":         "Georgetown Hoyas",
    "Hampton":            "Hampton Pirates",
    "Holy Cross":         "Holy Cross Crusaders",
    "Idaho":              "Idaho Vandals",
    "Jacksonville":       "Jacksonville Dolphins",
    "Jacksonville St":    "Jacksonville State Gamecocks",
    "Kent St":            "Kent State Golden Flashes",
    "La Salle":           "La Salle Explorers",
    "Lafayette":          "Lafayette Leopards",
    "Le Moyne":           "Le Moyne Dolphins",
    "Liberty":            "Liberty Flames",
    "Loyola Chicago":     "Loyola Chicago Ramblers",
    "Loyola MD":          "Loyola Maryland Greyhounds",
    "Marshall":           "Marshall Thundering Herd",
    "Missouri St":        "Missouri State Bears",
    "Murray St":          "Murray State Racers",
    "NJIT":               "NJIT Highlanders",
    "Navy":               "Navy Midshipmen",
    "Norfolk St":         "Norfolk State Spartans",
    "North Dakota St":    "North Dakota State Bison",
    "North Texas":        "North Texas Mean Green",
    "Ohio":               "Ohio Bobcats",
    "Oral Roberts":       "Oral Roberts Golden Eagles",
    "Portland St":        "Portland State Vikings",
    "Presbyterian":       "Presbyterian Blue Hose",
    "Quinnipiac":         "Quinnipiac Bobcats",
    "Radford":            "Radford Highlanders",
    "Robert Morris":      "Robert Morris Colonials",
    "SE Louisiana":       "SE Louisiana Lions",
    "Sacred Heart":       "Sacred Heart Pioneers",
    "San Jose St":        "San José State Spartans",
    "Santa Clara":        "Santa Clara Broncos",
    "Seattle":            "Seattle U Redhawks",
    "USC Upstate":        "South Carolina Upstate Spartans",
    "Southeast Missouri St": "Southeast Missouri State Redhawks",
    "SIU Edwardsville":   "SIU Edwardsville Cougars",
    "Southern Indiana":   "Southern Indiana Screaming Eagles",
    "Stonehill":          "Stonehill Skyhawks",
    "Tennessee St":       "Tennessee State Tigers",
    "Texas A&M-CC":       "Texas A&M-Corpus Christi Islanders",
    "UC San Diego":       "UC San Diego Tritons",
    "La.-Monroe":         "UL Monroe Warhawks",
    "UNC Wilmington":     "UNC Wilmington Seahawks",
    "UT Rio Grande Valley": "UT Rio Grande Valley Vaqueros",
    "Vermont":            "Vermont Catamounts",
    "Weber St":           "Weber State Wildcats",
    "Western Illinois":   "Western Illinois Leathernecks",
    "Western Michigan":   "Western Michigan Broncos",
    "William & Mary":     "William & Mary Tribe",
    "North Florida":      "North Florida Ospreys",

    # Saint / St. schools
    "St. Mary's":         "Saint Mary's Gaels",
    "Saint Mary's":       "Saint Mary's Gaels",
    "Saint Joseph's":     "Saint Joseph's Hawks",
    "Saint Louis":        "Saint Louis Billikens",
    "Saint Peter's":      "Saint Peter's Peacocks",
    "Saint Francis":      "Saint Francis Red Flash",
    "Loyola Marymount":   "Loyola Marymount Lions",
    "St. John's":         "St. John's Red Storm",
    "St. Bonaventure":    "St. Bonaventure Bonnies",
    "St. Joseph's":       "Saint Joseph's Hawks",
    "St. Louis":          "Saint Louis Billikens",
    "Saint Louis":        "Saint Louis Billikens",
    "St. Francis (PA)":   "Saint Francis Red Flash",
    "St. Francis (NY)":   "St. Francis Brooklyn Terriers",
    "St. Peter's":        "Saint Peter's Peacocks",
    "Mount St. Mary's":   "Mount St. Mary's Mountaineers",
    "St. Thomas":         "St. Thomas Tommies",
}

# Invert for reverse lookup
_MANUAL_INV = {v: k for k, v in MANUAL.items()}


def _clean(name: str) -> str:
    """Lowercase, normalize saint/st., strip common suffixes for fuzzy matching."""
    name = str(name).lower().strip()
    # Normalize "st." <-> "saint" so they match each other
    name = name.replace("st. ", "saint ").replace("st.", "saint")
    for suffix in [" bulldogs"," blue devils"," tar heels"," wildcats"," bears",
                   " tigers"," eagles"," panthers"," hawks"," wolves"," lions",
                   " spartans"," trojans"," bruins"," ducks"," beavers"," huskies",
                   " cyclones"," hawkeyes"," boilermakers"," hoosiers"," badgers",
                   " buckeyes"," wolverines"," nittany lions"," terrapins",
                   " mountaineers"," razorbacks"," rebels"," bulldogs"," aggies",
                   " cowboys"," longhorns"," sooners"," red raiders"," cougars",
                   " mustangs"," horned frogs"," seminoles"," gators"," hurricanes",
                   " yellow jackets"," demon deacons"," cavaliers"," hokies",
                   " wolfpack"," golden bears"," cardinals"," orange"," fighting irish",
                   " aztecs"," lobos"," rams"," falcons"," owls"," penguins",
                   " flyers"," pilots"," dons"," gaels"," toreros"," waves",
                   " anteaters"," lumberjacks"," colonels"," saints"," hatters",
                   " musketeers"," bearcats"," retrievers"," spiders"," dukes"]:
        name = name.replace(suffix, "")
    return name.strip()


def _build_cache(bart_names: list, espn_names: list) -> tuple[dict, dict]:
    """Build b2e (bart->espn) and e2b (espn->bart) dicts dynamically."""
    b2e, e2b = {}, {}

    # Start with manual overrides
    for b, e in MANUAL.items():
        b2e[b] = e
        e2b[e] = b

    # Auto-match remaining
    espn_clean = {_clean(e): e for e in espn_names if e not in _MANUAL_INV}
    for b in bart_names:
        if b in b2e:
            continue
        bc = _clean(b)
        if bc in espn_clean:
            e = espn_clean[bc]
            b2e[b] = e
            e2b[e] = b

    return b2e, e2b


# Module-level cache
_b2e: dict = {}
_e2b: dict = {}


def build(bart_names: list, espn_names: list):
    """Call once to initialize the mapping from live data."""
    global _b2e, _e2b
    _b2e, _e2b = _build_cache(bart_names, espn_names)


def to_espn(bart_name: str) -> str:
    """Convert BartTorvik short name to ESPN full name."""
    return _b2e.get(bart_name, bart_name)


def to_bart(espn_name: str) -> str:
    """Convert ESPN full name to BartTorvik short name."""
    return _e2b.get(espn_name, espn_name)


def enrich_game_df(game_df: pd.DataFrame, team_df: pd.DataFrame) -> pd.DataFrame:
    """
    Add 'bart_name' column to game_df so we can join to team_df.
    Also adds 'opp_net_eff' and 'opp_difficulty' columns.
    """
    if game_df.empty or team_df.empty:
        return game_df

    gdf = game_df.copy()
    tdf = team_df.copy()
    gdf.columns = [c.lower() for c in gdf.columns]
    tdf.columns = [c.lower() for c in tdf.columns]

    # Build mapping if not already done
    if not _b2e:
        bart_names = tdf["team"].dropna().tolist()
        espn_names = gdf["team"].dropna().unique().tolist()
        build(bart_names, espn_names)

    # Map ESPN opponent name -> BartTorvik name -> net_eff
    net_lookup = dict(zip(tdf["team"], tdf["net_eff"])) if "net_eff" in tdf.columns else {}

    def opp_net(espn_opp):
        bart = to_bart(str(espn_opp))
        return net_lookup.get(bart)

    gdf["opp_net_eff"] = gdf["opponent"].apply(opp_net)
    gdf["opp_net_eff"] = pd.to_numeric(gdf["opp_net_eff"], errors="coerce")

    def difficulty(ne):
        if ne is None or pd.isna(ne): return "—"
        if ne >= 15:  return "🔴 Elite"
        if ne >= 8:   return "🟠 Strong"
        if ne >= 2:   return "🟡 Average"
        if ne >= -5:  return "🟢 Below Avg"
        return "⚪ Weak"

    gdf["opp_difficulty"] = gdf["opp_net_eff"].apply(difficulty)
    return gdf


def get_team_games(game_df: pd.DataFrame, team_df: pd.DataFrame, bart_name: str) -> pd.DataFrame:
    """
    Get all games for a BartTorvik team name from the ESPN game history.
    Always rebuilds the map with the full dataset to avoid stale cache issues.
    """
    if game_df.empty:
        return pd.DataFrame()

    gdf = game_df.copy()
    gdf.columns = [c.lower() for c in gdf.columns]

    # Always rebuild with full data — cheap operation, avoids stale map issues
    bart_names = team_df["team"].dropna().tolist() if not team_df.empty else []
    espn_names = gdf["team"].dropna().unique().tolist()
    build(bart_names, espn_names)

    espn_name = to_espn(bart_name)

    # If direct match fails, try cleaned fuzzy match only — no first-word guessing
    # (first-word matching causes "North Carolina" -> "Northeastern" type mismatches)
    if espn_name == bart_name:
        bc = _clean(bart_name)
        espn_clean_map = {_clean(en): en for en in espn_names}
        if bc in espn_clean_map:
            espn_name = espn_clean_map[bc]

    return gdf[gdf["team"] == espn_name].copy()