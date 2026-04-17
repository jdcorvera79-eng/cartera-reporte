  import os, json, requests, anthropic, traceback, sys
from xml.etree import ElementTree as ET
from datetime import datetime
from urllib.parse import quote

STOCKS = [
    {"ticker": "TSLA",   "name": "Tesla"},
    {"ticker": "HIMS",   "name": "Hims & Hers"},
    {"ticker": "DUOL",   "name": "Duolingo"},
    {"ticker": "BMNR",   "name": "Bitmine Immersion Technologies"},
    {"ticker": "LODE",   "name": "Comstock Inc"},
    {"ticker": "HGRAF",  "name": "HydroGraph Clean Power"},
    {"ticker": "HBFG",   "name": "Happy Belly Food Group"},
    {"ticker": "ABX",    "name": "Abacus Global Management", "query": "ABX Abacus Global Management"},
    {"ticker": "3350", "name": "Metaplanet",               "query": "Metaplanet Bitcoin treasury"},
    {"ticker": "BILD",   "name": "BuildDirect Technologies", "query": "BuildDirect Technologies BILD"},
    {"ticker": "LIB",    "name": "LibertyStream Infrastructure", "query": "LibertyStream Infrastructure LIB"},
    {"ticker": "TTT",    "name": "Titonic",                      "query": "Titonic TTT stock"},
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
                "summary": (item.findtext("description") or "")[:200],
            })
        return items
    except Exception as e:
        print(f"  Yahoo RSS error for {ticker}: {e}")
        return []

