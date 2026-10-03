#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎬 IPTV Mega v16 - Auto-Update + 500 Sources + ML
- 500+ مصدر
- تحديث تلقائي كل 12 ساعة
- محرك ML + Inverted Index
- GitHub Actions Ready
"""

import os
import re
import sys
import csv
import math
import json
import time
import socket
import argparse
import difflib
import threading
import tempfile
import http.server
import socketserver
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============ المكتبات ============
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("❌ ثبّت: pip install requests")
    sys.exit(1)

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

try:
    import qrcode
    HAS_QR = True
except ImportError:
    HAS_QR = False


# ============================================================
# [1] النظام
# ============================================================
def detect_environment():
    env = {"os": "unknown", "is_android": False, "is_pydroid": False,
           "is_termux": False, "is_github": False, "supports_color": True}
    if os.environ.get("GITHUB_ACTIONS") == "true":
        env["is_github"] = True
        env["supports_color"] = False
        env["os"] = "github"
        return env
    if sys.platform.startswith("win"):
        env["os"] = "windows"
    elif sys.platform == "darwin":
        env["os"] = "macos"
    elif sys.platform.startswith("linux"):
        env["os"] = "linux"
        if "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ:
            env["is_android"] = True
        if "PYDROID" in os.environ or "com.aefyr.pydroid" in str(Path.home()).lower():
            env["is_pydroid"] = True
            env["is_android"] = True
            env["supports_color"] = False
        if "com.termux" in str(Path.home()).lower():
            env["is_termux"] = True
            env["is_android"] = True
    return env


ENV = detect_environment()


if ENV["supports_color"]:
    class C:
        R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"; B = "\033[94m"
        M = "\033[95m"; CY = "\033[96m"; W = "\033[97m"
        BOLD = "\033[1m"; DIM = "\033[2m"; END = "\033[0m"
else:
    class C:
        R = G = Y = B = M = CY = W = BOLD = DIM = END = ""


def get_output_dir():
    # على GitHub Actions نستخدم مجلد المشروع
    if ENV["is_github"]:
        p = Path.cwd() / "playlists"
        p.mkdir(parents=True, exist_ok=True)
        return p

    cands = []
    if ENV["is_android"]:
        cands = [
            Path("/storage/emulated/0/Download/IPTV"),
            Path("/sdcard/Download/IPTV"),
            Path("/storage/emulated/0/Download"),
            Path.home() / "IPTV",
        ]
    elif ENV["os"] == "windows":
        cands = [Path.home() / "Downloads" / "IPTV",
                 Path.home() / "Desktop" / "IPTV_Results"]
    else:
        cands = [Path.home() / "Downloads" / "IPTV",
                 Path.home() / "IPTV_Results"]

    print(f"{C.CY}🔍 البحث عن مجلد قابل للكتابة...{C.END}")
    for p in cands:
        try:
            p.mkdir(parents=True, exist_ok=True)
            t = p / ".w"; t.write_text("ok"); t.read_text(); t.unlink()
            print(f"{C.G}✅ مجلد الحفظ: {C.Y}{p}{C.END}")
            return p
        except Exception:
            pass

    try:
        fb = Path(tempfile.gettempdir()) / "IPTV_Results"
        fb.mkdir(parents=True, exist_ok=True)
        return fb
    except Exception:
        return Path.cwd()


OUTPUT_DIR = get_output_dir()
CACHE_DIR = OUTPUT_DIR / ".cache"
CACHE_FILE = CACHE_DIR / "channels.json"
CHECK_CACHE_FILE = CACHE_DIR / "check_cache.json"
MODEL_FILE = OUTPUT_DIR / "model.json"
CUSTOM_FILE = OUTPUT_DIR / "custom_sources.json"
SOURCES_FILE = Path(__file__).with_name("sources.txt")

CACHE_DURATION = 60 * 60 * 12          # 12 ساعة
CHECK_CACHE_DURATION = 60 * 60 * 6     # 6 ساعات
AUTO_UPDATE_INTERVAL = 60 * 60 * 12    # 12 ساعة

MAX_WORKERS = 30
CHECK_WORKERS = 60
REQUEST_TIMEOUT = 20
CHECK_TIMEOUT = 8


# ============================================================
# [2] الجلسة
# ============================================================
def make_session():
    s = requests.Session()
    retry = Retry(total=2, backoff_factor=0.3,
                  status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry,
                         pool_connections=64, pool_maxsize=128)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({"User-Agent": "Mozilla/5.0 (IPTV-Mega/16)"})
    return s


SESSION = make_session()


# ============================================================
# [3] 🚀 500+ مصدر
# ============================================================
def build_sources():
    """بناء 500+ مصدر"""
    s = {}

    # ============ iptv-org الأساسية (5) ============
    s["💎 iptv-org كامل"] = "https://iptv-org.github.io/iptv/index.m3u"
    s["💎 iptv-org الفئات"] = "https://iptv-org.github.io/iptv/index.category.m3u"
    s["💎 iptv-org اللغات"] = "https://iptv-org.github.io/iptv/index.language.m3u"
    s["💎 iptv-org الدول"] = "https://iptv-org.github.io/iptv/index.country.m3u"
    s["💎 iptv-org المناطق"] = "https://iptv-org.github.io/iptv/index.region.m3u"

    # ============ iptv-org اللغات (65 لغة × 2) ============
    langs = [
        "ara","eng","fre","spa","ger","tur","rus","fas","hin","por",
        "ita","ukr","pol","dut","gre","heb","jpn","zho","kor","swe",
        "ron","cze","hun","bul","hrv","srp","sqi","hye","aze","kaz",
        "uzb","swa","ind","tha","vie","dan","fin","nor","slk","slv",
        "lit","lav","est","kat","msa","fil","ben","urd","pus","kur",
        "amh","som","hau","yor","zul","bos","cat","ceb","glg","isl",
        "khk","kir","lao","lat","mlt","mon","mya","nep","pan","sin",
        "tam","tel","tgk","tuk","wol","afr","cym","epo","eus","fao",
        "grn","haw","ibo","jav","kan","khm","mlg","mar","oci","orm",
        "que","sna","sot","tat","tgl","tsn","uig","ven","xho","zha",
    ]
    for lg in langs:
        s[f"🌐 {lg}"] = f"https://iptv-org.github.io/iptv/languages/{lg}.m3u"
        s[f"🔥 raw {lg}"] = f"https://raw.githubusercontent.com/iptv-org/iptv/master/streams/{lg}.m3u"

    # ============ iptv-org الدول (~180 دولة × 2) ============
    countries = [
        # عربية (22)
        "sa","iq","eg","ae","kw","qa","bh","om","jo","lb","sy",
        "ye","ps","ma","dz","tn","ly","sd","mr","so","dj","km",
        # أمريكا الشمالية
        "us","ca","mx","gl","bm","pm","pr","vi","ky","bs","bb","jm",
        "ht","do","cu","tt","ag","dm","gd","kn","lc","vc","aw","cw",
        "sx","bq","gp","mq","bl","mf",
        # أمريكا الجنوبية
        "br","ar","cl","co","pe","ve","ec","uy","py","bo","gy","sr","gf","fk",
        # أوروبا
        "uk","fr","de","it","es","pt","nl","be","ch","at","se","no","dk",
        "fi","is","ie","pl","cz","sk","hu","ro","bg","gr","hr","si","rs",
        "ba","mk","al","me","xk","md","ua","by","lt","lv","ee","ru","tr",
        "cy","mt","ad","mc","sm","va","li","lu","gi","fo","ax",
        # آسيا
        "in","pk","bd","lk","np","bt","mv","af","ir","cn","jp","kr",
        "tw","hk","mo","mn","kz","uz","tm","tj","kg","az","ge","am",
        "th","vn","la","kh","mm","my","sg","id","ph","bn","tl","io",
        # أفريقيا
        "za","ng","ke","et","gh","tz","ug","zm","zw","bw","na","mw",
        "mz","ao","cm","ci","sn","ml","bf","ne","td","sd","ss","cd",
        "cg","ga","gq","cf","st","gw","gn","lr","sl","gm","cv","mr",
        "dj","so","er","rw","bi","mg","mu","sc","km","yt","re",
        # أوقيانوسيا
        "au","nz","fj","pg","sb","vu","nc","pf","ws","to","tv","ki",
        "nr","pw","fm","mh","as","gu","mp","ck","nu","tk","wf","nf",
    ]
    for cc in countries:
        s[f"🌍 {cc.upper()}"] = f"https://iptv-org.github.io/iptv/countries/{cc}.m3u"
        s[f"🔥 raw {cc.upper()}"] = f"https://raw.githubusercontent.com/iptv-org/iptv/master/streams/{cc}.m3u"

    # ============ iptv-org الفئات (44) ============
    cats = [
        "news","sports","movies","music","kids","documentary",
        "entertainment","cooking","auto","travel","science","shopping",
        "comedy","culture","history","education","lifestyle","gaming",
        "talk","weather","animals","health","religious","fashion",
        "agriculture","arts","business","classic","general","beauty",
        "construction","farming","design","transport","esports","family",
        "legislative","outdoor","public","relax","series","shop",
        "top-100","undefined",
    ]
    for c in cats:
        s[f"📂 {c}"] = f"https://iptv-org.github.io/iptv/categories/{c}.m3u"

    # ============ iptv-org المناطق (9) ============
    for r in ["afr","amer","asia","eur","mena","namer","lamer","oce","carib"]:
        s[f"🌍 {r.upper()}"] = f"https://iptv-org.github.io/iptv/regions/{r}.m3u"

    # ============ Free-TV (20) ============
    for n, p in [
        ("كامل", "playlist.m3u8"),
        ("DE","playlists/playlist_germany.m3u8"),
        ("UK","playlists/playlist_uk.m3u8"),
        ("US","playlists/playlist_usa.m3u8"),
        ("FR","playlists/playlist_france.m3u8"),
        ("IT","playlists/playlist_italy.m3u8"),
        ("ES","playlists/playlist_spain.m3u8"),
        ("TR","playlists/playlist_turkey.m3u8"),
        ("IN","playlists/playlist_india.m3u8"),
        ("BR","playlists/playlist_brazil.m3u8"),
        ("RU","playlists/playlist_russia.m3u8"),
        ("NL","playlists/playlist_netherlands.m3u8"),
        ("PL","playlists/playlist_poland.m3u8"),
        ("PT","playlists/playlist_portugal.m3u8"),
        ("GR","playlists/playlist_greece.m3u8"),
        ("AT","playlists/playlist_austria.m3u8"),
        ("CH","playlists/playlist_switzerland.m3u8"),
        ("CZ","playlists/playlist_czechia.m3u8"),
        ("RO","playlists/playlist_romania.m3u8"),
        ("HU","playlists/playlist_hungary.m3u8"),
    ]:
        s[f"🔥 Free-TV {n}"] = f"https://raw.githubusercontent.com/Free-TV/IPTV/master/{p}"

    # ============ مصادر مجتمعية إضافية ============
    extra = {
        "🔥 Streams ALL": "https://raw.githubusercontent.com/iptv-org/iptv/master/streams/all.m3u",
        "🔥 Arabic Full": "https://iptv-org.github.io/iptv/languages/ara.m3u",
        "🔥 MENA": "https://iptv-org.github.io/iptv/regions/mena.m3u",
        "🔥 Sports+": "https://iptv-org.github.io/iptv/categories/sports.m3u",
        "🔥 Kids+": "https://iptv-org.github.io/iptv/categories/kids.m3u",
        "🔥 News+": "https://iptv-org.github.io/iptv/categories/news.m3u",
        "🔥 Movies+": "https://iptv-org.github.io/iptv/categories/movies.m3u",
        "🔥 Music+": "https://iptv-org.github.io/iptv/categories/music.m3u",
        "🔥 Documentary+": "https://iptv-org.github.io/iptv/categories/documentary.m3u",
        "🔥 Entertainment+": "https://iptv-org.github.io/iptv/categories/entertainment.m3u",
    }
    s.update(extra)

    return s


SOURCES = build_sources()
print(f"{C.G}✅ {len(SOURCES)} مصدر جاهز{C.END}")


def load_file_sources():
    """قراءة روابط IPTV الإضافية من sources.txt بصيغة URL أو اسم | URL."""
    custom = {}
    if not SOURCES_FILE.exists():
        return custom
    try:
        for raw in SOURCES_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                name, url = (part.strip() for part in line.split("|", 1))
            else:
                url = line
                name = f"Custom {len(custom) + 1}"
            if url.startswith(("http://", "https://", "file://")):
                custom[name or f"Custom {len(custom) + 1}"] = url
    except Exception as exc:
        print(f"{C.Y}⚠️ تعذر قراءة sources.txt: {exc}{C.END}")
    return custom


# ============================================================
# [4] الأسماء البديلة
# ============================================================
ALIASES = {
    "bein": "bein beinsport beinsports beinsports1 beinsports2 beinsports3 beinsports4 beinsports5 beinsports6 beinsports7 beinsports8 beinsports9 beinsports10 bein1 bein2 bein3 bein4 bein5 bein6 bein7 bein8 bein9 bein10 bein11 bein12 bein13 bein14 bein15 beinsport1 beinsport2 beinsport3 beinnews beinsportsnews beinsportsmax beinsportsmena beinsportsglobal bein4k beinsports4k بين بيان بيإن بيإنسبورت بينسبورت بنسبورت",
    "cartoon": "cartoon cartoonnetwork cn cartoon_net cartoonnetworkhd cartoonnetworkarabic boomerang كرتون كرتوننتورك بوميرانغ",
    "disney": "disney disneychannel disneyjunior disneyxd disneyplus disneychannelhd disneychannelarabic ديزني",
    "nick": "nick nickelodeon nickjr nicktoons nickelodeonhd nickelodeonarabic نيك نيكلوديون",
    "mbc": "mbc mbc1 mbc2 mbc3 mbc4 mbc5 mbcmax mbcdrama mbcaction mbcmovies mbcbollywood mbcmasr mbciraq mbcplus امبي",
    "rotana": "rotana rotanacinema rotanaclip rotanakhalijia rotanacomedy rotanadrama rotanamovies روتانا",
    "jazeera": "jazeera aljazeera aljazeeraenglish aljazeeraarabic aljazeeralive aljazeeramubasher aj aje aja الجزيرة",
    "arabiya": "arabia arabiya alarabiya alarabiyaenglish alarabiyaarabic alarabiyaalhadath العربية",
    "sky": "sky skysport skysports skysport1 skysport2 skysport3 skysportsnews skysportsarena skynews sky1 sky2 skyatlantic skycinema skymovies سكاي",
    "spacetoon": "spacetoon sptv سبستون سبيستون",
    "majid": "majid majidtv ماجد",
    "baraem": "baraem barem براعم",
    "natgeo": "natgeo nationalgeographic natgeowild natgeopeople natgeoadventure ناشيونال",
    "discovery": "discovery discoverychannel discoveryid discoveryscience discoverykids ديسكفري",
    "hbo": "hbo hbomax hbosignature hbocomedy hbofamily hbohits",
    "osn": "osn osnseries osnmovies osncomedy osnliving osnfirst",
    "shahid": "shahid shahidvip شاهد",
    "bbc": "bbc bbcnews bbcone bbctwo bbcarabic bbcworld bbcearth",
    "cnn": "cnn cnnnews cnnturk cnnarabic",
    "dubai": "dubai dubaitv dubaisports dubairacing دبي",
    "abudhabi": "abudhabi abudhabisports adsports أبوظبي",
    "saudi": "saudi sauditv saudisports ssc saudi24 السعودية",
    "kuwait": "kuwait kuwaittv kuwaitsport ktv الكويت",
    "qatar": "qatar qatartv alrayyan قطر",
    "oman": "oman omantv عمان",
    "bahrain": "bahrain bahraintv البحرين",
    "jordan": "jordan jordantv jrtsport الأردن",
    "lebanon": "lebanon lebanontv lbci mtvlebanon لبنان",
    "iraq": "iraq iraqtv iraqia alsharqiya baghdadia العراق",
    "syria": "syria syriatv addounia سوريا",
    "palestine": "palestine palestinetv pbc alaqsa فلسطين",
    "yemen": "yemen yementv اليمن",
    "morocco": "morocco moroccotv snrt 2m medi1tv المغرب",
    "algeria": "algeria algeriatv entv الجزائر",
    "tunisia": "tunisia tunisiatv watania hannibal تونس",
    "libya": "libya libyatv ليبيا",
    "sudan": "sudan sudantv السودان",
    "espn": "espn espn1 espn2 espn3 espnnews espnu espnplus",
    "eurosport": "eurosport eurosport1 eurosport2 eurosport3",
    "supersport": "supersport supersport1 supersport2 supersport3 ss1 ss2 ss3",
    "dazn": "dazn dazn1 dazn2 dazn4k",
    "nba": "nba nbatv",
    "nfl": "nfl nflnetwork",
    "ufc": "ufc ufcfightpass",
    "wwe": "wwe wwenetwork",
    "fox": "fox foxnews foxtv foxmovies foxsports foxsport فوكس",
    "canal": "canal canalplus canalplus1 canalplussport",
    "movistar": "movistar movistarplus movistardeportes",
    "mtv": "mtv mtvmusic mtvlive mtvhits",
    "natgeo_ar": "ناشيونال جيوغرافيك natgeographic ناشيونال جيوغرافيك",
}

# قنوات وعلامات كبرى تُفهرس تلقائيًا من المصادر المتاحة فقط.
# وجود الاسم هنا لا يعني أن القناة مجانية أو متاحة قانونيًا؛ الأداة تصدر
# فقط الروابط التي وجدتها في المصادر التي يملك المستخدم حق استخدامها.
FEATURED_QUERIES = {
    "bein-sports": "bein",
    "ssc": "ssc",
    "sky-sports": "skysport",
    "dazn": "dazn",
    "espn": "espn",
    "eurosport": "eurosport",
    "super-sport": "supersport",
    "fox-sports": "foxsport",
    "nba-tv": "nba",
    "nfl-network": "nfl",
    "ufc": "ufc",
    "wwe": "wwe",
    "al-jazeera": "jazeera",
    "al-arabiya": "arabiya",
    "bbc": "bbc",
    "cnn": "cnn",
    "mbc": "mbc",
    "rotana": "rotana",
    "osn": "osn",
    "shahid": "shahid",
    "cartoon-network": "cartoon",
    "disney": "disney",
    "nickelodeon": "nick",
    "spacetoon": "spacetoon",
    "nat-geo": "natgeo",
    "discovery": "discovery",
    "news": "news",
}


# ============================================================
# [5] التطبيع
# ============================================================
AR_DIA = re.compile(r'[\u064B-\u065F\u0670\u06D6-\u06ED]')

def normalize_ar(t):
    if not t:
        return ""
    t = AR_DIA.sub('', t).replace('\u0640', '')
    t = re.sub(r'[أإآٱ]', 'ا', t)
    t = t.replace('ة', 'ه').replace('ى', 'ي').replace('ؤ', 'و').replace('ئ', 'ي')
    t = t.replace('ک', 'ك').replace('ی', 'ي').replace('گ', 'ك')
    t = t.replace('چ', 'ج').replace('پ', 'ب').replace('ڤ', 'ف')
    return t


LATIN_MAP = str.maketrans({
    'é':'e','è':'e','ê':'e','ë':'e','á':'a','à':'a','â':'a','ä':'a',
    'í':'i','ì':'i','î':'i','ï':'i','ó':'o','ò':'o','ô':'o','ö':'o',
    'ú':'u','ù':'u','û':'u','ü':'u','ñ':'n','ç':'c','ý':'y','ÿ':'y'
})


def normalize_latin(t):
    t = t.lower().translate(LATIN_MAP)
    for a, b in [('ph','f'),('ck','k'),('qu','k'),('ee','i'),('oo','u'),
                 ('sh','s'),('th','t'),('gh','g'),('zh','z')]:
        t = t.replace(a, b)
    return t


def normalize(t):
    if not t:
        return ""
    t = normalize_ar(t.lower())
    t = normalize_latin(t)
    return re.sub(r'[^\w\u0600-\u06FF]', '', t)


def tokenize(text):
    if not text:
        return []
    return [w for w in re.split(r'[\s\-_./|:,()\[\]]+', text.lower()) if w and len(w) >= 2]


# ============================================================
# [6] صوتيات + N-grams + Fuzzy
# ============================================================
AR_PHON = {'ا':'A','ه':'A','ع':'A','ح':'A','ء':'A','ى':'A','ب':'B','پ':'B',
           'ت':'T','ط':'T','ث':'S','ج':'J','چ':'J','د':'D','ض':'D','ذ':'Z',
           'ر':'R','ز':'Z','س':'S','ص':'S','ش':'S','ف':'F','ڤ':'F','ق':'K',
           'ك':'K','خ':'K','غ':'G','ل':'L','م':'M','ن':'N','و':'W','ي':'Y',
           'ئ':'Y','گ':'K'}


def ar_phonetic(t):
    t = re.sub(r'[^\u0600-\u06FF]', '', normalize_ar(t))
    if not t:
        return ""
    out = []; prev = ''
    for ch in t:
        c = AR_PHON.get(ch, ch)
        if c != prev:
            out.append(c); prev = c
    return ''.join(out)


EN_SOUNDEX = {'b':'1','f':'1','p':'1','v':'1','c':'2','g':'2','j':'2','k':'2',
              'q':'2','s':'2','x':'2','z':'2','d':'3','t':'3','l':'4',
              'm':'5','n':'5','r':'6'}


def en_soundex(t):
    t = re.sub(r'[^a-z]', '', normalize_latin(t))
    if not t:
        return ""
    first = t[0].upper()
    codes = []; prev = EN_SOUNDEX.get(t[0], '0')
    for ch in t[1:]:
        c = EN_SOUNDEX.get(ch, '0')
        if c != '0' and c != prev:
            codes.append(c); prev = c
        elif c == '0':
            prev = '0'
    return (first + ''.join(codes) + "000")[:4]


def ngrams(text, n=3):
    if not text:
        return set()
    if len(text) < n:
        return {text}
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def jaro_winkler(s1, s2, p=0.1):
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    l1, l2 = len(s1), len(s2)
    md = max(0, max(l1, l2) // 2 - 1)
    m1 = [False]*l1; m2 = [False]*l2; matches = 0
    for i in range(l1):
        for j in range(max(0,i-md), min(i+md+1,l2)):
            if m2[j] or s1[i] != s2[j]:
                continue
            m1[i] = m2[j] = True; matches += 1; break
    if matches == 0:
        return 0.0
    k = t = 0
    for i in range(l1):
        if not m1[i]:
            continue
        while not m2[k]:
            k += 1
        if s1[i] != s2[k]:
            t += 1
        k += 1
    t //= 2
    jaro = (matches/l1 + matches/l2 + (matches - t)/matches) / 3.0
    prefix = 0
    for i in range(min(l1,l2,4)):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break
    return jaro + prefix * p * (1 - jaro)


def levenshtein_ratio(s1, s2):
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if len(s2) < len(s1) * 0.5:
        return 0.0
    prev = list(range(len(s2)+1))
    for i, c1 in enumerate(s1):
        curr = [i+1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j+1]+1, curr[j]+1, prev[j]+(c1 != c2)))
        prev = curr
    return 1.0 - prev[-1]/max(len(s1), len(s2))


# ============================================================
# [7] ML Model - Logistic Regression
# ============================================================
FEATURES = [
    "exact_name_match", "name_contains", "name_prefix", "token_overlap",
    "jaro_name", "levenshtein_name", "phonetic_ar", "phonetic_en",
    "group_match", "country_match", "has_logo", "is_premium",
    "is_hd", "name_length_score", "source_trust",
]


class MLModel:
    def __init__(self):
        self.weights = {f: 0.0 for f in FEATURES}
        self.bias = -3.0
        self.learning_rate = 0.05
        self.samples = 0
        for f, v in {
            "exact_name_match": 3.0, "name_contains": 2.0, "name_prefix": 1.5,
            "token_overlap": 2.5, "jaro_name": 2.0, "levenshtein_name": 1.0,
            "phonetic_ar": 1.0, "phonetic_en": 1.0, "group_match": 0.8,
            "country_match": 0.5, "has_logo": 0.3, "is_premium": 0.2,
            "is_hd": 0.4, "name_length_score": 0.5, "source_trust": 1.2,
        }.items():
            self.weights[f] = v

    def sigmoid(self, x):
        try:
            return 1.0 / (1.0 + math.exp(-max(-50, min(50, x))))
        except OverflowError:
            return 0.0 if x < 0 else 1.0

    def predict(self, x):
        z = self.bias + sum(self.weights[f]*x.get(f,0) for f in FEATURES)
        return self.sigmoid(z)

    def update(self, x, label):
        pred = self.predict(x)
        err = label - pred
        lr = self.learning_rate / (1 + self.samples*0.01)
        for f in FEATURES:
            self.weights[f] += lr * err * x.get(f, 0)
        self.bias += lr * err
        self.samples += 1

    def save(self, path):
        try:
            path.write_text(json.dumps({
                "weights": self.weights, "bias": self.bias,
                "samples": self.samples}, indent=2), encoding="utf-8")
        except Exception:
            pass

    def load(self, path):
        if not path.exists():
            return
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            for f in FEATURES:
                if f in d.get("weights", {}):
                    self.weights[f] = d["weights"][f]
            self.bias = d.get("bias", self.bias)
            self.samples = d.get("samples", 0)
        except Exception:
            pass


MODEL = MLModel()
MODEL.load(MODEL_FILE)


PREMIUM_KW = {"bein","skysport","dazn","espn","supersport","ssc",
              "eurosport","canalplus","movistar","hbo","cinemax",
              "showtime","starz","osn","shahid","netflix","disneyplus"}


def is_premium_channel(name):
    n = normalize(name)
    return any(k in n for k in PREMIUM_KW)


def source_trust(source):
    if not source:
        return 0.3
    s = source.lower()
    if "iptv-org" in s and "raw" not in s:
        return 1.0
    if "iptv-org" in s and "raw" in s:
        return 0.9
    if "free-tv" in s:
        return 0.8
    return 0.6


def extract_features(query, channel, source=""):
    q_norm = normalize(query.lower().strip())
    q_tokens = set(tokenize(query.lower()))
    name = channel.get("name", "")
    name_norm = normalize(name)
    name_low = name.lower()
    group_norm = normalize(channel.get("group", ""))
    country = normalize(channel.get("country", ""))

    f = {k: 0.0 for k in FEATURES}
    if q_norm == name_norm:
        f["exact_name_match"] = 1.0
    if q_norm and q_norm in name_norm:
        f["name_contains"] = 1.0
    if q_norm and name_norm.startswith(q_norm):
        f["name_prefix"] = 1.0
    n_tok = set(tokenize(name))
    if q_tokens and n_tok:
        f["token_overlap"] = len(q_tokens & n_tok) / len(q_tokens)
    f["jaro_name"] = jaro_winkler(q_norm, name_norm)
    f["levenshtein_name"] = levenshtein_ratio(q_norm, name_norm)
    if en_soundex(query) and en_soundex(query) == en_soundex(name):
        f["phonetic_en"] = 1.0
    if ar_phonetic(query) and ar_phonetic(query) == ar_phonetic(name):
        f["phonetic_ar"] = 1.0
    if q_norm and q_norm in group_norm:
        f["group_match"] = 1.0
    if q_norm and q_norm in country:
        f["country_match"] = 1.0
    if channel.get("logo"):
        f["has_logo"] = 1.0
    if is_premium_channel(name):
        f["is_premium"] = 1.0
    if re.search(r'\b(hd|fhd|4k|uhd)\b', name_low):
        f["is_hd"] = 1.0
    if len(name_norm) > 0:
        f["name_length_score"] = max(0.0, 1.0 - (len(name_norm)-5)/50)
    f["source_trust"] = source_trust(source)
    return f


# ============================================================
# [8] SearchIndex
# ============================================================
class SearchIndex:
    def __init__(self, channels_with_source):
        self.channels = list(channels_with_source)
        self.token_idx = defaultdict(set)
        self.ngram_idx = defaultdict(set)
        self.ph_en_idx = defaultdict(set)
        self.ph_ar_idx = defaultdict(set)
        self._build()

    def _build(self):
        for i, (ch, _) in enumerate(self.channels):
            full = f"{ch['name']} {ch['group']} " \
                   f"{ch.get('country','')} {ch.get('language','')} " \
                   f"{ch.get('tvg_id','')}"
            norm = normalize(full)
            for tok in set(tokenize(full)):
                tn = normalize(tok)
                if tn:
                    self.token_idx[tn].add(i)
            name_norm = normalize(ch["name"])
            if name_norm:
                self.token_idx[name_norm].add(i)
            for ng in ngrams(norm, 3):
                self.ngram_idx[ng].add(i)
            pe = en_soundex(ch["name"])
            if pe:
                self.ph_en_idx[pe].add(i)
            pa = ar_phonetic(ch["name"])
            if pa:
                self.ph_ar_idx[pa].add(i)

    def total(self):
        return len(self.channels)


def expand_query(q):
    if not q.strip():
        return []
    tokens = [t for t in q.strip().split() if t]
    expanded = []
    for tok in tokens:
        variants = {tok, normalize(tok)}
        tn = normalize(tok)
        for key, alts_str in ALIASES.items():
            kn = normalize(key)
            if kn and (kn in tn or tn in kn):
                for alt in alts_str.split():
                    variants.add(alt); variants.add(normalize(alt))
        if tok.endswith('s') and len(tok) > 3:
            variants.add(tok[:-1])
        variants.add(tok + 's')
        expanded.append({v for v in variants if v})
    return expanded


# ============================================================
# [9] المحرك
# ============================================================
class MaxEngine:
    def __init__(self, data):
        flat = []; seen = set()
        for src, chs in data.items():
            for ch in chs:
                k = (ch["name"].lower(), ch["url"])
                if k in seen:
                    continue
                seen.add(k); flat.append((ch, src))

        print(f"{C.CY}⏳ بناء الفهرس لـ {len(flat)} قناة...{C.END}")
        t0 = time.time()
        self.index = SearchIndex(flat)
        print(f"{C.G}✓ جاهز في {time.time()-t0:.2f}ث{C.END}")

    def _candidates(self, query_variants):
        cands = set()
        for tok_set in query_variants:
            for v in tok_set:
                vn = normalize(v)
                if not vn:
                    continue
                if vn in self.index.token_idx:
                    cands.update(self.index.token_idx[vn])
                if 2 <= len(vn) <= 5:
                    for key, s in self.index.token_idx.items():
                        if key.startswith(vn):
                            cands.update(s)
                pe = en_soundex(v)
                if pe:
                    cands.update(self.index.ph_en_idx.get(pe, set()))
                pa = ar_phonetic(v)
                if pa:
                    cands.update(self.index.ph_ar_idx.get(pa, set()))
                if len(vn) >= 4:
                    for ng in ngrams(vn, 3):
                        if ng in self.index.ngram_idx:
                            cands.update(self.index.ngram_idx[ng])
        return cands

    def search(self, query, min_score=0.2, limit=None, use_ml=True):
        if not query.strip():
            return []
        qv = expand_query(query)
        cands = self._candidates(qv)
        if not cands:
            cands = set(range(len(self.index.channels)))

        scored = []
        for idx in cands:
            if idx >= len(self.index.channels):
                continue
            ch, src = self.index.channels[idx]
            feats = extract_features(query, ch, src)
            has = (feats["name_contains"] > 0 or feats["exact_name_match"] > 0
                   or feats["name_prefix"] > 0 or feats["jaro_name"] > 0.75
                   or feats["levenshtein_name"] > 0.7
                   or feats["token_overlap"] >= 0.5
                   or feats["phonetic_en"] > 0 or feats["phonetic_ar"] > 0)
            if not has:
                continue
            score = MODEL.predict(feats) if use_ml else (
                feats["exact_name_match"]*3 + feats["name_contains"]*2 +
                feats["name_prefix"]*1.5 + feats["token_overlap"]*2.5 +
                feats["jaro_name"]*2 + feats["phonetic_en"]*1.5 +
                feats["phonetic_ar"]*1.5) / 12.0
            if score >= min_score:
                ch_copy = dict(ch)
                ch_copy["_source"] = src
                ch_copy["_score"] = round(score*100, 1)
                ch_copy["_features"] = feats
                scored.append((score, ch_copy))

        scored.sort(key=lambda x: -x[0])
        seen_urls = set(); results = []
        for s, ch in scored:
            if ch["url"] in seen_urls:
                continue
            seen_urls.add(ch["url"]); results.append(ch)
            if limit and len(results) >= limit:
                break
        return results

    def learn(self, chosen, rejected):
        if chosen.get("_features"):
            MODEL.update(chosen["_features"], 1)
        for ch in rejected[:5]:
            if ch.get("_features"):
                MODEL.update(ch["_features"], 0)
        MODEL.save(MODEL_FILE)

    def all(self):
        seen = set(); out = []
        for ch, _ in self.index.channels:
            if ch["url"] not in seen:
                seen.add(ch["url"]); out.append(ch)
        return out

    def total(self):
        return self.index.total()


# ============================================================
# [10] كاش الفحص
# ============================================================
CHECK_CACHE = {}


def load_check_cache():
    global CHECK_CACHE
    if CHECK_CACHE_FILE.exists():
        try:
            d = json.loads(CHECK_CACHE_FILE.read_text(encoding="utf-8"))
            if time.time() - d.get("ts", 0) < CHECK_CACHE_DURATION:
                CHECK_CACHE = d.get("cache", {})
        except Exception:
            pass


def save_check_cache():
    try:
        CHECK_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHECK_CACHE_FILE.write_text(
            json.dumps({"ts": time.time(), "cache": CHECK_CACHE},
                       ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


# ============================================================
# [11] التحميل
# ============================================================
def fetch_m3u(url):
    try:
        if url.startswith("file://"):
            return Path(url[7:]).read_text(encoding="utf-8", errors="ignore")
        r = SESSION.get(url, timeout=REQUEST_TIMEOUT, verify=False)
        r.raise_for_status()
        return r.text
    except Exception:
        return ""


def parse_m3u(text):
    chs = []; cur = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            name = line.split(",")[-1].strip() or "بدون اسم"
            def g(p):
                m = re.search(p, line)
                return m.group(1) if m else ""
            cur = {
                "name": name,
                "logo": g(r'tvg-logo="([^"]*)"'),
                "group": g(r'group-title="([^"]*)"') or "غير مصنف",
                "country": g(r'tvg-country="([^"]*)"'),
                "language": g(r'tvg-language="([^"]*)"'),
                "tvg_id": g(r'tvg-id="([^"]*)"'),
            }
        elif not line.startswith("#") and cur:
            cur["url"] = line; chs.append(cur); cur = {}
    return chs


def fetch_one(item):
    name, url = item
    text = fetch_m3u(url)
    if not text:
        return name, []
    chs = parse_m3u(text)
    seen = set(); uniq = []
    for ch in chs:
        k = (ch["name"], ch["url"])
        if k not in seen:
            seen.add(k); uniq.append(ch)
    return name, uniq


def load_cache():
    if CACHE_FILE.exists():
        try:
            d = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            age = time.time() - d.get("timestamp", 0)
            if age < CACHE_DURATION:
                return d.get("channels", {}), age
        except Exception:
            pass
    return None, None


def save_cache(chs):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps({"timestamp": time.time(), "channels": chs},
                       ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def fetch_all(force=False, all_sources=None, quiet=False):
    if all_sources is None:
        all_sources = SOURCES

    if not force:
        cached, age = load_cache()
        if cached:
            total = sum(len(v) for v in cached.values())
            if not quiet:
                h = int(age//3600); m = int((age%3600)//60)
                print(f"{C.G}✅ {total} قناة من الكاش ({h}س {m}د){C.END}")
            return cached

    if not quiet:
        print(f"\n{C.CY}⏳ جلب {len(all_sources)} مصدر...{C.END}\n")
    results = {}; done = 0; lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(fetch_one, it): it for it in all_sources.items()}
        for fut in as_completed(futures):
            n, chs = fut.result()
            results[n] = chs
            with lock:
                done += 1
                if not quiet and not ENV["is_pydroid"] and not ENV["is_github"]:
                    if chs and done % 5 == 0:
                        print(f"  [{done:>3}/{len(all_sources)}] {C.G}✓{C.END} {n[:35]:<35} {C.DIM}{len(chs)}{C.END}")

    save_cache(results)
    total = sum(len(v) for v in results.values())
    if not quiet:
        print(f"\n{C.G}✅ اكتمل: {total} قناة{C.END}")
    return results


# ============================================================
# [12] فحص البث
# ============================================================
CHECK_UAS = [
    "Mozilla/5.0 (VLC/3.0.20) LibVLC/3.0.20",
    "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36",
    "TiviMate/4.7.0 (Linux; Android 11)",
    "Kodi/20.0 (Windows NT 10.0)",
]


def _classify(r, chunk):
    status = r.status_code
    ct = r.headers.get("Content-Type", "").lower()
    if status in (451, 403):
        return "geoblock"
    if chunk:
        text = chunk.decode("utf-8", errors="ignore")
        if "SAMPLE-AES" in text or "widevine" in text.lower():
            return "drm"
        if "#EXTM3U" in text or "#EXT-X" in text:
            return "ok"
        if chunk[:2] in (b"\x1f\x8b", b"\x78\x9c"):
            return "ok"
        if chunk[0] == 0x47:
            return "ok"
        if b"ftyp" in chunk[:20]:
            return "ok"
    if "mpegurl" in ct or "hls" in ct:
        return "hls"
    if any(t in ct for t in ["video/", "octet-stream", "mp2t", "mp4"]):
        return "ok"
    return "unknown"


def check_stream(url, timeout=CHECK_TIMEOUT):
    if not url or not url.startswith(("http://", "https://")):
        return url, False, "invalid"
    try:
        r = SESSION.head(url, headers={"User-Agent": CHECK_UAS[0]},
                        timeout=timeout//2, allow_redirects=True, verify=False)
        if r.status_code < 400:
            ct = r.headers.get("Content-Type", "").lower()
            if "mpegurl" in ct or "hls" in ct or "video" in ct:
                return url, True, "head"
    except Exception:
        pass
    for ua in CHECK_UAS:
        try:
            r = SESSION.get(url, headers={"User-Agent": ua}, timeout=timeout,
                           stream=True, allow_redirects=True, verify=False)
            if r.status_code >= 400:
                r.close(); continue
            try:
                chunk = next(r.iter_content(chunk_size=2048, decode_unicode=False), b"")
            except Exception:
                chunk = b""
            r.close()
            if not chunk or len(chunk) < 100:
                continue
            res = _classify(r, chunk)
            if res == "ok":
                return url, True, "ok"
            if res == "drm":
                return url, False, "drm"
            if res == "geoblock":
                return url, False, "geoblock"
        except Exception:
            continue
    return url, False, "dead"


def check_stream_cached(url, timeout=CHECK_TIMEOUT):
    if url in CHECK_CACHE:
        v = CHECK_CACHE[url]
        if isinstance(v, dict) and time.time() - v.get("ts", 0) < CHECK_CACHE_DURATION:
            return url, v.get("ok", False), "cached"
    ok, reason = check_stream(url, timeout)
    CHECK_CACHE[url] = {"ok": ok, "reason": reason, "ts": time.time()}
    return url, ok, reason


def check_many(chs, workers=CHECK_WORKERS):
    total = len(chs)
    if not total:
        return [], 0
    print(f"\n{C.BOLD}{C.CY}🔬 فحص {total} بث...{C.END}\n")
    working = []; failed = 0; drm = 0; geo = 0; done = 0
    lock = threading.Lock(); t0 = time.time()

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {ex.submit(check_stream_cached, ch["url"]): ch for ch in chs}
        for fut in as_completed(futures):
            ch = futures[fut]
            try:
                _, ok, reason = fut.result()
            except Exception:
                ok, reason = False, "err"
            with lock:
                done += 1
                if ok:
                    working.append(ch)
                else:
                    failed += 1
                    if reason == "drm": drm += 1
                    elif reason == "geoblock": geo += 1
                every = 50 if ENV["is_pydroid"] else 5
                if done % every == 0 or done == total:
                    pct = done/total*100
                    print(f"  [{done:>4}/{total}] {pct:5.1f}%  ✅{len(working)}  ❌{failed}  {C.M}🔒{drm}{C.END} {C.Y}🌍{geo}{C.END}")

    save_check_cache()
    el = time.time() - t0
    print(f"\n{C.G}✅ انتهى في {el:.1f}ث{C.END}")
    print(f"   ✅ يشتغل: {C.G}{len(working)}{C.END}")
    print(f"   ❌ معطل: {C.R}{failed}{C.END}")
    if drm:
        print(f"   🔒 DRM: {C.M}{drm}{C.END}")
    if geo:
        print(f"   🌍 محجوب: {C.Y}{geo}{C.END}")
    return working, failed


# ============================================================
# [13] الحفظ
# ============================================================
def safe_name(n):
    s = re.sub(r'[^\w\s\u0600-\u06FF-]', '', n, flags=re.UNICODE)
    return (s.strip().replace(" ", "_")[:50]) or "results"


def save_m3u(channels, filename):
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        p = OUTPUT_DIR / filename
        with open(p, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"#PLAYLIST: {filename}\n")
            f.write(f"#DATE: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            f.write(f"#TOTAL: {len(channels)}\n\n")
            for ch in channels:
                logo = f' tvg-logo="{ch["logo"]}"' if ch.get("logo") else ""
                country = f' tvg-country="{ch.get("country","")}"' if ch.get("country") else ""
                lang = f' tvg-language="{ch.get("language","")}"' if ch.get("language") else ""
                tvg_id = f' tvg-id="{ch.get("tvg_id","")}"' if ch.get("tvg_id") else ""
                grp = f' group-title="{ch.get("group", "غير مصنف")}"'
                name = ch["name"].replace("\n", " ").strip()
                f.write(f"#EXTINF:-1{tvg_id}{logo}{country}{lang}{grp},{name}\n{ch['url']}\n")
        return p
    except Exception as e:
        print(f"{C.R}❌ save_m3u: {e}{C.END}")
        return None


def save_out(results, query):
    if not results:
        return []
    out = []
    base = f"iptv_{safe_name(query)}_{time.strftime('%Y%m%d_%H%M%S')}"

    p = save_m3u(results, f"{base}.m3u")
    if p: out.append(p)

    try:
        p = OUTPUT_DIR / f"{base}.txt"
        with open(p, "w", encoding="utf-8") as f:
            f.write(f"# {query} ({len(results)})\n\n")
            for i, ch in enumerate(results, 1):
                f.write(f"[{i}] {ch['name']}\n")
                if ch.get("_score"):
                    f.write(f"    score: {ch['_score']}\n")
                if ch.get("_source"):
                    f.write(f"    src: {ch['_source']}\n")
                f.write(f"    {ch['url']}\n\n")
        out.append(p)
    except Exception:
        pass

    try:
        p = OUTPUT_DIR / f"{base}.json"
        data = [{k: v for k, v in ch.items() if not k.startswith("_")} for ch in results]
        p.write_text(json.dumps({"query": query, "count": len(results),
                                 "results": data}, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        out.append(p)
    except Exception:
        pass

    return out


# ============================================================
# [14] 🚀 Auto-Update System
# ============================================================
class AutoUpdater:
    """محدّث تلقائي كل 12 ساعة"""
    def __init__(self, interval_hours=12, on_update=None):
        self.interval = interval_hours * 3600
        self.on_update = on_update
        self.last_update = time.time()
        self._stop = threading.Event()
        self._thread = None
        self.next_update = self.last_update + self.interval

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.wait(self.interval):
            try:
                print(f"\n{C.BOLD}{C.CY}🔄 تحديث تلقائي... ({datetime.now().strftime('%H:%M:%S')}){C.END}")
                if self.on_update:
                    self.on_update()
                self.last_update = time.time()
                self.next_update = self.last_update + self.interval
                print(f"{C.G}✅ اكتمل التحديث التلقائي{C.END}")
            except Exception as e:
                print(f"{C.R}❌ خطأ تحديث: {e}{C.END}")

    def time_left(self):
        return max(0, self.next_update - time.time())

    def status_str(self):
        left = self.time_left()
        h = int(left // 3600); m = int((left % 3600) // 60)
        return f"التحديث القادم بعد {h}س {m}د"


def export_all_playlists(engine):
    """تصدير كل القوائم لـ GitHub"""
    print(f"\n{C.BOLD}{C.CY}📦 تصدير القوائم الكاملة...{C.END}\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) كل القنوات
    all_ch = engine.all()
    p = save_m3u(all_ch, "all.m3u8")
    if p:
        print(f"{C.G}✓{C.END} all.m3u8 ({len(all_ch)})")

    # 2) حسب الفئة
    cats_folder = OUTPUT_DIR / "categories"
    cats_folder.mkdir(exist_ok=True)

    by_group = defaultdict(list)
    for ch in all_ch:
        g = ch.get("group", "غير مصنف")
        by_group[g].append(ch)

    # اسم فئة لاتيني
    for grp, chs in by_group.items():
        fname = re.sub(r'[^\w\-]', '_', grp)[:40] or "other"
        p = cats_folder / f"{fname}.m3u8"
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f"#GROUP: {grp}\n")
                f.write(f"#TOTAL: {len(chs)}\n\n")
                for ch in chs:
                    f.write(f"#EXTINF:-1,{ch['name']}\n{ch['url']}\n")
        except Exception:
            pass

    print(f"{C.G}✓{C.END} categories/ ({len(by_group)} فئة)")

    # 3) حسب الدولة
    countries_folder = OUTPUT_DIR / "countries"
    countries_folder.mkdir(exist_ok=True)

    by_country = defaultdict(list)
    for ch in all_ch:
        cc = (ch.get("country") or "").upper()
        if cc:
            by_country[cc].append(ch)

    for cc, chs in by_country.items():
        p = countries_folder / f"{cc}.m3u8"
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f"#COUNTRY: {cc}\n")
                f.write(f"#TOTAL: {len(chs)}\n\n")
                for ch in chs:
                    f.write(f"#EXTINF:-1,{ch['name']}\n{ch['url']}\n")
        except Exception:
            pass

    print(f"{C.G}✓{C.END} countries/ ({len(by_country)} دولة)")

    # 4) حسب اللغة
    langs_folder = OUTPUT_DIR / "languages"
    langs_folder.mkdir(exist_ok=True)

    by_lang = defaultdict(list)
    for ch in all_ch:
        lg = (ch.get("language") or "").lower()
        if lg:
            by_lang[lg].append(ch)

    for lg, chs in by_lang.items():
        p = langs_folder / f"{lg}.m3u8"
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write("#EXTM3U\n")
                f.write(f"#LANGUAGE: {lg}\n")
                f.write(f"#TOTAL: {len(chs)}\n\n")
                for ch in chs:
                    f.write(f"#EXTINF:-1,{ch['name']}\n{ch['url']}\n")
        except Exception:
            pass

    print(f"{C.G}✓{C.END} languages/ ({len(by_lang)} لغة)")

    # 5) القنوات الكبرى: كل علامة في ملف مستقل + قائمة موحدة
    featured_folder = OUTPUT_DIR / "featured"
    featured_folder.mkdir(exist_ok=True)
    featured_all = []
    featured_seen = set()
    featured_counts = {}
    for slug, query in FEATURED_QUERIES.items():
        matches = engine.search(query, min_score=0.16, limit=500, use_ml=False)
        unique = []
        unique_urls = set()
        for ch in matches:
            if ch["url"] not in unique_urls:
                unique_urls.add(ch["url"])
                unique.append(ch)
            if ch["url"] not in featured_seen:
                featured_seen.add(ch["url"])
                featured_all.append(ch)
        if unique:
            save_m3u(unique, f"featured/{slug}.m3u8")
        featured_counts[slug] = len(unique)

    if featured_all:
        save_m3u(featured_all, "featured.m3u8")
    print(f"{C.G}✓{C.END} featured/ ({sum(1 for n in featured_counts.values() if n)}/{len(FEATURED_QUERIES)} علامات، {len(featured_all)} قناة فريدة)")

    # 6) قوائم مشهورة
    popular = {
        "arabic.m3u8": ["ara", "arabic", "عربي"],
        "sports.m3u8": ["sport", "رياضة", "sports"],
        "news.m3u8": ["news", "أخبار", "اخبار"],
        "kids.m3u8": ["kids", "children", "أطفال", "اطفال"],
        "movies.m3u8": ["movie", "cinema", "أفلام", "افلام"],
        "music.m3u8": ["music", "موسيقى"],
    }

    for fname, keywords in popular.items():
        matched = []
        seen = set()
        for ch in all_ch:
            text = f"{ch['name']} {ch.get('group','')}".lower()
            for kw in keywords:
                if kw in text and ch["url"] not in seen:
                    seen.add(ch["url"])
                    matched.append(ch)
                    break
        if matched:
            save_m3u(matched, fname)
            print(f"{C.G}✓{C.END} {fname} ({len(matched)})")

    # 7) README مع الإحصاءات
    stats_file = OUTPUT_DIR / "STATS.md"
    try:
        with open(stats_file, "w", encoding="utf-8") as f:
            f.write(f"# 📊 إحصائيات IPTV Mega\n\n")
            f.write(f"**آخر تحديث:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n")
            f.write(f"| القياس | القيمة |\n|---|---|\n")
            f.write(f"| إجمالي القنوات | {len(all_ch):,} |\n")
            f.write(f"| عدد الفئات | {len(by_group)} |\n")
            f.write(f"| عدد الدول | {len(by_country)} |\n")
            f.write(f"| عدد اللغات | {len(by_lang)} |\n")
            f.write(f"| عدد المصادر | {len(SOURCES)} |\n")
            f.write(f"| القنوات الكبرى المكتشفة | {len(featured_all)} |\n")
            f.write("\n## القنوات الكبرى\n\n")
            for slug, count in featured_counts.items():
                if count:
                    f.write(f"- `{slug}`: {count}\n")
        print(f"{C.G}✓{C.END} STATS.md")
    except Exception:
        pass

    print(f"\n{C.G}✅ تم تصدير كل القوائم إلى: {OUTPUT_DIR}{C.END}")
    return OUTPUT_DIR


# ============================================================
# [15] سيرفر
# ============================================================
def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2); s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]; s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def free_port(start=8888):
    for p in range(start, start + 30):
        try:
            t = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            t.bind(("0.0.0.0", p)); t.close(); return p
        except OSError:
            continue
    return None


def serve(file_path):
    if not file_path or not file_path.exists():
        print(f"{C.R}❌ الملف غير موجود.{C.END}"); return
    port = free_port(8888)
    if not port:
        print(f"{C.R}❌ لا منفذ حر.{C.END}"); return
    directory = str(file_path.parent); filename = file_path.name

    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=directory, **k)
        def log_message(self, *a): pass

    try:
        httpd = socketserver.TCPServer(("0.0.0.0", port), H)
    except Exception as e:
        print(f"{C.R}❌ {e}{C.END}"); return

    url = f"http://{get_ip()}:{port}/{filename}"
    print(f"\n{C.G}{'═'*70}{C.END}")
    print(f"{C.BOLD}{C.G}🌐 السيرفر يعمل!{C.END}")
    print(f"{C.G}{'═'*70}{C.END}\n")
    print(f"   📡 {C.Y}{C.BOLD}{url}{C.END}\n")
    if HAS_QR:
        try:
            qr = qrcode.QRCode(border=1)
            qr.add_data(url); qr.make(fit=True)
            qr.print_ascii(invert=True)
        except Exception: pass
    print(f"\n   {C.DIM}Ctrl+C للإيقاف{C.END}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{C.Y}⏹️  توقف.{C.END}")
    finally:
        httpd.shutdown(); httpd.server_close()


# ============================================================
# [16] العرض
# ============================================================
def show(results, query, limit=None):
    if not results:
        print(f"{C.R}❌ لا نتائج.{C.END}"); return
    print(f"\n{C.G}{'═'*70}{C.END}")
    print(f"{C.BOLD}{C.G}✅ {len(results)} قناة لـ '{query}'{C.END}")
    print(f"{C.G}{'═'*70}{C.END}\n")
    to_show = results if limit is None else results[:limit]
    for i, ch in enumerate(to_show, 1):
        premium = f" {C.M}💰{C.END}" if is_premium_channel(ch["name"]) else ""
        ctry = f" {C.CY}[{ch.get('country','')}]{C.END}" if ch.get("country") else ""
        score = f" {C.G}[{ch.get('_score', 0)}]{C.END}" if ch.get("_score") else ""
        src = f" {C.M}← {ch.get('_source','?')}{C.END}" if ch.get("_source") else ""
        print(f"{C.Y}[{i:>4}]{C.END} {C.BOLD}{ch['name']}{C.END}{score}{premium}{ctry}{src}")
        print(f"       {C.B}{ch['url']}{C.END}\n")


def help_():
    print(f"""
{C.BOLD}{C.CY}الأوامر:{C.END}

  {C.BOLD}{C.M}🔍 البحث:{C.END}
  {C.Y}كلمة{C.END}                   بحث ML + فحص + حفظ
  {C.Y}fast كلمة{C.END}              بدون فحص
  {C.Y}mega كلمة{C.END}              عرض الكل
  {C.Y}classic كلمة{C.END}           بحث تقليدي

  {C.BOLD}{C.M}🤖 التعلم:{C.END}
  {C.Y}choose N{C.END} / {C.Y}reject N{C.END}
  {C.Y}model{C.END} / {C.Y}resetmodel{C.END}

  {C.BOLD}{C.M}🔄 التحديث:{C.END}
  {C.Y}update{C.END}                 تحديث الآن
  {C.Y}export{C.END}                 تصدير كل القوائم
  {C.Y}nextup{C.END}                 وقت التحديث القادم

  {C.BOLD}{C.M}🔗 السيرفر:{C.END}
  {C.Y}merge{C.END} / {C.Y}serve{C.END} / {C.Y}one{C.END}

  {C.BOLD}{C.M}⚙️ أخرى:{C.END}
  {C.Y}sources{C.END} / {C.Y}stats{C.END} / {C.Y}open{C.END}
  {C.Y}clearcache{C.END} / {C.Y}quit{C.END}

