"""Campaign Controller & Views for Rabbi David 50 Replies & Personal Reading Room
"""
import os
import sys
import json
import time
import hmac
import hashlib
import base64
import secrets
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent

OFFER_HMAC_SECRET = 'rd_reading_room_hmac_sec_2026_10_9f8e7d6c5b4a'
ADMIN_SECRET = 'rd_admin_2026_secret'

BOOK_DETAILS = {
    'legacy': {
        'id': 'legacy',
        'title': 'The 5 Laws of Ancient Jewish Wealth',
        'subtitle': 'The Generational Vault',
        'category': 'Family & Legacy',
        'desc': 'Wealth that outlives you four generations: shared values, governance and education for an enduring family legacy. 208 pages.',
        'cover': '/images/cover-generational.webp',
        'price_cents': 3200,
        'was_price': '$62',
        'now_price': '$32',
        'price_id': 'price_1ULpxDQPUFXetkqGUJTb5kLA',
        'download': '/download/generational-wealth.html'
    },
    'protection': {
        'id': 'protection',
        'title': 'The Jewish Shield Against Financial Ruin',
        'subtitle': 'The Jewish Shield',
        'category': 'Protection & Resilience',
        'desc': 'Historical frameworks for protecting what you have built: risk, contingency and resilience against sudden crisis. 163 pages.',
        'cover': '/images/cover-shield.webp',
        'price_cents': 3200,
        'was_price': '$49',
        'now_price': '$32',
        'price_id': 'price_1ULpxEQPUFXetkqGvGXhXYJM',
        'download': '/download/protection.html'
    },
    'ceo': {
        'id': 'ceo',
        'title': 'Ancient Jewish Rules for Commercial Dominance',
        'subtitle': 'The Torah CEO Code',
        'category': 'Business Stewardship',
        'desc': 'Twelve principles on honest negotiation, partnerships and decisions, from the Torah CEO teachings. 150 pages.',
        'cover': '/images/cover-commercial.webp',
        'price_cents': 3200,
        'was_price': '$46',
        'now_price': '$32',
        'price_id': 'price_1ULpxFQPUFXetkqG7I6XUlrX',
        'download': '/download/torah-ceo-code.html'
    },
    'rituals': {
        'id': 'rituals',
        'title': 'The 7 Hidden Money Rituals of Secret Jewish Dynasties',
        'subtitle': 'The 7 Money Rituals',
        'category': 'Sacred Rituals',
        'desc': 'Seven daily practices to anchor gratitude, boundary setting, and quiet purpose around money. 37 pages.',
        'cover': '/images/cover-rituals.webp',
        'price_cents': 3200,
        'was_price': '$32',
        'now_price': '$32',
        'price_id': 'price_1UOfXCQPUFXetkqG1LYWXI7Y',
        'download': '/download/rituals.html'
    },
    'morning': {
        'id': 'morning',
        'title': "The Rabbi's Morning Wealth Blessing",
        'subtitle': "The Morning Blessing",
        'category': 'Daily Devotional',
        'desc': 'Seven sacred Hebrew morning blessings for daily bread, quiet mind, and family favor. 212 pages.',
        'cover': '/images/ebook-prayer-cover.webp',
        'price_cents': 3200,
        'was_price': '$49',
        'now_price': '$32',
        'price_id': 'price_1UOfX6QPUFXetkqGvcQeqjWm',
        'download': '/download/morning-blessing.html'
    },
    'bundle_all': {
        'id': 'bundle_all',
        'title': 'The Complete 6-Book Master Archive',
        'subtitle': 'The Entire Library',
        'category': 'The Whole Library · Best Value',
        'desc': 'Every prayer, daily practice, business teaching, generational blueprint and protection framework in one unified collection. 980+ pages.',
        'cover': '/images/cover-kabbalah.webp',
        'price_cents': 9700,
        'was_price': '$200',
        'now_price': '$97',
        'price_id': 'price_1ULpxIQPUFXetkqGPF3jgXVM',
        'download': '/download/all-access.html'
    },
    'complete': {
        'id': 'complete',
        'title': 'The Master Kabbalah Wealth System',
        'subtitle': 'The 3-Book Trilogy',
        'category': '3-Book Trilogy',
        'desc': 'Morning Blessing, 7 Money Rituals and the Complete Wealth System, together.',
        'cover': '/images/cover-kabbalah.webp',
        'price_cents': 6700,
        'was_price': '$120',
        'now_price': '$67',
        'price_id': 'price_1ULpxIQPUFXetkqGNRkOLTYK',
        'download': '/download/complete.html'
    }
}

class TokenResult:
    def __init__(self, is_valid, email, exp, err, book_id=None):
        self.is_valid = is_valid
        self.email = email
        self.exp = exp
        self.err = err
        self.book_id = book_id
    def __iter__(self):
        return iter((self.is_valid, self.email, self.exp, self.err))
    def __getitem__(self, index):
        return (self.is_valid, self.email, self.exp, self.err)[index]
    def __len__(self):
        return 4
    def __repr__(self):
        return f"<TokenResult valid={self.is_valid} email={self.email} exp={self.exp} err={self.err} book={self.book_id}>"

def make_offer_token(email: str, expires_at: int, book_id: str = None) -> str:
    email_clean = email.strip().lower()
    exp = int(expires_at)
    cfg_secret = os.environ.get('OFFER_HMAC_SECRET') or OFFER_HMAC_SECRET
    if book_id:
        payload = f"{email_clean}|{exp}|{book_id.strip()}"
    else:
        payload = f"{email_clean}|{exp}"
    sig = hmac.new(cfg_secret.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()
    raw = f"{payload}|{sig}".encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')

LETTERS_LOOKUP_CACHE = None

def lookup_letter_info(email: str):
    global LETTERS_LOOKUP_CACHE
    email_clean = email.strip().lower()
    if LETTERS_LOOKUP_CACHE is None:
        lookup_path = ROOT / 'data' / 'letters_lookup.json'
        if not lookup_path.is_file():
            lookup_path = Path(r"D:\playwright\rabbidavid-reading-room\letters_lookup.json")
        if lookup_path.is_file():
            try:
                LETTERS_LOOKUP_CACHE = json.loads(lookup_path.read_text(encoding='utf-8'))
            except Exception:
                LETTERS_LOOKUP_CACHE = {}
        else:
            LETTERS_LOOKUP_CACHE = {}
    return LETTERS_LOOKUP_CACHE.get(email_clean, {})

def lookup_letter_book(email: str) -> str:
    info = lookup_letter_info(email)
    return info.get('book_id') or 'morning'

def verify_offer_token(token: str) -> TokenResult:
    if not token:
        return TokenResult(False, None, 0, 'missing_token', None)
    try:
        padded = token + '=' * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode('ascii')).decode('utf-8')
        parts = decoded.split('|')
        cfg_secret = os.environ.get('OFFER_HMAC_SECRET') or OFFER_HMAC_SECRET
        
        if len(parts) == 4:
            email, exp_str, book_id, sig = parts
            email_clean = email.strip().lower()
            exp = int(exp_str)
            expected_sig = hmac.new(cfg_secret.encode('utf-8'), f"{email_clean}|{exp}|{book_id}".encode('utf-8'), hashlib.sha256).hexdigest()
            if not secrets.compare_digest(sig, expected_sig):
                return TokenResult(False, None, 0, 'invalid_signature', None)
        elif len(parts) == 3:
            email, exp_str, sig = parts
            email_clean = email.strip().lower()
            exp = int(exp_str)
            book_id = None
            expected_sig = hmac.new(cfg_secret.encode('utf-8'), f"{email_clean}|{exp}".encode('utf-8'), hashlib.sha256).hexdigest()
            if not secrets.compare_digest(sig, expected_sig):
                return TokenResult(False, None, 0, 'invalid_signature', None)
        else:
            return TokenResult(False, None, 0, 'malformed_token', None)

        now_ts = int(time.time())
        if exp <= now_ts:
            return TokenResult(False, email_clean, exp, 'expired', book_id)

        if not book_id:
            book_id = lookup_letter_book(email_clean)

        return TokenResult(True, email_clean, exp, None, book_id)
    except Exception as ex:
        return TokenResult(False, None, 0, f'exception: {ex}', None)

