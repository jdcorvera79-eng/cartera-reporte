import os, json, requests, anthropic
from xml.etree import ElementTree as ET
from datetime import datetime
from urllib.parse import quote
import yfinance as yf
import numpy as np

# ── Stock list ────────────────────────────────────────────────────────────────

STOCKS = [
    {"ticker": "TSLA",  "yf": "TSLA",   "name": "Tesla"},
    {"ticker": "HIMS",  "yf": "HIMS",   "name": "Hims & Hers"},
    {"ticker": "DUOL",  "yf": "DUOL",   "name": "Duolingo"},
    {"ticker": "BMNR",  "yf": "BMNR",   "name": "Bitmine Immersion Technologies"},
    {"ticker": "LODE",  "yf": "LODE",   "name": "Comstock Inc"},
    {"ticker": "HGRAF", "yf": "HGRAF",  "name": "HydroGraph Clean Power"},
    {"ticker": "HBFG",  "yf": "HBFG",   "name": "Happy Belly Food Group"},
    {"ticker": "ABX",   "yf": "ABX",    "name": "Abacus Global Management",    "query": "ABX Abacus Global Management"},
    {"ticker": "3350",  "yf": "3350.T", "name": "Metaplanet",                  "query": "Metaplanet Bitcoin treasury"},
    {"ticker": "BILD",  "yf": "BILD.V", "name": "BuildDirect Technologies",    "query": "BuildDirect Technologies BILD"},
    {"ticker": "LIB",   "yf": "LIB.V",  "name": "LibertyStream Infrastructure","query": "LibertyStream Infrastructure LIB"},
    {"ticker": "TTT",   "yf": "TTT",    "name": "Titonic",                     "query": "Titonic TTT stock"},
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CarteraBot/1.0)"}
HISTORICO_FILE = "historico.json"

REC_COLOR = {
    "COMPRAR":      "#3fb950",
    "MANTENER":     "#d29922",
    "VENDER":       "#f85149",
    "ESPECULATIVO": "#bc8cff",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def calculate_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    delta    = np.diff(closes)
    gain     = np.where(delta > 0, delta, 0.0)
    loss     = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.mean(gain[-period:])
    avg_loss = np.mean(loss[-period:])
    if avg_loss == 0:
        return 100
    return round(100 - 100 / (1 + avg_gain / avg_loss), 1)

def sparkline_svg(prices, width=130, height=38):
    if len(prices) < 2:
        return ""
    mn, mx = min(prices), max(prices)
    rng = mx - mn or 1
    pad = 3
    pts = []
    for i, p in enumerate(prices):
        x = round(i / (len(prices) - 1) * width, 1)
        y = round(height - pad - (p - mn) / rng * (height - 2 * pad), 1)
        pts.append(f"{x},{y}")
    color = "#3fb950" if prices[-1] >= prices[0] else "#f85149"
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'style="display:block;margin-bottom:10px">'
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" '
            f'stroke-width="1.5" stroke-linejoin="round"/></svg>')

def chg_str(v):
    return f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%"

def fetch_technicals(s, spy_30d=None):
    try:
        hist = yf.Ticker(s["yf"]).history(period="1y")
        if hist.empty:
            return None
        closes   = hist["Close"].values.astype(float)
        vols     = hist["Volume"].values.astype(float)
        price    = closes[-1]
        ma50     = np.mean(closes[-50:])  if len(closes) >= 50  else np.mean(closes)
        ma200    = np.mean(closes[-200:]) if len(closes) >= 200 else np.mean(closes)
        rsi      = calculate_rsi(closes)
        avg_vol  = np.mean(vols[-20:])    if len(vols)   >= 20  else np.mean(vols)
        vol_ratio = vols[-1] / avg_vol if avg_vol > 0 else 1.0
        vol_label = "Alto" if vol_ratio > 1.3 else ("Bajo" if vol_ratio < 0.7 else "Normal")
        wk52_hi  = float(np.max(closes[-252:])) if len(closes) >= 252 else float(np.max(closes))
        wk52_lo  = float(np.min(closes[-252:])) if len(closes) >= 252 else float(np.min(closes))
        c1d  = (closes[-1] / closes[-2]  - 1) * 100 if len(closes) >= 2  else 0
        c7d  = (closes[-1] / closes[-8]  - 1) * 100 if len(closes) >= 8  else 0
        c30d = (closes[-1] / closes[-31] - 1) * 100 if len(closes) >= 31 else 0
        vs_sp = f"{c30d - spy_30d:+.1f}%" if spy_30d is not None else "N/A"
        cur  = "¥" if s["yf"].endswith(".T") else ("C$" if s["yf"].endswith(".V") else "$")
        fmt  = lambda v: f"{cur}{v:.2f}" if v < 100 else f"{cur}{v:.1f}"
        spark = closes[-30:].tolist() if len(closes) >= 30 else closes.tolist()
        return {
            "precio":    fmt(price),
            "cambio":    chg_str(c1d),
            "cambio_7d": chg_str(c7d),
            "cambio_30d":chg_str(c30d),
            "vs_sp500":  vs_sp,
            "ma50":      fmt(ma50),
            "ma200":     fmt(ma200),
            "rsi":       int(rsi),
            "volumen":   vol_label,
            "semana52":  f"{fmt(wk52_lo)} – {fmt(wk52_hi)}",
            "spark":     spark,
        }
    except Exception as e:
        print(f"  yfinance error {s['yf']}: {e}")
        return None

