import os, json, requests, anthropic
from xml.etree import ElementTree as ET
from datetime import datetime

STOCKS = [
    {"ticker": "TSLA",   "name": "Tesla"},
    {"ticker": "HIMS",   "name": "Hims & Hers"},
    {"ticker": "DUOL",   "name": "Duolingo"},
    {"ticker": "BMNR",   "name": "Bitmine Immersion Technologies"},
    {"ticker": "LODE",   "name": "Comstock Inc"},
    {"ticker": "HGRAF",  "name": "HydroGraph Clean Power"},
    {"ticker": "HBFG",   "name": "Happy Belly Food Group"},
    {"ticker": "ABX",    "name": "Abacus Global Management", "query": "ABX Abacus Global Management"},
    {"ticker": "3350.T", "name": "Metaplanet",               "query": "Metaplanet Bitcoin treasury"},
    {"ticker": "BILD",   "name": "BuildDirect Technologies", "query": "BuildDirect Technologies BILD"},
    {"ticker": "LIB",    "name": "LibertyStream Infrastructure", "query": "LibertyStream Infrastructure LIB"},
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CarteraBot/1.0)"}

def fetch_yahoo(ticker):
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    try:
        r = requests.get(url, timeout=10, headers=HEADERS)
        root = ET.fromstring(r.content)
        items = []
        for item in root.findall(".//item")[:4]:
            items.append({
                "title":   item.findtext("title", ""),
                "link":    item.findtext("link", ""),
                "date":    item.findtext("pubDate", ""),
                "summary": (item.findtext("description") or "")[:300],
            })
        return items
    except Exception as e:
        print(f"  Yahoo RSS error for {ticker}: {e}")
        return []

def fetch_google(query):
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}+stock&hl=en-US&gl=US&ceid=US:en"
    try:
        r = requests.get(url, timeout=10, headers=HEADERS)
        root = ET.fromstring(r.content)
        items = []
        for item in root.findall(".//item")[:4]:
            items.append({
                "title":   item.findtext("title", ""),
                "link":    item.findtext("link", ""),
                "date":    item.findtext("pubDate", ""),
                "summary": "",
            })
        return items
    except Exception as e:
        print(f"  Google RSS error for {query}: {e}")
        return []

print("Fetching news...")
all_news = {}
for s in STOCKS:
    ticker = s["ticker"]
    query  = s.get("query", f"{s['name']} {ticker}")
    news   = fetch_yahoo(ticker) or fetch_google(query)
    if len(news) < 2:
        news += fetch_google(query)
    all_news[ticker] = {"name": s["name"], "news": news[:3]}
    print(f"  {ticker}: {len(all_news[ticker]['news'])} items")

now = datetime.utcnow()

print("Calling Claude API...")
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

prompt = f"""Eres un generador de reportes financieros profesionales en español.

FECHA: {now.strftime("%A %d de %B de %Y")} UTC (traduce día y mes al español)

NOTICIAS:
{json.dumps(all_news, indent=2, ensure_ascii=False)}

Genera un archivo HTML COMPLETO y autocontenido con las siguientes características:

1. Todo el texto en ESPAÑOL
2. Título: "📊 Reporte de Cartera"
3. Fecha en español en la cabecera
4. Tema oscuro con estas variables CSS:
   --bg:#0d1117; --surface:#161b22; --surface2:#21262d; --border:#30363d;
   --text:#e6edf3; --muted:#8b949e; --green:#3fb950; --red:#f85149;
   --yellow:#d29922; --blue:#58a6ff; --purple:#bc8cff; --orange:#ffa657;
5. Barra de resumen arriba con conteo de COMPRAR / MANTENER / VENDER / ESPECULATIVO
6. Grid de tarjetas, una por acción, con borde izquierdo de color:
   - Verde = COMPRAR
   - Amarillo = MANTENER
   - Rojo = VENDER
   - Morado = ESPECULATIVO
7. Cada tarjeta tiene 3 columnas:
   IZQUIERDA — Noticias: las noticias del JSON con enlaces clicables, fuente, fecha y una frase de descripción en español. Fuentes oficiales (GlobeNewswire, PR Newswire, IR pages) marcadas con "📋 [OFICIAL]"
   CENTRO — Análisis técnico: precio estimado actual, MA50, MA200, barra visual RSI con colores (rojo si <30, verde si 30-70, naranja si >70), comparación de volumen
   DERECHA — Recomendación: badge con color, 2-3 frases de razonamiento en español basadas en las noticias y el análisis
8. Pie de página: "Este reporte es solo informativo y no constituye asesoramiento financiero."

IMPORTANTE: Responde ÚNICAMENTE con el código HTML. Sin explicaciones, sin markdown, sin bloques de código. Empieza directamente con <!DOCTYPE html>"""

msg = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=8192,
    messages=[{"role": "user", "content": prompt}],
)

html = msg.content[0].text.strip()
if not html.startswith("<!"):
    idx = html.find("<!DOCTYPE")
    if idx == -1:
        idx = html.find("<html")
    if idx >= 0:
        html = html[idx:]

with open("reporte_cartera.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Report written ({len(html):,} chars)")