def init_campaign_tables(server_module):
    with server_module.LOCK:
        with server_module.connection() as con:
            con.execute('''
                CREATE TABLE IF NOT EXISTS reply_slots (
                    id TEXT PRIMARY KEY,
                    campaign TEXT,
                    email TEXT UNIQUE,
                    session_id TEXT,
                    order_id TEXT,
                    created INTEGER
                )
            ''')
            con.execute('''
                CREATE TABLE IF NOT EXISTS reply_questions (
                    id TEXT PRIMARY KEY,
                    email TEXT,
                    name TEXT,
                    question TEXT,
                    session_id TEXT UNIQUE,
                    status TEXT DEFAULT 'pending',
                    created INTEGER,
                    answered_at INTEGER
                )
            ''')
            con.execute('''
                CREATE TABLE IF NOT EXISTS gift_redemptions (
                    token TEXT PRIMARY KEY,
                    email TEXT,
                    redeemed_at INTEGER
                )
            ''')
            con.commit()

def get_supabase_client(server_module):
    sb = getattr(server_module, 'SUPABASE', None)
    if sb and getattr(sb, 'configured', False):
        return sb
    cfg = getattr(server_module, 'CONFIG', None)
    if not cfg:
        try:
            cfg_path = Path(__file__).resolve().parent / "config.json"
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if cfg and hasattr(server_module, 'SupabaseClient'):
        try:
            client = server_module.SupabaseClient(cfg)
            if client.is_configured():
                return client
        except Exception:
            pass
    return None

