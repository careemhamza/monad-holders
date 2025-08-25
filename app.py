import io, csv, re, time
from flask import Flask, request, jsonify, render_template_string
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

EVM_HEX = re.compile(r"^0x[a-fA-F0-9]{40}$")

def is_evm_address(x: str) -> bool:
    return bool(EVM_HEX.match(x.strip()))

def unique_order(seq):
    seen, out = set(), []
    for s in seq:
        if s not in seen:
            out.append(s)
            seen.add(s)
    return out

def fetch_holders(contract, base="https://testnet.monadexplorer.com"):
    holders = []
    page = 1
    while True:
        url = f"{base}/token/{contract}?tab=Holder&page={page}"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        rows = soup.select("table tr")
        new_count = 0
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) < 2: 
                continue
            addr = (tds[0].get_text(strip=True) or "").split("\n")[0]
            if is_evm_address(addr):
                holders.append(addr.lower())
                new_count += 1
        if new_count == 0: break
        page += 1
        time.sleep(0.2)
    return unique_order(holders)

HTML = """
<!doctype html>
<html><head><title>Monad Holders Extractor</title></head>
<body>
  <h1>Monad Holders Extractor</h1>
  <form id="f" method="POST" action="/extract">
    <input name="contract" placeholder="0x..." size="60"/>
    <select name="net">
      <option value="testnet">testnet</option>
      <option value="mainnet">mainnet</option>
    </select>
    <button type="submit">Fetch</button>
  </form>
  {% if holders %}
    <h3>{{ holders|length }} holders found</h3>
    <pre>{{ holders|join("\\n") }}</pre>
  {% endif %}
</body></html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML)

@app.route("/extract", methods=["POST"])
def extract():
    contract = request.form.get("contract","").strip()
    net = request.form.get("net","testnet")
    base = "https://testnet.monadexplorer.com" if net=="testnet" else "https://monadexplorer.com"
    try:
        holders = fetch_holders(contract, base=base)
        return render_template_string(HTML, holders=holders)
    except Exception as e:
        return f"Error: {e}", 500

# Vercel يحتاج handler باسم app
app = app