def fetch_rss(url):
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
    except:
        return []

def fetch_yahoo(ticker):
    return fetch_rss(f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US")

def fetch_google(query):
    items = fetch_rss(f"https://news.google.com/rss/search?q={quote(query)}+stock&hl=en-US&gl=US&ceid=US:en")
    for i in items:
        i.pop("summary", None)
    return items

def fetch_macro_news():
    topics = [
        ("Mercado general", "S&P500 stock market today 2026"),
        ("Reserva Federal", "Federal Reserve interest rates 2026"),
        ("Bitcoin / Cripto", "Bitcoin price today 2026"),
        ("Aranceles / Macro", "trade tariffs market impact 2026"),
    ]
    results = []
    for label, query in topics:
        items = fetch_google(query)[:2]
        for item in items:
            results.append({"categoria": label, **item})
    return results

def load_historico():
    if os.path.exists(HISTORICO_FILE):
        with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_historico(historico, acciones):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    entry = {"fecha": today, "recs": {a["ticker"]: a["recomendacion"] for a in acciones}}
    historico = [h for h in historico if h["fecha"] != today]
    historico.append(entry)
    historico = historico[-30:]
    with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)
    return historico

# ── Data fetching ─────────────────────────────────────────────────────────────

print("Fetching SPY data for benchmark...")
spy_30d = None
try:
    spy_hist = yf.Ticker("SPY").history(period="2mo")["Close"].values.astype(float)
    if len(spy_hist) >= 31:
        spy_30d = (spy_hist[-1] / spy_hist[-31] - 1) * 100
        print(f"  SPY 30d: {spy_30d:+.1f}%")
except Exception as e:
    print(f"  SPY error: {e}")

print("Fetching stock news and technicals...")
all_news        = {}
all_technicals  = {}
for s in STOCKS:
    ticker = s["ticker"]
    query  = s.get("query", f"{s['name']} {ticker}")
    news   = fetch_yahoo(ticker) or []
    if len(news) < 2:
        news += fetch_google(query)
    all_news[ticker] = {"name": s["name"], "news": news[:3]}
    tech = fetch_technicals(s, spy_30d)
    all_technicals[ticker] = tech
    ts = f"precio={tech['precio']} rsi={tech['rsi']}" if tech else "sin datos"
    print(f"  {ticker}: {len(all_news[ticker]['news'])} noticias, {ts}")

print("Fetching macro news...")
macro_news = fetch_macro_news()
print(f"  {len(macro_news)} macro items")

historico = load_historico()

# ── Claude API ────────────────────────────────────────────────────────────────

now    = datetime.utcnow()
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