def get_reply_slots_count(server_module, campaign='reply50_2026_10'):
    # Check Supabase if configured
    try:
        sb = get_supabase_client(server_module)
        if sb:
            res = sb._request(f'/rest/v1/sessions?user_id=eq.campaign:{campaign}&select=id', method='GET', use_service_key=True)
            if res.get('status') == 200 and isinstance(res.get('data'), list):
                return len(res['data'])
    except Exception as e:
        print(f"[SUPABASE SLOTS COUNT ERROR] {e}", flush=True)

    with server_module.connection() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS reply_slots (
            id TEXT PRIMARY KEY, campaign TEXT, email TEXT UNIQUE,
            session_id TEXT, order_id TEXT, created INTEGER)''')
        row = con.execute("SELECT COUNT(DISTINCT email) FROM reply_slots WHERE campaign=?", (campaign,)).fetchone()
        return row[0] if row else 0

def reserve_reply_slot(server_module, email: str, session_id: str, order_id: str = '', campaign='reply50_2026_10'):
    email_clean = email.strip().lower()
    now_ts = int(time.time())
    with server_module.LOCK:
        with server_module.connection() as con:
            con.execute('''CREATE TABLE IF NOT EXISTS reply_slots (
                id TEXT PRIMARY KEY, campaign TEXT, email TEXT UNIQUE,
                session_id TEXT, order_id TEXT, created INTEGER)''')
            existing = con.execute("SELECT id FROM reply_slots WHERE email=? AND campaign=?", (email_clean, campaign)).fetchone()
            if existing:
                return True, "already_reserved"
            total = con.execute("SELECT COUNT(DISTINCT email) FROM reply_slots WHERE campaign=?", (campaign,)).fetchone()[0]
            if total >= 50:
                return False, "slots_full"
            slot_id = f"slot_{session_id}_{int(time.time())}"
            con.execute("INSERT OR REPLACE INTO reply_slots (id, campaign, email, session_id, order_id, created) VALUES (?, ?, ?, ?, ?, ?)",
                        (slot_id, campaign, email_clean, session_id, order_id, now_ts))
            con.commit()

    # Sync to Supabase
    try:
        sb = get_supabase_client(server_module)
        if sb:
            sb._request('/rest/v1/sessions', method='POST', data={
                'id': f'slot:{session_id}',
                'user_id': f'campaign:{campaign}',
                'data': {'email': email_clean, 'session_id': session_id, 'order_id': order_id, 'created': now_ts},
                'updated': now_ts
            }, use_service_key=True)
    except Exception as e:
        print(f"[SUPABASE SLOT SYNC ERROR] {e}", flush=True)

    return True, "reserved"

def render_offer_closed_html():
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>This invitation has closed · Rabbi David</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
body{background:#f7f2e8;color:#1d1a16;font:16px/1.6 Inter,system-ui,sans-serif;margin:0;padding:80px 20px;text-align:center}
.box{max-width:540px;margin:0 auto;background:#fffdf8;border:1px solid #e4d9c4;border-radius:14px;padding:40px 30px}
.logo{font-size:14px;letter-spacing:4px;text-transform:uppercase;color:#a8812f;font-weight:600}
h1{font:600 36px/1.1 "Cormorant Garamond",Georgia,serif;margin:16px 0}
p{color:#6b6157;font-size:16px;margin:0 0 24px}
a.btn{display:inline-block;background:#18233a;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600}
</style>
</head>
<body>
<div class="box">
  <div class="logo">Rabbi David</div>
  <h1>This invitation has closed</h1>
  <p>The private reader's pricing closed on Sunday, October 11 at 8:00 PM EDT. The full library remains available on the main website.</p>
  <a class="btn" href="https://rabbidavid.org">Visit the Library</a>
</div>
</body>
</html>"""

def render_invalid_link_html():
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Invalid link · Rabbi David</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
body{background:#f7f2e8;color:#1d1a16;font:16px/1.6 Inter,system-ui,sans-serif;margin:0;padding:80px 20px;text-align:center}
.box{max-width:540px;margin:0 auto;background:#fffdf8;border:1px solid #e4d9c4;border-radius:14px;padding:40px 30px}
.logo{font-size:14px;letter-spacing:4px;text-transform:uppercase;color:#a8812f;font-weight:600}
h1{font:600 36px/1.1 "Cormorant Garamond",Georgia,serif;margin:16px 0}
p{color:#6b6157;font-size:16px;margin:0 0 24px}
a.btn{display:inline-block;background:#18233a;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600}
</style>
</head>
<body>
<div class="box">
  <div class="logo">Rabbi David</div>
  <h1>Invalid link</h1>
  <p>This invitation link is not valid or has been modified.</p>
  <a class="btn" href="https://rabbidavid.org">Visit the Library</a>
</div>
</body>
</html>"""

def render_personal_reading_room_html(token, email, first_name, book_id, expires_at):
    personal_book = BOOK_DETAILS.get(book_id) or BOOK_DETAILS['morning']
    bundle = BOOK_DETAILS['bundle_all']
    other_books = [b for b in [BOOK_DETAILS['legacy'], BOOK_DETAILS['protection'], BOOK_DETAILS['ceo'], BOOK_DETAILS['rituals'], BOOK_DETAILS['morning']] if b['id'] != personal_book['id']]

    other_cards_html = ""
    for b in other_books:
        other_cards_html += f"""
    <article class="card" data-book="{b['id']}">
      <img src="{b['cover']}" alt="{b['title']} cover" loading="lazy">
      <div class="cat">{b['category']}</div>
      <h3 class="serif">{b['title']}</h3>
      <p>{b['desc']}</p>
      <div class="price"><span class="was">{b['was_price']}</span><span class="now">{b['now_price']}</span></div>
      <a class="btn btn-dark" href="#" data-offer-buy="{b['id']}">Get it for $32</a>
    </article>"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<title>Chosen for you, {first_name} · Rabbi David</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;0,700;1,500&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<script src="/js/reading-room.js" defer></script>
<style>
:root{{
  --ink:#1d1a16; --muted:#6b6157; --paper:#f7f2e8; --card:#fffdf8; --line:#e4d9c4;
  --gold:#a8812f; --gold-soft:#f1e6cc; --navy:#18233a; --ok:#2f6b4a;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--paper);color:var(--ink);font:16px/1.6 Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
.serif{{font-family:"Cormorant Garamond",Georgia,serif}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 16px}}

/* top bar */
.bar{{background:var(--navy);color:#f3ead7;text-align:center;font-size:14px;padding:10px 16px;position:sticky;top:0;z-index:50}}
.bar b{{color:#e8c77a;font-variant-numeric:tabular-nums;letter-spacing:.5px}}

/* hero */
header{{text-align:center;padding:56px 0 28px}}
.logo{{font-size:15px;letter-spacing:4px;text-transform:uppercase;color:var(--gold);font-weight:600}}
h1{{font-size:clamp(34px,6vw,54px);line-height:1.08;margin:14px 0 14px;font-weight:600}}
.lede{{max-width:620px;margin:0 auto;color:var(--muted);font-size:17px}}
.letter{{max-width:620px;margin:30px auto 0;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:24px 26px;text-align:left;font-size:16px}}
.letter p+p{{margin-top:10px}}
.sign{{font-style:italic;font-size:22px;margin-top:12px;color:var(--navy)}}

/* real countdown */
.clock{{display:flex;justify-content:center;gap:10px;margin:28px 0 6px}}
.clock div{{background:var(--card);border:1px solid var(--line);border-radius:12px;min-width:78px;padding:10px 6px;text-align:center}}
.clock span{{display:block;font:600 30px/1 "Cormorant Garamond",serif;font-variant-numeric:tabular-nums}}
.clock small{{font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted)}}
.clock-note{{text-align:center;color:var(--muted);font-size:13px}}

/* real reply slots counter */
.reply-badge{{display:inline-block;background:var(--navy);color:#f3ead7;border:1px solid var(--gold);border-radius:99px;padding:6px 18px;font-size:13.5px;font-weight:600;letter-spacing:0.5px}}
.reply-badge.closed{{background:#374151;border-color:#4b5563;color:#d1d5db}}

/* personal book feature */
.personal-feature{{margin:36px 0 24px;background:#fffdf8;border:2px solid var(--gold);border-radius:18px;padding:32px;display:grid;grid-template-columns:220px 1fr;gap:30px;align-items:center;box-shadow:0 8px 30px rgba(168,129,47,0.12)}}
.personal-feature img{{width:100%;max-width:200px;aspect-ratio:2/3;object-fit:cover;border-radius:10px;box-shadow:0 12px 28px rgba(0,0,0,0.18)}}
.personal-badge{{display:inline-block;background:var(--gold);color:#fff;font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:5px 12px;border-radius:99px;margin-bottom:8px}}
.personal-feature h2{{font-size:32px;line-height:1.15;margin:8px 0;font-weight:600;color:var(--navy)}}
.personal-feature p{{color:var(--muted);font-size:16px;line-height:1.6}}

/* archive feature */
.feature{{margin:32px 0 18px;background:var(--navy);color:#f3ead7;border-radius:18px;padding:30px;display:grid;grid-template-columns:260px 1fr;gap:30px;align-items:center}}
.stack{{position:relative;height:230px}}
.stack img{{position:absolute;width:118px;border-radius:6px;box-shadow:0 10px 24px rgba(0,0,0,.45)}}
.tag{{display:inline-block;background:#e8c77a;color:var(--navy);font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;padding:5px 10px;border-radius:99px}}
.feature h2{{font-size:34px;line-height:1.1;margin:12px 0 8px;font-weight:600;color:#fff}}
.feature p{{color:#cfc6b3}}
.feature ul{{list-style:none;margin:12px 0 0;display:grid;gap:4px;font-size:15px;color:#e6dcc6}}
.feature li:before{{content:"✦ ";color:#e8c77a}}
.price{{display:flex;align-items:baseline;gap:12px;margin:18px 0 14px;flex-wrap:wrap}}
.was{{text-decoration:line-through;opacity:.6;font-size:20px}}
.now{{font:700 44px/1 "Cormorant Garamond",serif}}
.save{{font-size:13px;font-weight:600;color:#e8c77a}}

/* buttons */
.btn{{display:inline-block;border:0;cursor:pointer;text-decoration:none;font:600 15px Inter,sans-serif;border-radius:10px;padding:14px 22px;text-align:center;transition:transform .1s,filter .15s}}
.btn:active{{transform:translateY(1px)}}
.btn-gold{{background:#e8c77a;color:var(--navy)}}
.btn-gold:hover{{filter:brightness(1.05)}}
.btn-dark{{background:var(--navy);color:#fff;width:100%}}
.btn-dark:hover{{filter:brightness(1.2)}}
.btn.loading{{opacity:.75;pointer-events:none}}

/* grid */
.section-title{{text-align:center;margin:54px 0 6px;font-size:32px;font-weight:600}}
.section-sub{{text-align:center;color:var(--muted);margin-bottom:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:18px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;display:flex;flex-direction:column}}
.card img{{width:100%;aspect-ratio:2/3;object-fit:cover;border-radius:8px;background:var(--gold-soft)}}
.cat{{font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--gold);font-weight:600;margin-top:14px}}
.card h3{{font-size:22px;line-height:1.15;margin:4px 0 6px;font-weight:600}}
.card p{{font-size:14px;color:var(--muted);flex:1}}
.card .price{{margin:12px 0}}
.card .was{{font-size:17px;color:var(--muted);opacity:1}}
.card .now{{font-size:34px;color:var(--navy)}}

/* trust */
.trust{{margin:40px 0 60px;display:flex;justify-content:center;gap:30px;color:var(--muted);font-size:13px;flex-wrap:wrap}}

/* closed state */
.closed{{display:none;text-align:center;padding:100px 16px;max-width:540px;margin:0 auto}}
footer{{text-align:center;padding:30px 16px;color:var(--muted);font-size:13px;border-top:1px solid var(--line);margin-top:40px}}
footer a{{color:var(--muted)}}

body.is-closed .open-only{{display:none}}
body.is-closed .closed{{display:block}}

@media (max-width:720px){{
  .personal-feature{{grid-template-columns:1fr;text-align:center;padding:22px}}
  .personal-feature img{{margin:0 auto}}
  .feature{{grid-template-columns:1fr;padding:22px}}
  .stack{{height:190px;max-width:260px;margin:0 auto;width:100%}}
  .grid{{grid-template-columns:1fr}}
  .clock div{{min-width:66px}}
  .clock span{{font-size:26px}}
}}
</style>
</head>
<body data-token="{token}" data-email="{email}" data-book="{personal_book['id']}" data-expires="{expires_at * 1000}">

<div class="bar open-only">Private reader's pricing · closes Sunday, Oct 11 · <b id="bar-clock">--:--:--</b></div>

<main class="wrap open-only">
  <header>
    <div class="logo">Rabbi David</div>
    <h1 class="serif">Chosen for you, {first_name}</h1>
    <p class="lede">I have set aside this specific book from my library for you, alongside the full collection, with personal reader's pricing until Sunday.</p>

    <div class="clock" aria-label="Time remaining">
      <div><span id="c-h">--</span><small>Hours</small></div>
      <div><span id="c-m">--</span><small>Minutes</small></div>
      <div><span id="c-s">--</span><small>Seconds</small></div>
    </div>
    <p class="clock-note">Closes Sunday, Oct 11 at 8:00 PM EDT</p>

    <div id="reply-slots-wrap" style="text-align:center; margin:16px auto 0;">
      <div id="reply-slots-badge" class="reply-badge">
        <span id="slots-count">50</span> of 50 personal replies left
      </div>
    </div>

    <div id="offer-error" style="display:none; max-width:620px; margin:20px auto 0; background:#fde8e8; border:1px solid #f8b4b4; color:#9b1c1c; border-radius:10px; padding:14px 18px; text-align:center; font-size:15px; font-weight:500;"></div>
  </header>

  <!-- 1. The Chosen Book on Top at $32 -->
  <section class="personal-feature" data-book="{personal_book['id']}">
    <div>
      <img src="{personal_book['cover']}" alt="{personal_book['title']} cover">
    </div>
    <div>
      <span class="personal-badge">Your Personal Selection · $32</span>
      <h2 class="serif">{personal_book['title']}</h2>
      <p>{personal_book['desc']}</p>
      <div class="price">
        <span class="was">{personal_book['was_price']}</span>
        <span class="now">{personal_book['now_price']}</span>
      </div>
      <a class="btn btn-gold" style="display:inline-block; width:auto; padding:16px 32px;" href="#" data-offer-buy="{personal_book['id']}">Take This Book — {personal_book['now_price']}</a>
    </div>
  </section>

  <!-- 2. The Complete 6-Book Collection at $97 -->
  <section class="feature" data-book="bundle_all">
    <div class="stack" aria-hidden="true">
      <img src="/images/cover-shield.webp" alt="" style="left:0;top:40px;transform:rotate(-8deg)">
      <img src="/images/cover-generational.webp" alt="" style="left:44px;top:14px;transform:rotate(-2deg)">
      <img src="/images/cover-kabbalah.webp" alt="" style="left:92px;top:30px;transform:rotate(5deg)">
      <img src="/images/cover-commercial.webp" alt="" style="left:134px;top:58px;transform:rotate(10deg)">
    </div>
    <div>
      <span class="tag">The whole library · best value</span>
      <h2 class="serif">The Complete 6-Book Master Archive</h2>
      <p>Every prayer, daily practice, business teaching, generational blueprint and protection framework in one collection.</p>
      <ul>
        <li>All 6 books in PDF · 980+ pages</li>
        <li>Instant download and delivery to your email</li>
        <li>Lifetime access</li>
      </ul>
      <div class="price"><span class="was">$200</span><span class="now">$97</span><span class="save">You keep $103</span></div>
      <a class="btn btn-gold" href="#" data-offer-buy="bundle_all">Acquire the Full Archive — $97</a>
    </div>
  </section>

  <!-- 3. Other Individual Books at $32 -->
  <h2 class="section-title serif">The Rest of the Library</h2>
  <p class="section-sub">Each single volume at reader's price ($32) until Sunday.</p>

  <section class="grid">
    {other_cards_html}
  </section>

  <div class="trust">
    <span>🔒 Secure checkout by Stripe</span>
    <span>📩 Instant delivery to your email</span>
    <span>↺ Repeat purchases permitted</span>
  </div>
</main>

<section class="closed">
  <div class="logo">Rabbi David</div>
  <h1 class="serif">This reading room has closed</h1>
  <p class="lede" style="margin-top:12px">The reader's pricing closed on Sunday, October 11 at 8:00 PM EDT. The full library remains available on the website at its usual price.</p>
  <p style="margin-top:26px"><a class="btn btn-dark" style="width:auto" href="/#catalog">Visit the library</a></p>
</section>

<footer>
  © 2026 Rabbi David · <a href="/terms">Terms</a> · <a href="/refund">Refunds</a> · <a href="/privacy">Privacy</a>
</footer>

</body>
</html>"""

def render_gift_page(email: str, first_name: str, already_redeemed: bool = False):
    status_msg = "Your gift has been sent to your email." if not already_redeemed else "Your gift was already redeemed and sent to your email."
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Your Gift from Rabbi David</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
body{{background:#f7f2e8;color:#1d1a16;font:16px/1.6 Inter,system-ui,sans-serif;margin:0;padding:60px 20px;text-align:center}}
.box{{max-width:580px;margin:0 auto;background:#fffdf8;border:1px solid #e4d9c4;border-radius:14px;padding:40px 30px;box-shadow:0 8px 30px rgba(0,0,0,0.06)}}
.logo{{font-size:14px;letter-spacing:4px;text-transform:uppercase;color:#a8812f;font-weight:600}}
h1{{font:600 34px/1.15 "Cormorant Garamond",Georgia,serif;margin:18px 0 14px;color:#18233a}}
p{{color:#6b6157;font-size:16px;line-height:1.6;margin:0 0 20px}}
.book-card{{display:flex;align-items:center;gap:20px;background:#f7f2e8;border-radius:10px;padding:20px;margin:24px 0;text-align:left}}
.book-card img{{width:90px;aspect-ratio:2/3;object-fit:cover;border-radius:6px;box-shadow:0 4px 12px rgba(0,0,0,0.1)}}
.book-info h3{{font:600 20px/1.2 "Cormorant Garamond",Georgia,serif;margin:0 0 6px;color:#18233a}}
.book-info p{{margin:0;font-size:14px;color:#6b6157}}
a.btn{{display:inline-block;background:#18233a;color:#f3ead7;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:15px}}
a.btn:hover{{background:#0d1624}}
</style>
</head>
<body>
<div class="box">
  <div class="logo">Rabbi David</div>
  <h1>A Quiet Gift For Your Mornings</h1>
  <p>Shalom {first_name},</p>
  <p>{status_msg} We have delivered <em>The Rabbi's Morning Wealth Blessing</em> directly to <strong>{email}</strong>.</p>
  
  <div class="book-card">
    <img src="/images/ebook-prayer-cover.webp" alt="Cover">
    <div class="book-info">
      <h3>The Rabbi's Morning Wealth Blessing</h3>
      <p>Seven sacred Hebrew morning blessings for daily bread, quiet mind, and family favor.</p>
    </div>
  </div>

  <p>You can also download your copy right now below:</p>
  <a class="btn" href="/download/morning-blessing.html">Download Your Gift Ebook</a>
</div>
</body>
</html>"""

def render_thanks_question_html(session_id: str, email: str, name: str, book_id: str, has_slot: bool, existing_question: str = None):
    book = BOOK_DETAILS.get(book_id) or BOOK_DETAILS['bundle_all']
    
    if existing_question:
        form_content = f"""
        <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:10px; padding:22px; margin:26px 0; text-align:left;">
          <h3 style="color:#166534; font-size:18px; margin-bottom:8px;">✓ Question Received</h3>
          <p style="color:#166534; font-size:15px; margin-bottom:12px;">Your quiet question has been received. Rabbi David will reply directly to <strong>{email}</strong> within seven days.</p>
          <div style="background:#fff; border:1px solid #dcfce7; border-radius:8px; padding:14px; font-style:italic; color:#374151; font-size:14.5px;">"{existing_question}"</div>
        </div>
        """
    elif has_slot:
        form_content = f"""
        <div style="background:#fffdf8; border:1.5px solid #d4af37; border-radius:12px; padding:26px; margin:26px 0; text-align:left;">
          <div style="display:inline-block; background:#18233a; color:#f3ead7; font-size:11px; font-weight:700; letter-spacing:1px; text-transform:uppercase; padding:4px 10px; border-radius:99px; margin-bottom:10px;">1 of 50 Places Reserved</div>
          <h2 class="serif" style="font-size:24px; color:#18233a; margin-bottom:8px;">Ask Rabbi David Your 1 or 2 Quiet Questions</h2>
          <p style="font-size:14.5px; color:#6b6157; margin-bottom:16px;">As promised in the letter, Rabbi David will personally read and reply to your question by email within seven days.</p>
          
          <form id="replyForm">
            <input type="hidden" name="session_id" value="{session_id}">
            <textarea id="questionText" name="question" rows="5" maxlength="600" required placeholder="Write your quiet questions here (about family, work, debt, or daily blessing)..." style="width:100%; border:1px solid #d1d5db; border-radius:8px; padding:12px; font:15px Inter,sans-serif; resize:vertical; box-sizing:border-box;"></textarea>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
              <span id="charCount" style="font-size:12px; color:#6b7280;">0 / 600 characters</span>
              <button type="submit" id="submitBtn" style="background:#18233a; color:#fff; border:0; padding:12px 24px; border-radius:8px; font-weight:600; font-size:14.5px; cursor:pointer;">Submit Your Question</button>
            </div>
          </form>
          <div id="formMsg" style="display:none; margin-top:14px; font-size:14.5px; font-weight:500;"></div>
        </div>
        <script src="/js/thanks-question.js" defer></script>
        """
    else:
        form_content = """
        <div style="background:#f3f4f6; border:1px solid #d1d5db; border-radius:10px; padding:22px; margin:26px 0; text-align:left;">
          <h3 style="color:#374151; font-size:18px; margin-bottom:8px;">The 50 Personal Replies Have Been Filled</h3>
          <p style="color:#6b7280; font-size:14.5px; margin:0;">All fifty personal reply places for this week have been taken. Your book purchase is complete and your download is ready below.</p>
        </div>
        """

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Thank You for Your Order · Rabbi David</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
body{{background:#f7f2e8;color:#1d1a16;font:16px/1.6 Inter,system-ui,sans-serif;margin:0;padding:50px 20px;text-align:center}}
.box{{max-width:620px;margin:0 auto;background:#fffdf8;border:1px solid #e4d9c4;border-radius:14px;padding:36px 30px;box-shadow:0 8px 30px rgba(0,0,0,0.06)}}
.logo{{font-size:14px;letter-spacing:4px;text-transform:uppercase;color:#a8812f;font-weight:600}}
h1{{font:600 34px/1.15 "Cormorant Garamond",Georgia,serif;margin:16px 0 10px;color:#18233a}}
p{{color:#6b6157;font-size:16px;line-height:1.6;margin:0 0 16px}}
.serif{{font-family:"Cormorant Garamond",Georgia,serif}}
a.btn{{display:inline-block;background:#18233a;color:#f3ead7;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:15px}}
a.btn:hover{{background:#0d1624}}
</style>
</head>
<body>
<div class="box">
  <div class="logo">Rabbi David</div>
  <h1>Thank You, {name}</h1>
  <p>Your order is confirmed. A receipt and your permanent library access have been sent to <strong>{email}</strong>.</p>
  
  {form_content}

  <div style="margin-top:30px; padding-top:24px; border-top:1px solid #e4d9c4;">
    <p style="font-size:15px; color:#4b5563; margin-bottom:14px;">Access your purchased book immediately below:</p>
    <a class="btn" href="{book['download']}?session_id={session_id}&paid=true">Download {book['title']}</a>
  </div>
</div>
</body>
</html>"""

def render_admin_dashboard_html(questions, slots_count, admin_key):
    pending_count = sum(1 for q in questions if q['status'] == 'pending')
    answered_count = sum(1 for q in questions if q['status'] == 'answered')

    rows_html = ""
    for q in questions:
        created_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(q['created']))
        badge_style = "background:#fef3c7; color:#92400e;" if q['status'] == 'pending' else "background:#d1fae5; color:#065f46;"
        action_html = f"""<button class="btn-mark-answered" data-id="{q['id']}" data-key="{admin_key}" style="background:#18233a; color:#fff; border:0; padding:6px 12px; border-radius:6px; font-size:12px; cursor:pointer;">Mark Answered</button>""" if q['status'] == 'pending' else "<span style='color:#059669; font-size:12px;'>✓ Completed</span>"

        rows_html += f"""
        <tr style="border-bottom:1px solid #e5e7eb;">
          <td style="padding:12px 10px; font-size:13px; color:#6b7280; white-space:nowrap;">{created_str}</td>
          <td style="padding:12px 10px; font-size:14px; font-weight:600; color:#111;">{q['name']}<br><span style="font-size:12px; font-weight:400; color:#4b5563;">{q['email']}</span></td>
          <td style="padding:12px 10px; font-size:14px; color:#374151; max-width:380px;">{q['question']}</td>
          <td style="padding:12px 10px; text-align:center;"><span style="display:inline-block; padding:4px 8px; border-radius:99px; font-size:12px; font-weight:600; {badge_style}">{q['status']}</span></td>
          <td style="padding:12px 10px; text-align:center;">{action_html}</td>
        </tr>
        """

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Admin Dashboard · 50 Personal Replies</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
body{{background:#f9fafb;color:#111827;font:14px/1.5 Inter,sans-serif;margin:0;padding:30px 20px}}
.wrap{{max-width:1100px;margin:0 auto}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin:20px 0 30px}}
.stat{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:20px}}
.stat-num{{font-size:32px;font-weight:700;color:#18233a;line-height:1}}
.stat-label{{font-size:12px;font-weight:600;text-transform:uppercase;color:#6b7280;margin-top:6px;letter-spacing:0.5px}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden}}
th{{background:#f3f4f6;text-align:left;padding:12px 10px;font-size:12px;font-weight:600;text-transform:uppercase;color:#4b5563;letter-spacing:0.5px}}
</style>
<script src="/js/admin.js" defer></script>
</head>
<body>
<div class="wrap">
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <h1 style="font-size:24px; font-weight:700; color:#18233a;">Rabbi David · 50 Personal Questions Dashboard</h1>
    <span style="font-size:12px; background:#e0e7ff; color:#3730a3; padding:4px 10px; border-radius:99px; font-weight:600;">Admin Mode</span>
  </div>

  <div class="stats">
    <div class="stat">
      <div class="stat-num">{slots_count} / 50</div>
      <div class="stat-label">Occupied Reply Slots</div>
    </div>
    <div class="stat">
      <div class="stat-num">{len(questions)}</div>
      <div class="stat-label">Total Questions Received</div>
    </div>
    <div class="stat">
      <div class="stat-num" style="color:#d97706;">{pending_count}</div>
      <div class="stat-label">Pending Reply</div>
    </div>
    <div class="stat">
      <div class="stat-num" style="color:#059669;">{answered_count}</div>
      <div class="stat-label">Answered &amp; Sent</div>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Date</th>
        <th>Reader</th>
        <th>Question Text (Max 600 chars)</th>
        <th style="text-align:center;">Status</th>
        <th style="text-align:center;">Action</th>
      </tr>
    </thead>
    <tbody>
      {rows_html if rows_html else '<tr><td colspan="5" style="text-align:center; padding:30px; color:#6b7280;">No questions submitted yet.</td></tr>'}
    </tbody>
  </table>
</div>
</body>
</html>"""


def send_gift_email_resend(email: str, first_name: str):
    resend_key = os.environ.get('RESEND_API_KEY')
    if not resend_key:
        try:
            cfg = json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))
            resend_key = cfg.get('smtp_password') or cfg.get('resend_api_key')
        except Exception:
            resend_key = ''

    name_clean = first_name.strip() if first_name and first_name.strip() != 'friend' else 'my friend'
    unsub_url = f"https://rabbidavid.org/api/unsubscribe?e={urllib.parse.quote(email)}"
    download_url = "https://rabbidavid.org/download/morning-blessing.html"

    subject = "Your gift: The Rabbi's Morning Wealth Blessing"
    text_body = f"""Shalom {name_clean},

As promised in my letter, I am sending you this as a quiet gift: The Rabbi's Morning Wealth Blessing.

You can read and download your copy here:
{download_url}

There is nothing to pay, ever.

May your house be quiet and your bread certain,
Rabbi David

—
You receive this because you read one of my books or took the reflection at rabbidavid.org.
If you would rather not hear from me, reply "remove" or click: {unsub_url}"""

    html_body = f"""<div dir="ltr" style="font-family: Georgia, serif; font-size: 16px; line-height: 1.6; color: #111;">
<p>Shalom {name_clean},</p>
<p>As promised in my letter, I am sending you this as a quiet gift: <em>The Rabbi's Morning Wealth Blessing</em>.</p>
<p style="margin:24px 0;"><a href="{download_url}" style="background:#18233a; color:#f3ead7; padding:12px 22px; text-decoration:none; border-radius:6px; font-weight:600; display:inline-block;">Download Your Gift Ebook</a></p>
<p>There is nothing to pay, ever.</p>
<p>May your house be quiet and your bread certain,<br>Rabbi David</p>
<br>
—<br>
<span style="font-size:12px; color:#666;">You receive this because you read one of my books or took the reflection at rabbidavid.org.<br>
If you would rather not hear from me, reply "remove" or click: <a href="{unsub_url}">unsubscribe</a></span>
</div>"""

    payload = {
        "from": "Rabbi David <david@rabbidavid.org>",
        "to": [email],
        "subject": subject,
        "reply_to": "david@rabbidavid.org",
        "text": text_body,
        "html": html_body,
        "headers": {
            "List-Unsubscribe": f"<{unsub_url}>, <mailto:david@rabbidavid.org?subject=Unsubscribe>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"
        }
    }

    pdf_path = ROOT / 'ebooks' / 'The-Rabbis-Morning-Wealth-Blessing.pdf'
    if pdf_path.is_file():
        try:
            pdf_bytes = pdf_path.read_bytes()
            if len(pdf_bytes) < 15 * 1024 * 1024:
                payload["attachments"] = [{
                    "filename": "The-Rabbis-Morning-Wealth-Blessing.pdf",
                    "content": base64.b64encode(pdf_bytes).decode('ascii')
                }]
        except Exception as e:
            print(f"[ATTACHMENT ERROR] {e}", flush=True)

    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode('utf-8'),
        headers={
            "Authorization": f"Bearer {resend_key}",
            "Content-Type": "application/json",
            "User-Agent": "RabbiDavid/1.0"
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return True, data.get("id"), None
    except urllib.error.HTTPError as he:
        err_msg = he.read().decode('utf-8', errors='ignore')
        return False, None, f"HTTP {he.code}: {err_msg}"
    except Exception as ex:
        return False, None, str(ex)

def handle_go(handler, token: str, server_module):
    token = token.strip()
    res = verify_offer_token(token)
    if not res.is_valid:
        if res.err == 'expired':
            html = render_offer_closed_html()
            return handler.send(410, body=html.encode('utf-8'), mime='text/html; charset=utf-8')
        html = render_invalid_link_html()
        return handler.send(400, body=html.encode('utf-8'), mime='text/html; charset=utf-8')

    book_id = res.book_id or lookup_letter_book(res.email) or 'morning'
    book = BOOK_DETAILS.get(book_id) or BOOK_DETAILS['morning']

    stripe_key = os.environ.get('STRIPE_SECRET_KEY') or server_module.CONFIG.get('stripe_secret_key')
    if not stripe_key:
        return handler.send(500, {'ok': False, 'error': 'Payment service is not configured'})

    origin = server_module.public_origin()
    success_url = f"{origin}/thanks-question?s={{CHECKOUT_SESSION_ID}}&book={book['id']}"
    cancel_url = f"{origin}/for/{token}"

    params = {
        'payment_method_types[]': 'card',
        'mode': 'payment',
        'success_url': success_url,
        'cancel_url': cancel_url,
        'line_items[0][price]': book['price_id'],
        'line_items[0][quantity]': '1',
        'customer_email': res.email,
        'metadata[campaign]': 'reply50_2026_10',
        'metadata[book_id]': book['id'],
        'metadata[token]': token,
    }
    now_ts = int(time.time())
    if res.exp >= now_ts + 1800:
        params['expires_at'] = str(min(res.exp, now_ts + 86400))

    data = urllib.parse.urlencode(params).encode('utf-8')
    req = urllib.request.Request(
        'https://api.stripe.com/v1/checkout/sessions',
        data=data,
        headers={'Authorization': f'Bearer {stripe_key}'}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            cs_data = json.loads(r.read().decode('utf-8'))
        checkout_url = cs_data.get('url')
        if not checkout_url:
            return handler.send(500, {'ok': False, 'error': 'No checkout URL returned by Stripe'})
        return handler.send(303, body=b'', headers={'Location': checkout_url, 'Cache-Control': 'no-store, no-cache, must-revalidate'})
    except Exception as ex:
        print(f"[STRIPE GO ERROR] {ex}", flush=True)
        return handler.send(500, {'ok': False, 'error': f'Payment gateway error: {ex}'})

def handle_for(handler, token: str, server_module):
    token = token.strip()
    res = verify_offer_token(token)
    if not res.is_valid:
        if res.err == 'expired':
            html = render_offer_closed_html()
            return handler.send(410, body=html.encode('utf-8'), mime='text/html; charset=utf-8')
        html = render_invalid_link_html()
        return handler.send(400, body=html.encode('utf-8'), mime='text/html; charset=utf-8')

    email = res.email
    user_info = server_module.lookup_recipient_info(email)
    first_name = user_info.get('first_name', '')
    if not first_name:
        letter_info = lookup_letter_info(email)
        first_name = letter_info.get('first_name', '')
    display_name = first_name if first_name else 'friend'
    book_id = res.book_id or lookup_letter_book(email) or 'morning'

    html = render_personal_reading_room_html(
        token=token,
        email=email,
        first_name=display_name,
        book_id=book_id,
        expires_at=res.exp
    )
    return handler.send(200, body=html.encode('utf-8'), mime='text/html; charset=utf-8')

def handle_gift(handler, token: str, server_module):
    token = token.strip()
    res = verify_offer_token(token)
    if not res.is_valid:
        if res.err == 'expired':
            html = render_offer_closed_html()
            return handler.send(410, body=html.encode('utf-8'), mime='text/html; charset=utf-8')
        html = render_invalid_link_html()
        return handler.send(400, body=html.encode('utf-8'), mime='text/html; charset=utf-8')

    email = res.email
    letter_info = lookup_letter_info(email)

    with server_module.connection() as con:
        con.execute("CREATE TABLE IF NOT EXISTS gift_redemptions (token TEXT PRIMARY KEY, email TEXT, redeemed_at INTEGER)")
        existing = con.execute("SELECT redeemed_at FROM gift_redemptions WHERE token=? OR email=?", (token, email)).fetchone()

    first_name = letter_info.get('first_name') or server_module.lookup_recipient_info(email).get('first_name', '') or 'friend'

    if existing:
        html = render_gift_page(email, first_name, already_redeemed=True)
        return handler.send(200, body=html.encode('utf-8'), mime='text/html; charset=utf-8')

    now_ts = int(time.time())
    with server_module.LOCK:
        with server_module.connection() as con:
            con.execute("INSERT OR REPLACE INTO gift_redemptions (token, email, redeemed_at) VALUES (?, ?, ?)", (token, email, now_ts))
            con.commit()

    try:
        sb = get_supabase_client(server_module)
        if sb:
            sb._request('/rest/v1/sessions', method='POST', data={
                'id': f'gift:{token}',
                'user_id': 'gift:reply50_2026_10',
                'data': {'email': email, 'token': token, 'redeemed_at': now_ts},
                'updated': now_ts
            }, use_service_key=True)
    except Exception as e:
        print(f"[SUPABASE GIFT SYNC ERROR] {e}", flush=True)

    send_gift_email_resend(email, first_name)

    html = render_gift_page(email, first_name, already_redeemed=False)
    return handler.send(200, body=html.encode('utf-8'), mime='text/html; charset=utf-8')

def handle_thanks_question(handler, u, server_module):
    qs = urllib.parse.parse_qs(u.query)
    session_id = qs.get('s', [''])[0] or qs.get('session_id', [''])[0]
    book_id = qs.get('book', [''])[0] or 'bundle_all'
    if not session_id:
        return handler.send(400, body=b"Missing purchase session ID", mime='text/plain')

    stripe_key = os.environ.get('STRIPE_SECRET_KEY') or server_module.CONFIG.get('stripe_secret_key')
    if not stripe_key:
        return handler.send(500, body=b"Payment service unconfigured", mime='text/plain')

    try:
        req = urllib.request.Request(f'https://api.stripe.com/v1/checkout/sessions/{session_id}', headers={'Authorization': f'Bearer {stripe_key}'})
        with urllib.request.urlopen(req, timeout=15) as r:
            cs = json.loads(r.read().decode('utf-8'))
    except Exception as ex:
        print(f"[STRIPE VERIFY ERROR] {ex}", flush=True)
        return handler.send(403, body=b"Could not verify purchase session.", mime='text/plain')

    if cs.get('payment_status') != 'paid':
        return handler.send(403, body=b"A completed purchase is required to access this page.", mime='text/plain')

    email = (cs.get('customer_details') or {}).get('email') or cs.get('customer_email') or ''
    name = (cs.get('customer_details') or {}).get('name') or 'Valued Reader'
    meta = cs.get('metadata') or {}
    order_book = meta.get('book_id') or book_id

    reserved, reason = reserve_reply_slot(server_module, email, session_id, order_id=cs.get('id', ''))
    has_slot = (reserved is True) or (reason == 'already_reserved')

    with server_module.connection() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS reply_questions (
            id TEXT PRIMARY KEY, email TEXT, name TEXT, question TEXT,
            session_id TEXT UNIQUE, status TEXT DEFAULT 'pending',
            created INTEGER, answered_at INTEGER
        )''')
        q_row = con.execute("SELECT question, created, status FROM reply_questions WHERE session_id=?", (session_id,)).fetchone()

    html = render_thanks_question_html(
        session_id=session_id,
        email=email,
        name=name,
        book_id=order_book,
        has_slot=has_slot,
        existing_question=q_row[0] if q_row else None
    )
    return handler.send(200, body=html.encode('utf-8'), mime='text/html; charset=utf-8')