def fetch_google(query):
    url = f"https://news.google.com/rss/search?q={quote(query)}+stock&hl=en-US&gl=US&ceid=US:en"
    try:
        r = requests.get(url, timeout=10, headers=HEADERS)
        root = ET.fromstring(r.content)
        items = []
        for item in root.findall(".//item")[:4]:
            items.append({
                "title": item.findtext("title", ""),
                "link":  item.findtext("link", ""),
                "date":  item.findtext("pubDate", ""),
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
    news   = fetch_yahoo(ticker) or []
    if len(news) < 2:
        news += fetch_google(query)
    all_news[ticker] = {"name": s["name"], "news": news[:3]}
    print(f"  {ticker}: {len(all_news[ticker]['news'])} items")

now = datetime.utcnow()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

BATCH_PROMPT = """Analiza estas acciones y responde ÚNICAMENTE con un array JSON válido (sin explicaciones, sin markdown).

FECHA: {fecha}
NOTICIAS: {noticias}

Devuelve un array JSON con esta estructura por acción:
[
  {{
    "ticker": "TSLA",
    "nombre": "Tesla",
    "precio": "$245.50",
    "cambio": "+2.3%",
    "ma50": "$230",
    "ma200": "$265",
    "rsi": 55,
    "volumen": "Normal",
    "recomendacion": "MANTENER",
    "razonamiento": "2 frases en español justificando la recomendación.",
    "noticias": [
      {{
        "titulo": "Título en español",
        "fuente": "Yahoo Finance",
        "fecha": "17 abr 2026",
        "url": "https://...",
        "descripcion": "Una frase en español.",
        "oficial": false
      }}
    ]
  }}
]

Reglas:
- recomendacion: COMPRAR, MANTENER, VENDER o ESPECULATIVO
- oficial=true si fuente es GlobeNewswire, PR Newswire, BusinessWire o IR empresa
- rsi es entero 0-100, todo el texto en español
- Empieza directamente con ["""

def analyze_batch(batch_news, fecha):
    prompt = BATCH_PROMPT.format(
        fecha=fecha,
        noticias=json.dumps(batch_news, ensure_ascii=False)
    )
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    print(f"  Batch stop_reason: {msg.stop_reason}, length: {len(raw)}")
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    if not raw.startswith("["):
        raw = raw[raw.find("["):]
    return json.loads(raw)

tickers = list(all_news.keys())
batches = [tickers[i:i+4] for i in range(0, len(tickers), 4)]
fecha_str = now.strftime("%A %d de %B de %Y")

print("Calling Claude API in batches...")
all_acciones = []
for i, batch in enumerate(batches):
    print(f"  Batch {i+1}/{len(batches)}: {batch}")
    batch_news = {t: all_news[t] for t in batch}
    acciones = analyze_batch(batch_news, fecha_str)
    all_acciones.extend(acciones)
    print(f"  Got {len(acciones)} stocks")

data = {"fecha": fecha_str, "acciones": all_acciones}
print(f"Total stocks: {len(all_acciones)}")

# ── Build HTML from template ──────────────────────────────────────────────────

REC_COLOR = {
    "COMPRAR":     "#3fb950",
    "MANTENER":    "#d29922",
    "VENDER":      "#f85149",
    "ESPECULATIVO":"#bc8cff",
}

def rsi_bar(rsi):
    if rsi < 30:
        color = "#f85149"
        label = f"Sobrevendido ({rsi})"
    elif rsi > 70:
        color = "#ffa657"
        label = f"Sobrecomprado ({rsi})"
    else:
        color = "#3fb950"
        label = f"Neutral ({rsi})"
    pct = int(rsi)
    return f"""<div style="margin-top:6px">
      <div style="font-size:11px;color:var(--muted);margin-bottom:3px">RSI: {label}</div>
      <div style="background:var(--surface2);border-radius:4px;height:8px;overflow:hidden">
        <div style="width:{pct}%;height:100%;background:{color};border-radius:4px"></div>
      </div>
    </div>"""

def stock_card(a):
    color = REC_COLOR.get(a["recomendacion"], "#58a6ff")
    news_html = ""
    for n in a.get("noticias", []):
        badge = '<span style="color:#58a6ff;font-size:10px;font-weight:600">📋 [OFICIAL]</span> ' if n.get("oficial") else ""
        news_html += f"""<div style="margin-bottom:12px;padding-bottom:12px;border-bottom:1px solid var(--border)">
          {badge}<a href="{n['url']}" target="_blank" style="color:var(--text);font-weight:600;font-size:13px;text-decoration:none;line-height:1.4">{n['titulo']}</a>
          <div style="color:var(--muted);font-size:11px;margin-top:3px">{n['fuente']} · {n['fecha']}</div>
          <div style="color:var(--muted);font-size:12px;margin-top:4px">{n['descripcion']}</div>
        </div>"""

    cambio_color = "#3fb950" if "+" in a.get("cambio","") else "#f85149"

    return f"""<div class="stock-card" style="border-left:4px solid {color}">
  <div class="stock-header">
    <div>
      <span class="stock-name">{a['nombre']}</span>
      <span class="stock-ticker">{a['ticker']}</span>
    </div>
    <div style="text-align:right">
      <div style="font-size:18px;font-weight:700;color:var(--text)">{a['precio']}</div>
      <div style="font-size:13px;color:{cambio_color}">{a['cambio']}</div>
    </div>
  </div>
  <div class="stock-body">
    <div class="stock-section">
      <div class="section-title">📰 Noticias</div>
      {news_html or '<div style="color:var(--muted);font-size:13px">Sin noticias recientes</div>'}
    </div>
    <div class="stock-section">
      <div class="section-title">📈 Análisis técnico</div>
      <table style="width:100%;font-size:13px;border-collapse:collapse">
        <tr><td style="color:var(--muted);padding:3px 0">MA50</td><td style="color:var(--text);text-align:right">{a['ma50']}</td></tr>
        <tr><td style="color:var(--muted);padding:3px 0">MA200</td><td style="color:var(--text);text-align:right">{a['ma200']}</td></tr>
        <tr><td style="color:var(--muted);padding:3px 0">Volumen</td><td style="color:var(--text);text-align:right">{a['volumen']}</td></tr>
      </table>
      {rsi_bar(a.get('rsi', 50))}
    </div>
    <div class="stock-section">
      <div class="section-title">🎯 Recomendación</div>
      <div style="margin-bottom:10px">
        <span style="background:{color};color:#000;padding:4px 12px;border-radius:20px;font-weight:700;font-size:13px">{a['recomendacion']}</span>
      </div>
      <div style="color:var(--muted);font-size:13px;line-height:1.6">{a['razonamiento']}</div>
    </div>
  </div>
</div>"""

counts = {k: 0 for k in REC_COLOR}
for a in data["acciones"]:
    r = a.get("recomendacion","MANTENER")
    if r in counts:
        counts[r] += 1

cards_html = "\n".join(stock_card(a) for a in data["acciones"])
fecha = data.get("fecha", now.strftime("%d de %B de %Y"))

html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📊 Reporte de Cartera</title>
<style>
  :root {{
    --bg:#0d1117; --surface:#161b22; --surface2:#21262d; --border:#30363d;
    --text:#e6edf3; --muted:#8b949e; --green:#3fb950; --red:#f85149;
    --yellow:#d29922; --blue:#58a6ff; --purple:#bc8cff; --orange:#ffa657;
  }}
  * {{ box-sizing:border-box; margin:0; padding:0 }}
  body {{ background:var(--bg); color:var(--text); font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; min-height:100vh }}
  header {{ background:var(--surface); border-bottom:1px solid var(--border); padding:20px 32px; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px }}
  .header-title {{ font-size:22px; font-weight:700 }}
  .header-date {{ color:var(--muted); font-size:14px; margin-top:4px }}
  .summary-bar {{ background:var(--surface); border-bottom:1px solid var(--border); padding:12px 32px; display:flex; gap:24px; flex-wrap:wrap }}
  .summary-item {{ display:flex; align-items:center; gap:8px; font-size:14px }}
  .summary-dot {{ width:10px; height:10px; border-radius:50% }}
  .stocks-grid {{ padding:24px 32px; display:grid; gap:20px }}
  .stock-card {{ background:var(--surface); border-radius:8px; overflow:hidden }}
  .stock-header {{ padding:16px 20px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border) }}
  .stock-name {{ font-size:16px; font-weight:700; margin-right:10px }}
  .stock-ticker {{ color:var(--muted); font-size:13px; background:var(--surface2); padding:2px 8px; border-radius:4px }}
  .stock-body {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:0 }}
  .stock-section {{ padding:16px 20px; border-right:1px solid var(--border) }}
  .stock-section:last-child {{ border-right:none }}
  .section-title {{ font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.8px; color:var(--muted); margin-bottom:12px }}
  footer {{ text-align:center; padding:24px; color:var(--muted); font-size:12px; border-top:1px solid var(--border) }}
  @media(max-width:768px) {{ .stock-body {{ grid-template-columns:1fr }} .stock-section {{ border-right:none; border-bottom:1px solid var(--border) }} .stocks-grid {{ padding:12px 16px }} header {{ padding:16px }} .summary-bar {{ padding:12px 16px }} }}
</style>
</head>
<body>
<header>
  <div>
    <div class="header-title">📊 Reporte de Cartera</div>
    <div class="header-date">{fecha}</div>
  </div>
</header>
<div class="summary-bar">
  <div class="summary-item"><div class="summary-dot" style="background:var(--green)"></div><strong>{counts['COMPRAR']}</strong> COMPRAR</div>
  <div class="summary-item"><div class="summary-dot" style="background:var(--yellow)"></div><strong>{counts['MANTENER']}</strong> MANTENER</div>
  <div class="summary-item"><div class="summary-dot" style="background:var(--red)"></div><strong>{counts['VENDER']}</strong> VENDER</div>
  <div class="summary-item"><div class="summary-dot" style="background:var(--purple)"></div><strong>{counts['ESPECULATIVO']}</strong> ESPECULATIVO</div>
</div>
<div class="stocks-grid">
{cards_html}
</div>
<footer>Este reporte es solo informativo y no constituye asesoramiento financiero. · Actualizado: {fecha}</footer>
</body>
</html>"""

with open("reporte_cartera.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Report written ({len(html):,} chars) with {len(data['acciones'])} stocks")