BATCH_PROMPT = """Analiza estas acciones y responde ÚNICAMENTE con un array JSON válido (sin explicaciones, sin markdown).

FECHA: {fecha}
DATOS: {datos}

Array JSON con esta estructura por acción:
[{{"ticker":"TSLA","nombre":"Tesla","recomendacion":"MANTENER","razonamiento":"2 frases en español basadas en noticias y datos técnicos.","noticias":[{{"titulo":"Título en español","fuente":"Yahoo Finance","fecha":"18 abr 2026","url":"https://...","descripcion":"Una frase en español.","oficial":false}}]}}]

Reglas:
- recomendacion: COMPRAR, MANTENER, VENDER o ESPECULATIVO
- oficial=true si fuente es GlobeNewswire, PR Newswire, BusinessWire o web IR empresa
- Todo texto en español, empieza con ["""

def analyze_batch(batch_tickers, fecha):
    batch_data = {t: {"name": all_news[t]["name"], "news": all_news[t]["news"], "tech": all_technicals.get(t)} for t in batch_tickers}
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": BATCH_PROMPT.format(fecha=fecha, datos=json.dumps(batch_data, ensure_ascii=False))}],
    )
    raw = msg.content[0].text.strip()
    print(f"  stop={msg.stop_reason} len={len(raw)}")
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    if not raw.startswith("["):
        raw = raw[raw.find("["):]
    return json.loads(raw)

tickers    = list(all_news.keys())
batches    = [tickers[i:i+4] for i in range(0, len(tickers), 4)]
fecha_str  = now.strftime("%A %d de %B de %Y")

print("Calling Claude API in batches...")
all_acciones = []
for i, batch in enumerate(batches):
    print(f"  Batch {i+1}/{len(batches)}: {batch}")
    all_acciones.extend(analyze_batch(batch, fecha_str))
    print(f"  Total so far: {len(all_acciones)}")

print("Generating executive summary...")
cartera_resumen = [{"ticker": a["ticker"], "rec": a["recomendacion"], "razon": a["razonamiento"]} for a in all_acciones]
summary_prompt = f"""Eres un analista financiero. Resume en 3-4 frases el estado actual de esta cartera.

FECHA: {fecha_str}
CARTERA: {json.dumps(cartera_resumen, ensure_ascii=False)}
MACRO: {json.dumps(macro_news[:6], ensure_ascii=False)}

Escribe un párrafo en español (directo, profesional) que mencione: sentimiento general (alcista/bajista/mixto), 1-2 acciones destacadas, contexto macro relevante. Solo el párrafo, sin títulos."""

summary_msg  = client.messages.create(model="claude-sonnet-4-6", max_tokens=400,
    messages=[{"role": "user", "content": summary_prompt}])
resumen_ejecutivo = summary_msg.content[0].text.strip()

historico = save_historico(historico, all_acciones)
print(f"Total: {len(all_acciones)} stocks")

# ── HTML helpers ──────────────────────────────────────────────────────────────

def rsi_bar(rsi):
    color = "#f85149" if rsi < 30 else ("#ffa657" if rsi > 70 else "#3fb950")
    label = f"Sobrevendido ({rsi})" if rsi < 30 else (f"Sobrecomprado ({rsi})" if rsi > 70 else f"Neutral ({rsi})")
    return f'''<div style="margin-top:8px">
      <div style="font-size:11px;color:var(--muted);margin-bottom:3px">RSI: {label}</div>
      <div style="background:var(--surface2);border-radius:4px;height:7px;overflow:hidden">
        <div style="width:{rsi}%;height:100%;background:{color};border-radius:4px"></div>
      </div></div>'''

def hist_badges(ticker):
    last5 = historico[-5:] if len(historico) >= 5 else historico
    if not last5:
        return ""
    rows = ""
    for h in reversed(last5):
        rec = h["recs"].get(ticker, "—")
        c   = REC_COLOR.get(rec, "#8b949e")
        rows += f'<span style="font-size:10px;background:{c}22;color:{c};border:1px solid {c}55;border-radius:3px;padding:1px 5px;margin:1px;display:inline-block">{h["fecha"][5:]} {rec}</span>'
    return f'<div style="margin-top:10px"><div style="font-size:10px;color:var(--muted);margin-bottom:4px;text-transform:uppercase;letter-spacing:.6px">Historial</div>{rows}</div>'