def handle_submit_reply_question(handler, body, server_module):
    session_id = (body.get('session_id') or '').strip()
    question = (body.get('question') or '').strip()
    if not session_id or not question:
        return handler.send(400, {'ok': False, 'error': 'Missing session_id or question'})
    if len(question) > 600:
        return handler.send(400, {'ok': False, 'error': 'Question exceeds 600 characters limit'})

    stripe_key = os.environ.get('STRIPE_SECRET_KEY') or server_module.CONFIG.get('stripe_secret_key')
    try:
        req = urllib.request.Request(f'https://api.stripe.com/v1/checkout/sessions/{session_id}', headers={'Authorization': f'Bearer {stripe_key}'})
        with urllib.request.urlopen(req, timeout=15) as r:
            cs = json.loads(r.read().decode('utf-8'))
        if cs.get('payment_status') != 'paid':
            return handler.send(403, {'ok': False, 'error': 'Purchase is not verified'})
    except Exception as ex:
        return handler.send(403, {'ok': False, 'error': f'Could not verify purchase: {ex}'})

    email = (cs.get('customer_details') or {}).get('email') or cs.get('customer_email') or ''
    name = (cs.get('customer_details') or {}).get('name') or 'Valued Reader'
    now_ts = int(time.time())

    qid = f"q_{session_id}"
    with server_module.LOCK:
        with server_module.connection() as con:
            con.execute('''INSERT OR REPLACE INTO reply_questions 
                           (id, email, name, question, session_id, status, created) 
                           VALUES (?, ?, ?, ?, ?, 'pending', ?)''',
                        (qid, email, name, question, session_id, now_ts))
            con.commit()

    try:
        sb = get_supabase_client(server_module)
        if sb:
            sb._request('/rest/v1/sessions', method='POST', data={
                'id': f'q:{session_id}',
                'user_id': 'question:reply50_2026_10',
                'data': {
                    'email': email,
                    'name': name,
                    'question': question,
                    'session_id': session_id,
                    'status': 'pending',
                    'created': now_ts
                },
                'updated': now_ts
            }, use_service_key=True)
    except Exception as e:
        print(f"[SUPABASE QUESTION SYNC ERROR] {e}", flush=True)

    return handler.send(200, {'ok': True, 'message': 'Your question has been received. Rabbi David will reply within seven days.'})

