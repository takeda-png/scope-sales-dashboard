"""
builder_list_staging.csv + companies.csv を結合して
builder_list_view.html を再生成する
"""
import csv, sys, json
sys.stdout.reconfigure(encoding='utf-8')

# --- companies.csv (送信履歴) を URL をキーに読み込む ---
pipeline = {}
with open('companies.csv', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        url = r.get('url', '').strip().rstrip('/')
        if url:
            pipeline[url] = r

# --- builder_list_staging.csv 読み込み ---
with open('builder_list_staging.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

# --- 結合 ---
STATUS_LABEL = {
    'submitted':    ('送信済み',     '#198754'),
    'error':        ('エラー',       '#dc3545'),
    'manual_check': ('要確認',       '#fd7e14'),
    'skip':         ('スキップ',     '#6c757d'),
    'no_form':      ('フォームなし', '#6c757d'),
    'pending':      ('未送信',       '#aaa'),
    '':             ('－',           '#ccc'),
}

data_js = []
for r in rows:
    url = r.get('url', '').strip().rstrip('/')
    p = pipeline.get(url, {})
    status     = p.get('status', '')
    submitted  = p.get('submitted_at', '')
    contact    = p.get('contact_url', '')
    note       = p.get('note', '')
    label, color = STATUS_LABEL.get(status, ('－', '#ccc'))
    data_js.append([
        r.get('company_name', ''),   # 0
        r.get('prefecture', ''),     # 1
        r.get('address', ''),        # 2
        r.get('phone', ''),          # 3
        url,                         # 4 サイトURL
        contact,                     # 5 フォームURL
        status,                      # 6
        label,                       # 7
        color,                       # 8
        submitted,                   # 9
        note,                        # 10
    ])

# --- 集計 ---
total       = len(rows)
with_url    = sum(1 for r in rows if r.get('url','').strip())
without_url = total - with_url
submitted_n = sum(1 for d in data_js if d[6] == 'submitted')
error_n     = sum(1 for d in data_js if d[6] == 'error')
manual_n    = sum(1 for d in data_js if d[6] == 'manual_check')
pending_n   = sum(1 for d in data_js if d[6] == 'pending')
no_pipeline = sum(1 for d in data_js if d[6] == '')

data_json = json.dumps(data_js, ensure_ascii=False)
prefs = sorted(set(r.get('prefecture','') for r in rows if r.get('prefecture','')))
pref_opts = ''.join(f'<option value="{p}">{p}</option>' for p in prefs)

html = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>工務店リスト 全国 - フォーム営業管理</title>
<style>
*{box-sizing:border-box}
body{font-family:sans-serif;margin:0;background:#f0f2f5;font-size:13px}
.hd{background:#2c3e50;color:#fff;padding:10px 16px;position:sticky;top:0;z-index:10;box-shadow:0 2px 6px rgba(0,0,0,.4)}
.hd h1{margin:0 0 6px;font-size:15px}
.ctrl{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.ctrl input,.ctrl select{padding:4px 8px;border:none;border-radius:4px;font-size:12px}
.ctrl input{width:180px}
.summary{background:#1a252f;padding:6px 16px;display:flex;gap:16px;font-size:11px;flex-wrap:wrap}
.summary .box{color:#ecf0f1}
.summary .box b{font-size:13px}
.summary .s-submitted b{color:#2ecc71}
.summary .s-error b{color:#e74c3c}
.summary .s-manual b{color:#f39c12}
.summary .s-pending b{color:#95a5a6}
.summary .s-url b{color:#3498db}
table{width:100%;border-collapse:collapse;background:#fff}
th{background:#ecf0f1;padding:7px 10px;text-align:left;border-bottom:2px solid #bbb;position:sticky;top:82px;z-index:5;cursor:pointer;white-space:nowrap;font-size:12px}
th:hover{background:#d5dbdb}
td{padding:5px 10px;border-bottom:1px solid #eee;vertical-align:middle}
tr:hover td{background:#fef9e7}
a.ul{color:#2980b9;text-decoration:none;font-size:11px;display:inline-block;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:middle}
a.ul:hover{text-decoration:underline}
.pref{background:#eaf2ff;color:#2471a3;padding:1px 5px;border-radius:3px;font-size:11px}
.nourl{color:#bbb;font-size:11px}
.badge{display:inline-block;padding:2px 7px;border-radius:10px;font-size:11px;color:#fff;font-weight:bold;white-space:nowrap}
.dt{color:#555;font-size:11px;white-space:nowrap}
.note{color:#888;font-size:11px;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pg{padding:8px 16px;display:flex;gap:4px;align-items:center;background:#fff;border-top:1px solid #ddd;flex-wrap:wrap}
.pg button{padding:3px 9px;border:1px solid #bbb;border-radius:3px;cursor:pointer;background:#fff;font-size:12px}
.pg button:hover{background:#ecf0f1}
.pg button.active{background:#2c3e50;color:#fff;border-color:#2c3e50}
#cnt{font-weight:bold;color:#f39c12}
</style>
</head>
<body>
<div class="hd">
  <h1>&#127968; 工務店リスト 全国 &mdash; フォーム営業管理 (TOTAL_COUNT社)</h1>
  <div class="ctrl">
    <input id="kw" placeholder="会社名・住所で検索..." oninput="go(1)">
    <select id="pf" onchange="go(1)"><option value="">全都道府県</option>PREF_OPTS</select>
    <select id="uf" onchange="go(1)">
      <option value="">URL全て</option>
      <option value="1">URL取得済み</option>
      <option value="0">URL未取得</option>
    </select>
    <select id="sf" onchange="go(1)">
      <option value="">全ステータス</option>
      <option value="submitted">送信済み</option>
      <option value="error">エラー</option>
      <option value="manual_check">要確認</option>
      <option value="pending">未送信</option>
      <option value="skip">スキップ</option>
      <option value="no_form">フォームなし</option>
    </select>
    <span style="color:#ecf0f1;font-size:12px">表示: <b id="cnt">-</b>社</span>
  </div>
</div>
<div class="summary">
  <div class="box s-submitted"><span>&#10003; 送信済み</span><br><b>SUBMITTED_N社</b></div>
  <div class="box s-error"><span>&#10007; エラー</span><br><b>ERROR_N社</b></div>
  <div class="box s-manual"><span>&#9888; 要確認</span><br><b>MANUAL_N社</b></div>
  <div class="box s-pending"><span>&#9900; 未送信</span><br><b>PENDING_N社</b></div>
  <div class="box s-url"><span>&#128279; URL取得済み</span><br><b>WITH_URL社 / TOTAL_COUNT社</b></div>
</div>
<table><thead><tr>
  <th onclick="srt(0)">#</th>
  <th onclick="srt(1)">社名</th>
  <th onclick="srt(2)">都道府県</th>
  <th onclick="srt(3)">住所</th>
  <th onclick="srt(4)">電話</th>
  <th onclick="srt(5)">サイトURL</th>
  <th onclick="srt(6)">フォームURL</th>
  <th onclick="srt(7)">送信ステータス</th>
  <th onclick="srt(9)">送信日時</th>
  <th onclick="srt(10)">メモ</th>
</tr></thead><tbody id="tb"></tbody></table>
<div class="pg" id="pg"></div>
<script>
const R=DATA_JSON;
const PER=100;
let filtered=R,sortCol=-1,sortAsc=true,page=1;
function go(p){
  page=p;
  const kw=document.getElementById('kw').value.toLowerCase();
  const pf=document.getElementById('pf').value;
  const uf=document.getElementById('uf').value;
  const sf=document.getElementById('sf').value;
  filtered=R.filter(r=>{
    if(kw&&!(r[0].toLowerCase().includes(kw)||r[2].toLowerCase().includes(kw)))return false;
    if(pf&&r[1]!==pf)return false;
    if(uf==='1'&&!r[4])return false;
    if(uf==='0'&&r[4])return false;
    if(sf&&r[6]!==sf)return false;
    return true;
  });
  if(sortCol>=0){
    filtered=[...filtered].sort((a,b)=>{
      const va=a[sortCol]||'',vb=b[sortCol]||'';
      return sortAsc?va.localeCompare(vb,'ja'):vb.localeCompare(va,'ja');
    });
  }
  render();
}
function srt(col){
  if(sortCol===col)sortAsc=!sortAsc; else{sortCol=col;sortAsc=true;}
  go(page);
}
function mkUrl(url,cls){
  if(!url)return '<span class="nourl">-</span>';
  const s=url.replace(/^https?:\\/\\//,'').substring(0,30);
  return '<a class="ul '+cls+'" href="'+url+'" target="_blank" title="'+url+'">&#128279;'+s+'</a>';
}
function render(){
  document.getElementById('cnt').textContent=filtered.length.toLocaleString();
  const start=(page-1)*PER,end=Math.min(start+PER,filtered.length);
  const rows=filtered.slice(start,end);
  document.getElementById('tb').innerHTML=rows.map((r,i)=>{
    const badge='<span class="badge" style="background:'+r[8]+'">'+r[7]+'</span>';
    return '<tr>'
      +'<td>'+(start+i+1)+'</td>'
      +'<td><b>'+r[0]+'</b></td>'
      +'<td><span class="pref">'+r[1]+'</span></td>'
      +'<td>'+r[2]+'</td>'
      +'<td>'+r[3]+'</td>'
      +'<td>'+mkUrl(r[4],'')+'</td>'
      +'<td>'+mkUrl(r[5],'')+'</td>'
      +'<td>'+badge+'</td>'
      +'<td class="dt">'+r[9]+'</td>'
      +'<td class="note" title="'+r[10]+'">'+r[10]+'</td>'
      +'</tr>';
  }).join('');
  const pages=Math.ceil(filtered.length/PER);
  let pg='';
  for(let i=1;i<=pages;i++){
    if(i===1||i===pages||Math.abs(i-page)<=2){
      pg+='<button class="'+(i===page?'active':'')+'" onclick="go('+i+')">'+i+'</button>';
    }else if(Math.abs(i-page)===3){
      pg+='<span style="padding:0 4px">...</span>';
    }
  }
  document.getElementById('pg').innerHTML=pg;
}
go(1);
</script>
</body>
</html>"""

html = (html
    .replace('TOTAL_COUNT', f'{total:,}')
    .replace('WITH_URL',    f'{with_url:,}')
    .replace('SUBMITTED_N', f'{submitted_n:,}')
    .replace('ERROR_N',     f'{error_n:,}')
    .replace('MANUAL_N',    f'{manual_n:,}')
    .replace('PENDING_N',   f'{pending_n:,}')
    .replace('PREF_OPTS',   pref_opts)
    .replace('DATA_JSON',   data_json)
)

with open('builder_list_view.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f'生成完了!')
print(f'  合計:       {total:,}社')
print(f'  URL取得済み: {with_url:,}社')
print(f'  送信済み:    {submitted_n:,}社')
print(f'  エラー:      {error_n:,}社')
print(f'  要確認:      {manual_n:,}社')
print(f'  未送信:      {pending_n:,}社')
print(f'  パイプライン外: {no_pipeline:,}社')