def stock_card(a):
    color = REC_COLOR.get(a["recomendacion"], "#58a6ff")
    tech  = all_technicals.get(a["ticker"]) or {}

    news_html = ""
    for n in a.get("noticias", []):
        badge = '<span style="color:#58a6ff;font-size:10px;font-weight:600">📋 [OFICIAL]</span> ' if n.get("oficial") else ""
        news_html += f'''<div style="margin-bottom:11px;padding-bottom:11px;border-bottom:1px solid var(--border)">
          {badge}<a href="{n['url']}" target="_blank" style="color:var(--text);font-weight:600;font-size:13px;text-decoration:none;line-height:1.4">{n['titulo']}</a>
          <div style="color:var(--muted);font-size:11px;margin-top:3px">{n['fuente']} · {n['fecha']}</div>
          <div style="color:var(--muted);font-size:12px;margin-top:3px">{n['descripcion']}</div>
        </div>'''

    precio    = tech.get("precio",    "N/A")
    cambio    = tech.get("cambio",    "—")
    c7d       = tech.get("cambio_7d", "—")
    c30d      = tech.get("cambio_30d","—")
    vs_sp     = tech.get("vs_sp500",  "N/A")
    ma50      = tech.get("ma50",      "N/A")
    ma200     = tech.get("ma200",     "N/A")
    volumen   = tech.get("volumen",   "N/A")
    semana52  = tech.get("semana52",  "N/A")
    rsi_val   = tech.get("rsi",       50)
    spark     = tech.get("spark",     [])

    def cc(v):
        return "#3fb950" if "+" in str(v) else "#f85149"

    return f'''<div class="stock-card" style="border-left:4px solid {color}">
  <div class="stock-header">
    <div>
      <span class="stock-name">{a['nombre']}</span>
      <span class="stock-ticker">{a['ticker']}</span>
    </div>
    <div style="text-align:right">
      <div style="font-size:18px;font-weight:700">{precio}</div>
      <div style="font-size:12px;display:flex;gap:8px;justify-content:flex-end;margin-top:3px">
        <span style="color:{cc(cambio)}">1d {cambio}</span>
        <span style="color:{cc(c7d)}">7d {c7d}</span>
        <span style="color:{cc(c30d)}">30d {c30d}</span>
      </div>
    </div>
  </div>
  <div class="stock-body">
    <div class="stock-section">
      <div class="section-title">📰 Noticias</div>
      {sparkline_svg(spark)}
      {news_html or '<div style="color:var(--muted);font-size:13px">Sin noticias recientes</div>'}
    </div>
    <div class="stock-section">
      <div class="section-title">📈 Análisis técnico</div>
      <table style="width:100%;font-size:13px;border-collapse:collapse">
        <tr><td style="color:var(--muted);padding:3px 0">MA50</td><td style="text-align:right">{ma50}</td></tr>
        <tr><td style="color:var(--muted);padding:3px 0">MA200</td><td style="text-align:right">{ma200}</td></tr>
        <tr><td style="color:var(--muted);padding:3px 0">Volumen</td><td style="text-align:right">{volumen}</td></tr>
        <tr><td style="color:var(--muted);padding:3px 0">52 sem.</td><td style="text-align:right;font-size:11px">{semana52}</td></tr>
        <tr><td style="color:var(--muted);padding:3px 0">vs S&P500</td><td style="text-align:right;color:{cc(vs_sp)}">{vs_sp}</td></tr>
      </table>
      {rsi_bar(rsi_val)}
    </div>
    <div class="stock-section">
      <div class="section-title">🎯 Recomendación</div>
      <div style="margin-bottom:10px">
        <span style="background:{color};color:#000;padding:4px 14px;border-radius:20px;font-weight:700;font-size:13px">{a['recomendacion']}</span>
      </div>
      <div style="color:var(--muted);font-size:13px;line-height:1.6">{a['razonamiento']}</div>
      {hist_badges(a['ticker'])}
    </div>
  </div>
</div>'''

# ── Build HTML ────────────────────────────────────────────────────────────────

counts = {k: 0 for k in REC_COLOR}
for a in all_acciones:
    r = a.get("recomendacion", "MANTENER")
    if r in counts:
        counts[r] += 1

cards_html = "\n".join(stock_card(a) for a in all_acciones)
fecha = fecha_str