def handle_admin_questions(handler, u, server_module):
    qs = urllib.parse.parse_qs(u.query)
    key = qs.get('key', [''])[0]
    auth_header = handler.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        key = auth_header[7:].strip()
    if key != ADMIN_SECRET:
        return handler.send(401, body=b"Unauthorized: Admin key required (?key=...)", mime='text/plain')

    with server_module.connection() as con:
        con.execute('''CREATE TABLE IF NOT EXISTS reply_questions (
            id TEXT PRIMARY KEY, email TEXT, name TEXT, question TEXT,
            session_id TEXT UNIQUE, status TEXT DEFAULT 'pending',
            created INTEGER, answered_at INTEGER
        )''')
        rows = con.execute("SELECT id, email, name, question, session_id, status, created, answered_at FROM reply_questions ORDER BY created DESC").fetchall()
        slots_count = get_reply_slots_count(server_module)

    questions = []
    for r in rows:
        questions.append({
            'id': r[0],
            'email': r[1],
            'name': r[2],
            'question': r[3],
            'session_id': r[4],
            'status': r[5],
            'created': r[6],
            'answered_at': r[7]
        })

    html = render_admin_dashboard_html(questions, slots_count, key)
    return handler.send(200, body=html.encode('utf-8'), mime='text/html; charset=utf-8')

def handle_admin_mark_answered(handler, body, u, server_module):
    qs = urllib.parse.parse_qs(u.query)
    key = qs.get('key', [''])[0] or body.get('key', '')
    if key != ADMIN_SECRET:
        return handler.send(401, {'ok': False, 'error': 'Unauthorized'})
    qid = body.get('id')
    now_ts = int(time.time())
    with server_module.LOCK:
        with server_module.connection() as con:
            con.execute("UPDATE reply_questions SET status='answered', answered_at=? WHERE id=?", (now_ts, qid))
            con.commit()
    return handler.send(200, {'ok': True, 'status': 'answered'})

def handle_reply_slots(handler, server_module):
    taken = get_reply_slots_count(server_module)
    remaining = max(0, 50 - taken)
    return handler.send(200, {
        'ok': True,
        'total': 50,
        'taken': taken,
        'remaining': remaining,
        'active': taken < 50
    })
