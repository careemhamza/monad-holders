import io, csv, re, time
from flask import Flask, request, jsonify, Response, render_template_string
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

EVM_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")

UA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

def is_evm(addr: str) -> bool:
    return bool(EVM_RE.match(addr.strip()))

def unique(seq):
    out, seen = [], set()
    for s in seq:
        if s not in seen:
            out.append(s)
            seen.add(s)
    return out

def fetch_holders(contract: str, base: str, max_pages: int = 200, sleep=0.2):
    """
    يمر على صفحات الـ holders ويلم أي لينك عنوان /address/0x... 
    """
    holders = []
    page = 1
    while page <= max_pages:
        url = f"{base}/token/{contract}?tab=Holder&page={page}"
        r = requests.get(url, timeout=30, headers=UA_HEADERS)
        r.raise_for_status()
        html = r.text

        soup = BeautifulSoup(html, "lxml")

        # نجيب كل لينكات العناوين
        links = soup.select('a[href^="/address/0x"], a[href*="/address/0x"]')
        found = 0
        for a in links:
            text = (a.get_text(strip=True) or "").split()[0]
            # أوقات النص بيكون مختصر (0x1234...abcd)؛ حاول نقرأ الـ href كمان
            href = a.get("href", "")
            cand = text if is_evm(text) else ""
            if not cand and "/address/" in href:
                # استخرج العنوان من الـ href
                m = re.search(r"0x[a-fA-F0-9]{40}", href)
                if m:
                    cand = m.group(0)
            if cand and is_evm(cand):
                holders.append(cand.lower())
                found += 1

        # لو الصفحة مفيهاش جديد نوقف
        if found == 0:
            break

        page += 1
        time.sleep(sleep)

    # فلترة + إزالة مكرر
    holders = [h for h in holders if is_evm(h)]
    holders = unique(holders)
    return holders

INDEX_HTML = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Monad Holders Extractor</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 min-h-screen">
  <div class="max-w-3xl mx-auto p-6">
    <h1 class="text-2xl font-bold mb-4">استخراج عناوين الـ NFT Holders (Monad)</h1>
    <div class="bg-white shadow rounded-2xl p-5 space-y-4">
      <div class="grid md:grid-cols-3 gap-3">
        <div class="md:col-span-2">
          <label class="block text-sm mb-1">عنوان العقد (Contract)</label>
          <input id="contract" class="w-full border rounded-xl px-3 py-2"
                 placeholder="0xC9A8... (مثال)" value="0xC9A8158579568264bC2eb5903e329b8752cC1845" />
        </div>
        <div>
          <label class="block text-sm mb-1">الشبكة</label>
          <select id="net" class="w-full border rounded-xl px-3 py-2">
            <option value="testnet" selected>Monad Testnet</option>
            <option value="mainnet">Monad Mainnet</option>
          </select>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <button id="fetchBtn" class="px-4 py-2 rounded-xl bg-black text-white">Fetch</button>
        <div id="spinner" class="hidden animate-spin h-5 w-5 border-2 border-slate-300 border-t-black rounded-full"></div>
        <span id="status" class="text-sm text-slate-600"></span>
      </div>

      <div id="resultBox" class="hidden">
        <div class="flex items-center justify-between">
          <h2 class="font-semibold">النتيجة</h2>
          <div class="flex items-center gap-2">
            <button id="copyBtn" class="px-3 py-1 rounded-lg border">Copy</button>
            <a id="downloadCsv" class="px-3 py-1 rounded-lg border" href="#" download>Download CSV</a>
          </div>
        </div>
        <p class="text-sm text-slate-600 mt-1">العناوين: <span id="count">0</span></p>
        <textarea id="out" class="w-full h-80 border rounded-xl p-3 mt-2 font-mono text-xs"></textarea>
      </div>
    </div>

    <p class="text-xs text-slate-500 mt-4">لو النتيجة فاضية: تأكد إن صفحة الـ Explorer فيها تبويب Holders، أو جرّب بعد دقيقة لو في Rate-Limit.</p>
  </div>

<script>
async function fetchHolders() {
  const contract = document.getElementById('contract').value.trim();
  const net = document.getElementById('net').value;
  const status = document.getElementById('status');
  const spinner = document.getElementById('spinner');
  const out = document.getElementById('out');
  const resultBox = document.getElementById('resultBox');
  const count = document.getElementById('count');
  const dl = document.getElementById('downloadCsv');

  if (!/^0x[a-fA-F0-9]{40}$/.test(contract)) {
    status.textContent = 'عنوان العقد غير صالح';
    return;
  }

  status.textContent = '';
  spinner.classList.remove('hidden');
  resultBox.classList.add('hidden');
  out.value = '';

  try {
    const res = await fetch('/api/extract', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ contract, net })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Request failed');

    const list = data.holders || [];
    out.value = list.join('\\n');
    count.textContent = list.length;
    resultBox.classList.remove('hidden');

    // Prepare CSV download link
    const params = new URLSearchParams({ contract, net });
    dl.href = '/download.csv?' + params.toString();

    status.textContent = list.length ? 'تم الجلب بنجاح' : 'مفيش Holders متاحة';
  } catch (e) {
    status.textContent = 'خطأ: ' + e.message;
  } finally {
    spinner.classList.add('hidden');
  }
}

document.getElementById('fetchBtn').addEventListener('click', fetchHolders);
document.getElementById('copyBtn').addEventListener('click', () => {
  const out = document.getElementById('out');
  out.select();
  document.execCommand('copy');
});
</script>

</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(INDEX_HTML)

@app.route("/api/extract", methods=["POST"])
def api_extract():
    data = request.get_json(force=True, silent=True) or {}
    contract = (data.get("contract") or "").strip()
    net = (data.get("net") or "testnet").strip().lower()

    if not is_evm(contract):
        return jsonify({"error": "Invalid contract address"}), 400

    base = "https://testnet.monadexplorer.com" if net == "testnet" else "https://monadexplorer.com"
    try:
        holders = fetch_holders(contract, base=base)
        return jsonify({"holders": holders, "count": len(holders), "contract": contract, "net": net})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download.csv", methods=["GET"])
def download_csv():
    contract = (request.args.get("contract") or "").strip()
    net = (request.args.get("net") or "testnet").strip().lower()
    if not is_evm(contract):
        return Response("Invalid contract", status=400)

    base = "https://testnet.monadexplorer.com" if net == "testnet" else "https://monadexplorer.com"

    try:
        holders = fetch_holders(contract, base=base)
        # CSV in-memory
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["address"])
        for h in holders:
            writer.writerow([h])
        csv_bytes = output.getvalue().encode("utf-8")
        return Response(
            csv_bytes,
            mimetype="text/csv",
            headers={"Content-Disposition": f'attachment; filename="holders_{contract[:10]}.csv"'}
        )
    except Exception as e:
        return Response(str(e), status=500)

# required by Vercel
app = app