macro_html = ""
for m in macro_news:
    macro_html += f'''<div style="min-width:220px;max-width:280px;background:var(--surface2);border-radius:6px;padding:10px 14px;flex-shrink:0">
      <div style="font-size:10px;color:var(--blue);font-weight:600;text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px">{m['categoria']}</div>
      <a href="{m['link']}" target="_blank" style="color:var(--text);font-size:12px;font-weight:600;text-decoration:none;line-height:1.4">{m['title']}</a>
      <div style="color:var(--muted);font-size:11px;margin-top:3px">{m['date'][:16] if m.get('date') else ''}</div>
    </div>'''

html = f'''<!DOCTYPE html>
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
  .header-date  {{ color:var(--muted); font-size:14px; margin-top:4px }}
  .summary-bar  {{ background:var(--surface); border-bottom:1px solid var(--border); padding:12px 32px; display:flex; gap:24px; flex-wrap:wrap; align-items:center }}
  .summary-item {{ display:flex; align-items:center; gap:8px; font-size:14px }}
  .summary-dot  {{ width:10px; height:10px; border-radius:50%; flex-shrink:0 }}
  .exec-summary {{ background:var(--surface); border-bottom:1px solid var(--border); padding:16px 32px }}
  .exec-summary p {{ color:var(--muted); font-size:14px; line-height:1.7; max-width:900px }}
  .macro-strip  {{ padding:16px 32px; display:flex; gap:12px; overflow-x:auto; border-bottom:1px solid var(--border) }}
  .stocks-grid  {{ padding:24px 32px; display:grid; gap:20px }}
  .stock-card   {{ background:var(--surface); border-radius:8px; overflow:hidden }}
  .stock-header {{ padding:16px 20px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--border) }}
  .stock-name   {{ font-size:16px; font-weight:700; margin-right:10px }}
  .stock-ticker {{ color:var(--muted); font-size:13px; background:var(--surface2); padding:2px 8px; border-radius:4px }}
  .stock-body   {{ display:grid; grid-template-columns:1fr 1fr 1fr }}
  .stock-section {{ padding:16px 20px; border-right:1px solid var(--border) }}
  .stock-section:last-child {{ border-right:none }}
  .section-title {{ font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:.8px; color:var(--muted); margin-bottom:12px }}
  footer {{ text-align:center; padding:24px; color:var(--muted); font-size:12px; border-top:1px solid var(--border) }}
  @media(max-width:768px) {{
    .stock-body {{ grid-template-columns:1fr }}
    .stock-section {{ border-right:none; border-bottom:1px solid var(--border) }}
    .stocks-grid,.exec-summary,.macro-strip {{ padding:12px 16px }}
    header,.summary-bar {{ padding:16px }}
  }}
</style>
</head>
<body>

<header>
  <div>
    <div class="header-title">📊 Reporte de Cartera</div>
    <div class="header-date">{fecha}</div>
  </div>
</header>

<div class="exec-summary">
  <div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:var(--blue);margin-bottom:8px">Resumen ejecutivo</div>
  <p>{resumen_ejecutivo}</p>
</div>

<div class="summary-bar">
  <div class="summary-item"><div class="summary-dot" style="background:var(--green)"></div><strong>{counts['COMPRAR']}</strong>&nbsp;COMPRAR</div>
  <div class="summary-item"><div class="summary-dot" style="background:var(--yellow)"></div><strong>{counts['MANTENER']}</strong>&nbsp;MANTENER</div>
  <div class="summary-item"><div class="summary-dot" style="background:var(--red)"></div><strong>{counts['VENDER']}</strong>&nbsp;VENDER</div>
  <div class="summary-item"><div class="summary-dot" style="background:var(--purple)"></div><strong>{counts['ESPECULATIVO']}</strong>&nbsp;ESPECULATIVO</div>
  <div style="margin-left:auto;font-size:12px;color:var(--muted)">SPY 30d: {f"{spy_30d:+.1f}%" if spy_30d is not None else "N/A"}</div>
</div>

<div class="macro-strip">
  <div style="font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.7px;writing-mode:vertical-lr;transform:rotate(180deg);flex-shrink:0;align-self:center">Macro</div>
  {macro_html}
</div>

<div class="stocks-grid">
{cards_html}
</div>

<footer>Este reporte es solo informativo y no constituye asesoramiento financiero. · Actualizado: {fecha}</footer>
</body>
</html>'''

with open("reporte_cartera.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"Done: {len(all_acciones)} stocks, {len(html):,} chars")
