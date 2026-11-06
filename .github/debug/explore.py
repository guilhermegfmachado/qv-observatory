"""Temporary: which RSS feeds answer from CI, how many items, how far back."""
import re, urllib.request, urllib.error
from email.utils import parsedate_to_datetime

UA = {"User-Agent": "qv-observatory/0.3 (research; github.com/guilhermegfmachado/qv-observatory)"}
FEEDS = {
 "news/en bbc-europe": "https://feeds.bbci.co.uk/news/world/europe/rss.xml",
 "news/en guardian-europe": "https://www.theguardian.com/world/europe-news/rss",
 "news/en euronews": "https://www.euronews.com/rss?level=theme&name=news",
 "news/fr france24-europe": "https://www.france24.com/fr/europe/rss",
 "news/fr lemonde-europe": "https://www.lemonde.fr/europe/rss_full.xml",
 "news/fr rfi-europe": "https://www.rfi.fr/fr/europe/rss",
 "news/nl nos": "https://feeds.nos.nl/nosnieuwsalgemeen",
 "news/nl nos-buitenland": "https://feeds.nos.nl/nosnieuwsbuitenland",
 "news/nl vrt": "https://www.vrt.be/vrtnws/nl.rss.articles.xml",
 "news/pt rtp-mundo": "https://www.rtp.pt/noticias/rss/mundo",
 "news/pt publico": "https://feeds.feedburner.com/PublicoRSS",
 "news/pt observador": "https://observador.pt/feed/",
 "news/de tagesschau": "https://www.tagesschau.de/xml/rss2/",
 "news/es elpais-int": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada",
 "news/it ansa-mondo": "https://www.ansa.it/sito/notizie/mondo/mondo_rss.xml",
 "art/en eflux-ann-1": "https://www.e-flux.com/rss/announcements/",
 "art/en eflux-ann-2": "https://www.e-flux.com/announcements/rss/",
 "art/en eflux-journal": "https://www.e-flux.com/journal/rss/",
 "art/en frieze": "https://www.frieze.com/rss.xml",
 "art/en artforum": "https://www.artforum.com/feed/",
 "art/en artnews": "https://www.artnews.com/feed/",
 "art/en hyperallergic": "https://hyperallergic.com/feed/",
 "art/en artnewspaper": "https://www.theartnewspaper.com/rss.xml",
 "art/en artreview": "https://artreview.com/feed/",
 "art/en mousse": "https://www.moussemagazine.it/feed/",
 "art/en contemporaryand": "https://contemporaryand.com/feed/",
 "art/fr quotidiendelart": "https://www.lequotidiendelart.com/rss",
 "art/fr connaissancedesarts": "https://www.connaissancedesarts.com/feed/",
 "art/nl metropolism": "https://www.metropolism.com/feed/",
 "art/nl hart": "https://www.hartmagazine.be/feed/",
 "art/pt artecapital": "https://www.artecapital.net/rss.php",
 "art/pt contemporanea": "https://contemporanea.pt/feed",
 "art/de monopol": "https://www.monopol-magazin.de/rss.xml",
 "art/es elcultural-arte": "https://elcultural.com/rss/arte",
}
for name, url in FEEDS.items():
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace"); st = r.status
    except urllib.error.HTTPError as e:
        print(f"{name:28} HTTP {e.code}"); continue
    except Exception as e:
        print(f"{name:28} ERR {str(e)[:60]}"); continue
    items = re.findall(r"<(item|entry)\b.*?</\1>", body, re.S)
    dates = []
    for d in re.findall(r"<(?:pubDate|published|updated|dc:date)>([^<]+)<", body):
        try: dates.append(parsedate_to_datetime(d.strip()).date().isoformat())
        except Exception:
            m = re.match(r"\d{4}-\d{2}-\d{2}", d.strip()); m and dates.append(m[0])
    desc = re.findall(r"<(?:description|summary|content:encoded|content)\b[^>]*>(.*?)</", body, re.S)
    avg = sum(len(re.sub(r"<[^>]+>|<!\[CDATA\[|\]\]>", "", x)) for x in desc) // max(1, len(desc))
    print(f"{name:28} {st} items={len(items):3} dates={min(dates) if dates else '-'}..{max(dates) if dates else '-'} avgdesc={avg}")