{C.BOLD}{C.Y}📊 المصادر:{C.END} {len(SOURCES)}
{C.BOLD}{C.Y}📂 الحفظ:{C.END} {OUTPUT_DIR}
{C.BOLD}{C.Y}🧠 النموذج:{C.END} {MODEL.samples} مثال
""")


# ============================================================
# [17] GitHub Mode
# ============================================================
def github_update_mode():
    """وضع GitHub Actions: جلب + تصدير + إنهاء"""
    print(f"{C.CY}🚀 GitHub Actions Mode{C.END}")
    print(f"📅 {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n")

    # force refresh (بدون كاش) مع المصادر التي وضعها المستخدم في sources.txt
    all_src = dict(SOURCES)
    file_sources = load_file_sources()
    if file_sources:
        print(f"💎 {len(file_sources)} مصدر مخصص من sources.txt")
        all_src.update(file_sources)
    data = fetch_all(force=True, all_sources=all_src, quiet=True)
    total = sum(len(v) for v in data.values())
    print(f"✅ {total} قناة من {len(data)} مصدر")

    eng = MaxEngine(data)
    export_all_playlists(eng)

    print(f"\n{C.G}✅ اكتمل التحديث التلقائي{C.END}")


# ============================================================
# [18] البرنامج الرئيسي
# ============================================================
def main():
    global CHECK_WORKERS, CHECK_TIMEOUT

    # --- CLI ---
    parser = argparse.ArgumentParser(description="IPTV Mega")
    parser.add_argument("--update", action="store_true",
                        help="وضع GitHub Actions: تحديث + خروج")
    parser.add_argument("--export", action="store_true",
                        help="تصدير كل القوائم وخروج")
    parser.add_argument("--no-autoupdate", action="store_true",
                        help="تعطيل التحديث التلقائي")
    args = parser.parse_args()

    # --- GitHub Mode ---
    if args.update:
        github_update_mode()
        return

    # --- Header ---
    print(f"{C.BOLD}{C.M}")
    print("═" * 70)
    print("     🎬  IPTV Mega v16 - Auto-Update  🎬")
    print(f"     {len(SOURCES)} مصدر · ML Engine · تحديث كل 12 ساعة")
    print("═" * 70)
    print(f"{C.END}")
    print(f"{C.CY}🖥️  {C.Y}{ENV['os'].upper()}{C.END}")
    print(f"{C.CY}📂 {C.Y}{OUTPUT_DIR}{C.END}")
    print(f"{C.CY}🧠 النموذج: {C.Y}{MODEL.samples} مثال{C.END}\n")

    load_check_cache()

    # --- المصادر المخصصة ---
    custom = load_file_sources()
    if CUSTOM_FILE.exists():
        try:
            custom.update(json.loads(CUSTOM_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass

    all_src = dict(SOURCES)
    if custom:
        print(f"{C.G}💎 {len(custom)} مصدر مخصص{C.END}")
        all_src.update(custom)

    # --- جلب البيانات ---
    data = fetch_all(all_sources=all_src)

    eng = MaxEngine(data)
    print(f"{C.G}✅ جاهز! ({eng.total()} قناة){C.END}")

    # --- تصدير تلقائي إذا كان export ---
    if args.export:
        export_all_playlists(eng)
        return

    # --- Auto-Updater ---
    auto_updater = None
    if not args.no_autoupdate:
        def on_auto_update():
            nonlocal data, eng
            print(f"{C.CY}⏳ إعادة جلب المصادر...{C.END}")
            data = fetch_all(force=True, all_sources=all_src)
            eng = MaxEngine(data)
            export_all_playlists(eng)

        auto_updater = AutoUpdater(interval_hours=12, on_update=on_auto_update)
        auto_updater.start()
        print(f"{C.G}🔄 التحديث التلقائي مُفعّل: كل 12 ساعة{C.END}")
        print(f"{C.DIM}   {auto_updater.status_str()}{C.END}")

    print(f"\n{C.DIM}💡 جرّب: bein, cartoon, mbc, spacetoon{C.END}")
    print(f"{C.DIM}💡 علّم النموذج: choose N / reject N{C.END}")

    last_merged = None
    last_results = []

    # --- Loop ---
    while True:
        try:
            cmd = input(f"\n{C.BOLD}{C.CY}➤ {C.END}").strip()
        except (KeyboardInterrupt, EOFError):
            if auto_updater:
                auto_updater.stop()
            MODEL.save(MODEL_FILE)
            print(f"\n{C.M}👋 وداعًا{C.END}")
            break

        if not cmd:
            continue
        low = cmd.lower()

        # ============ خروج ============
        if low in ("quit", "exit", "q"):
            if auto_updater:
                auto_updater.stop()
            MODEL.save(MODEL_FILE)
            print(f"{C.M}👋 وداعًا{C.END}")
            break

        # ============ مساعدة ============
        if low == "help":
            help_(); continue

        if low == "sources":
            print(f"\n{C.CY}📚 المصادر ({len(data)}):{C.END}\n")
            for i, (n, chs) in enumerate(data.items(), 1):
                if chs:
                    print(f"  {C.Y}{i:>3}.{C.END} {n[:38]:<38} {C.DIM}{len(chs)}{C.END}")
            continue

        if low == "stats":
            print(f"\n📊 إحصائيات:")
            print(f"  • النظام: {ENV['os']}")
            print(f"  • المجلد: {OUTPUT_DIR}")
            print(f"  • المصادر: {len(data)} ({len(custom)} مخصص)")
            print(f"  • القنوات: {eng.total()}")
            print(f"  • أمثلة تدريب: {MODEL.samples}")
            print(f"  • كاش فحص: {len(CHECK_CACHE)}")
            if auto_updater:
                print(f"  • {auto_updater.status_str()}")
            continue

        if low == "nextup":
            if auto_updater:
                print(f"🔄 {auto_updater.status_str()}")
            else:
                print(f"{C.Y}التحديث التلقائي معطّل{C.END}")
            continue

        if low == "update":
            print(f"{C.CY}🔄 تحديث الآن...{C.END}")
            data = fetch_all(force=True, all_sources=all_src)
            eng = MaxEngine(data)
            print(f"{C.G}✅ {eng.total()} قناة{C.END}")
            continue

        if low == "export":
            export_all_playlists(eng)
            continue

        if low == "model":
            print(f"\n{C.BOLD}🧠 أوزان النموذج ({MODEL.samples} مثال):{C.END}\n")
            print(f"  {'bias':<25} {MODEL.bias:+.4f}")
            for f in FEATURES:
                w = MODEL.weights[f]
                color = C.G if w > 0 else C.R
                print(f"  {f:<25} {color}{w:+.4f}{C.END}")
            continue

        if low == "resetmodel":
            MODEL = MLModel()
            MODEL.save(MODEL_FILE)
            print(f"{C.G}✅ أُعيدت الأوزان{C.END}")
            continue

        if low == "clearcache":
            CHECK_CACHE.clear()
            if CHECK_CACHE_FILE.exists():
                CHECK_CACHE_FILE.unlink()
            print(f"{C.G}✅ مُسح الكاش{C.END}")
            continue

        if low == "open":
            try:
                if ENV["os"] == "windows":
                    os.startfile(str(OUTPUT_DIR))
                elif ENV["os"] == "macos":
                    import subprocess; subprocess.Popen(["open", str(OUTPUT_DIR)])
                elif ENV["is_android"]:
                    print(f"📂 {OUTPUT_DIR}")
                else:
                    import subprocess; subprocess.Popen(["xdg-open", str(OUTPUT_DIR)])
            except Exception:
                print(f"📂 {OUTPUT_DIR}")
            continue

        # ============ choose / reject ============
        if low.startswith("choose"):
            if not last_results:
                print(f"{C.R}⚠️  لا نتائج سابقة{C.END}"); continue
            try:
                parts = cmd.split()
                n = int(parts[1]) - 1 if len(parts) > 1 else 0
                if 0 <= n < len(last_results):
                    chosen = last_results[n]
                    rejected = [r for i, r in enumerate(last_results) if i != n]
                    eng.learn(chosen, rejected)
                    print(f"{C.G}🎓 تعلم: '{chosen['name']}' جيدة{C.END}")
                    print(f"{C.DIM}   النموذج: {MODEL.samples} مثال{C.END}")
                else:
                    print(f"{C.R}⚠️  رقم غير صالح{C.END}")
            except Exception:
                print(f"{C.R}⚠️  choose N{C.END}")
            continue

        if low.startswith("reject "):
            try:
                n = int(cmd.split()[1]) - 1
                if 0 <= n < len(last_results):
                    rejected = last_results[n]
                    MODEL.update(rejected["_features"], 0)
                    MODEL.save(MODEL_FILE)
                    print(f"{C.G}❌ تعلم: '{rejected['name']}' سيئة{C.END}")
                else:
                    print(f"{C.R}⚠️  رقم غير صالح{C.END}")
            except Exception:
                print(f"{C.R}⚠️  reject N{C.END}")
            continue

        # ============ merge / serve ============
        if low == "merge":
            all_ch = eng.all()
            p = save_m3u(all_ch, "ALL_CHANNELS.m3u8")
            if p:
                last_merged = p
            continue

        if low == "serve":
            if last_merged is None:
                c = sorted(OUTPUT_DIR.glob("ALL_CHANNELS*.m3u8"),
                          key=lambda x: x.stat().st_mtime, reverse=True)
                if c:
                    last_merged = c[0]
                else:
                    print(f"{C.Y}⚠️  نفّذ merge أولاً{C.END}")
                    continue
            serve(last_merged)
            continue

        if low == "one":
            all_ch = eng.all()
            p = save_m3u(all_ch, "ALL_CHANNELS.m3u8")
            if p:
                last_merged = p
                time.sleep(1)
                serve(p)
            continue

        if low == "all":
            all_ch = eng.all()
            save_out(all_ch, "all_channels")
            print(f"{C.G}✅ {len(all_ch)} قناة{C.END}")
            continue

        # ============ البحث ============
        skip = False; mega = False; classic = False; q = cmd
        if low.startswith("fast "):
            skip = True; q = cmd[5:].strip()
        elif low.startswith("mega "):
            mega = True; q = cmd[5:].strip()
        elif low.startswith("classic "):
            classic = True; q = cmd[8:].strip()

        print(f"\n{C.CY}🔍 بحث عن '{q}'...{C.END}")
        t0 = time.time()
        found = eng.search(q, min_score=0.1 if mega else 0.2,
                          use_ml=not classic)
        st = time.time() - t0

        if not found:
            print(f"{C.R}❌ لا نتائج{C.END}")
            continue

        print(f"{C.G}✅ {len(found)} نتيجة ({st:.2f}ث){C.END}")

        if skip or mega:
            working = found
        else:
            working, _ = check_many(found)

        if not working:
            print(f"{C.R}⚠️  لا قنوات تبث{C.END}")
            continue

        last_results = working
        show(working, q)

        saved = save_out(working, q)
        if saved:
            print(f"\n{C.G}💾 حُفظت في {len(saved)} ملفات{C.END}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        MODEL.save(MODEL_FILE)
        print(f"\n{C.M}👋 توقف.{C.END}")
        sys.exit(0)
