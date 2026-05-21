from .usage_snapshot import UsageSnapshot, ModelUsage

# ── two themes: dark & light ────────────────────────────────────────

THEMES = {
    "dark": {
        "name": "深色",
        "bg": "#0d1117",
        "surface": "#161b22",
        "border": "rgba(255,255,255,.08)",
        "text": "#c9d1d9",
        "text_dim": "#6e7681",
        "text_bright": "#f0f6fc",
        "card_balance_from": "#1a1350",
        "card_balance_to": "#2d1f8a",
        "card_cost_from": "#1a1118",
        "card_cost_to": "#2d1a26",
        "accent": "#6e8cff",
        "accent2": "#4c6ef5",
        "cost_text": "#f0a050",
        "model_bg": "rgba(255,255,255,.03)",
        "model_hover": "rgba(255,255,255,.06)",
        "section": "#6e7681",
        "prompt_bar": "#6e8cff",
        "comp_bar": "#3fb950",
        "shadow": "none",
    },
    "light": {
        "name": "浅色",
        "bg": "#f0f2f5",
        "surface": "#ffffff",
        "border": "rgba(0,0,0,.08)",
        "text": "#24292f",
        "text_dim": "#656d76",
        "text_bright": "#1a1a2e",
        "card_balance_from": "#eef0ff",
        "card_balance_to": "#dde0ff",
        "card_cost_from": "#fff8f0",
        "card_cost_to": "#ffe8d0",
        "accent": "#4c6ef5",
        "accent2": "#364fc7",
        "cost_text": "#c05020",
        "model_bg": "#ffffff",
        "model_hover": "#f6f8fa",
        "section": "#656d76",
        "prompt_bar": "#6e8cff",
        "comp_bar": "#2da44e",
        "shadow": "0 1px 3px rgba(0,0,0,.06)",
    },
}

DEFAULT_THEME = "dark"

THEME_NAMES = {k: v["name"] for k, v in THEMES.items()}

# JS update function
UPDATE_JS = r"""
<script>
window._updateData = function(data) {
  document.getElementById('bal-val').textContent = '¥' + data.total_balance.toFixed(2);
  document.getElementById('bal-sub').textContent = data.topped_up_balance_fmt;
  document.getElementById('cost-val').textContent = '¥' + data.total_cost.toFixed(2);
  document.getElementById('cost-sub').textContent = data.total_tokens_fmt + ' tokens';
  document.getElementById('footer-status').textContent = data.ts_text;
  var dot = document.getElementById('dot');
  dot.className = 'footer-dot ' + data.dot_class;
  var grid = document.getElementById('models-grid');
  grid.innerHTML = data.model_cards_html;
};
</script>"""


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _cache_rate(m: ModelUsage) -> float:
    total = m.prompt_cache_hit_tokens + m.prompt_cache_miss_tokens
    return (m.prompt_cache_hit_tokens / total * 100) if total else 0.0


def _max_tokens(models: list[ModelUsage]) -> int:
    return max((m.total_tokens for m in models), default=1)


def _build_model_cards(snap: UsageSnapshot) -> str:
    max_t = _max_tokens(snap.models)
    cards = ""
    for m in snap.models:
        rate = _cache_rate(m)
        rate_color = "#2da44e" if rate > 80 else ("#d29922" if rate > 30 else "#cf222e")
        p_pct = (m.prompt_tokens / max_t * 100) if max_t else 0
        c_pct = (m.completion_tokens / max_t * 100) if max_t else 0

        sub = ""
        if m.prompt_cache_hit_tokens:
            sub += '<div class="dr"><span class="dl">缓存命中</span><span class="dv">' + _fmt(m.prompt_cache_hit_tokens) + '</span></div>'
        if m.prompt_cache_miss_tokens:
            sub += '<div class="dr"><span class="dl">缓存未命中</span><span class="dv">' + _fmt(m.prompt_cache_miss_tokens) + '</span></div>'

        click = 'onclick="this.classList.toggle(\'open\')"' if sub else ''

        cards += '<div class="mc" ' + click + '>'
        cards += '<div class="mh"><span class="mn">' + m.model_name + '</span><span class="mp">¥' + f"{m.cost:.2f}" + '</span></div>'
        cards += '<div class="cw"><div class="cb"><div class="cf" style="width:' + f"{rate:.0f}" + '%;background:' + rate_color + '"></div></div><span class="cl" style="color:' + rate_color + '">' + f"{rate:.0f}%</span></div>"
        cards += '<div class="mr"><span class="ml">Prompt</span><span class="mv">' + _fmt(m.prompt_tokens) + '</span><div class="mb"><div class="mf pbar" style="width:' + f"{p_pct:.1f}" + '%"></div></div></div>'
        cards += '<div class="mr"><span class="ml">Completion</span><span class="mv">' + _fmt(m.completion_tokens) + '</span><div class="mb"><div class="mf cbar" style="width:' + f"{c_pct:.1f}" + '%"></div></div></div>'
        cards += '<div class="mr"><span class="ml">API</span><span class="mv">' + str(m.api_calls) + '</span></div>'
        if sub:
            cards += '<div class="sd">' + sub + '</div>'
        cards += '</div>'
    return cards


def make_update_json(snap, status: str) -> str:
    import json as _json
    dot_class = {"ok": "dot-ok", "cached": "dot-cached", "error": "dot-err"}.get(status, "dot-ok")
    payload = {
        "total_balance": snap.total_balance,
        "topped_up_balance_fmt": "充值 ¥" + f"{snap.topped_up_balance:.2f}",
        "total_cost": snap.total_cost,
        "total_tokens_fmt": _fmt(snap.total_tokens),
        "ts_text": "更新于 " + snap.fetched_at.strftime("%H:%M:%S"),
        "dot_class": dot_class,
        "model_cards_html": _build_model_cards(snap),
    }
    return _json.dumps(payload, ensure_ascii=False)


def render_html(snap: UsageSnapshot, status: str = "ok", theme: str = DEFAULT_THEME) -> str:
    t = THEMES.get(theme, THEMES[DEFAULT_THEME])
    dot_class = {"ok": "dot-ok", "cached": "dot-cached", "error": "dot-err"}.get(status, "dot-ok")
    cards = _build_model_cards(snap)
    ts = snap.fetched_at.strftime("%H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8">
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html{{height:100%}}
  body{{
    font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
    background:transparent; color:{t['text']};
    padding:0; line-height:1.5; user-select:none;
    overflow:hidden; border-radius:16px;
    min-height:100%;
  }}
  .wrap{{padding:16px;min-height:100%;background:{t['bg']};border-radius:16px}}
  ::-webkit-scrollbar{{width:4px;background:transparent}}
  ::-webkit-scrollbar-track{{background:transparent}}
  ::-webkit-scrollbar-thumb{{background:transparent;border-radius:2px}}
  .grid:hover::-webkit-scrollbar-thumb{{background:{t['border']}}}
  ::-webkit-scrollbar-thumb:hover{{background:{t['accent']}}}

  .hd{{display:flex;align-items:center;gap:8px;margin-bottom:12px}}
  body.folded .hd{{margin-bottom:10px}}
  .hd-dot{{width:10px;height:10px;border-radius:3px;background:{t['accent']}}}
  .hd-t{{font-size:15px;font-weight:700;color:{t['text_bright']};letter-spacing:.3px}}
  .hb{{
    background:{t['model_bg']}; border:1px solid {t['border']};
    color:{t['text']}; font-size:14px; width:32px; height:32px;
    border-radius:8px; cursor:pointer; display:flex; align-items:center;
    justify-content:center; transition:all .15s;
  }}
  .hb:hover{{background:{t['model_hover']};border-color:{t['accent']}}}

  .cards{{display:flex;gap:10px;margin-bottom:12px}}
  .card{{flex:1;border-radius:10px;padding:12px 14px;position:relative;overflow:hidden;
    background:{t['surface']}; border:1px solid {t['border']}; box-shadow:{t['shadow']};}}
  .card-bal{{border-left:3px solid {t['accent']}}}
  .card-cos{{border-left:3px solid {t['cost_text']}}}
  .card-l{{font-size:10px;color:{t['text_dim']};margin-bottom:2px;letter-spacing:.5px;text-transform:uppercase}}
  .card-v{{font-size:22px;font-weight:800;color:{t['text_bright']}}}
  .card-s{{font-size:10px;color:{t['text_dim']};margin-top:2px}}

  .st,.grid,.ft{{}}
  body.folded .st{{display:none}}
  body.folded .grid{{display:none}}
  body.folded .ft{{display:none}}
  body.folded .cards{{margin-bottom:0}}
  body.folded .card{{padding:6px 12px}}
  body.folded .card-l{{font-size:10px;margin-bottom:0;display:inline}}
  body.folded .card-v{{font-size:16px;display:inline;margin-left:8px}}
  body.folded .card-s{{display:none}}
  body.folded .wrap{{padding-bottom:12px}}

  .st{{font-size:10px;font-weight:700;color:{t['section']};text-transform:uppercase;letter-spacing:2px;margin-bottom:10px}}

  .grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;align-items:start;max-height:420px;overflow-y:auto;padding-right:4px}}
  .mc{{
    background:{t['model_bg']};border-radius:10px;padding:14px 16px;
    border:1px solid {t['border']};transition:all .15s;
    box-shadow:{t['shadow']};
  }}
  .mc:hover{{background:{t['model_hover']}}}
  .mc:not([onclick]){{cursor:default}}
  .mh{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
  .mn{{font-size:13px;font-weight:700;color:{t['text_bright']}}}
  .mp{{font-size:13px;font-weight:700;color:{t['cost_text']}}}

  .cw{{display:flex;align-items:center;gap:8px;margin-bottom:8px}}
  .cb{{flex:1;height:5px;background:rgba(128,128,128,.15);border-radius:3px;overflow:hidden}}
  .cf{{height:100%;border-radius:3px;transition:width .3s}}
  .cl{{font-size:10px;font-weight:600;white-space:nowrap}}

  .mr{{display:flex;align-items:center;gap:8px;margin-bottom:3px}}
  .ml{{font-size:10px;color:{t['text_dim']};width:68px;flex-shrink:0}}
  .mv{{font-size:10px;color:{t['text']};width:46px;text-align:right;flex-shrink:0;font-weight:600}}
  .mb{{flex:1;height:3px;background:rgba(128,128,128,.12);border-radius:2px;overflow:hidden}}
  .mf{{height:100%;border-radius:2px;transition:width .4s}}
  .pbar{{background:{t['prompt_bar']}}}
  .cbar{{background:{t['comp_bar']}}}

  .sd{{display:none;margin-top:8px;padding:8px 0 0 12px;border-left:2px solid {t['border']}}}
  .mc.open .sd{{display:block}}
  .dr{{display:flex;justify-content:space-between;margin-bottom:3px}}
  .dl{{font-size:10px;color:{t['text_dim']}}}
  .dv{{font-size:10px;color:{t['text_dim']}}}

  .ft{{display:flex;justify-content:space-between;align-items:center;
    margin-top:16px;padding-top:12px;border-top:1px solid {t['border']};
    font-size:11px;color:{t['text_dim']}}}
  .spinner{{width:14px;height:14px;border:2px solid {t['border']};border-top-color:{t['accent']};border-radius:50%;animation:spin .6s linear infinite}}
  @keyframes spin{{to{{transform:rotate(360deg)}}}}
  .ft-d{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px}}
  .dot-ok{{background:#2da44e;box-shadow:0 0 6px rgba(45,164,78,.5)}}
  .dot-err{{background:#cf222e;box-shadow:0 0 6px rgba(207,34,46,.5)}}
  .dot-cached{{background:#d29922;box-shadow:0 0 6px rgba(210,153,34,.5)}}

  @keyframes fi{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:translateY(0)}}}}
  .mc{{animation:fi .35s ease both}}
  .mc:nth-child(1){{animation-delay:.02s}}
  .mc:nth-child(2){{animation-delay:.06s}}
  .mc:nth-child(3){{animation-delay:.10s}}
  .mc:nth-child(4){{animation-delay:.14s}}

  .page{{transition:opacity .2s,transform .2s}}
  .page-hidden{{opacity:0;transform:translateX(20px);pointer-events:none;position:absolute;visibility:hidden}}

  .sett-row{{display:flex;align-items:center;justify-content:space-between;padding:10px 0}}
  .sett-row label{{font-size:13px;color:{t['text']}}}
  .sett-row input[type=number],.sett-row input[type=password],.sett-row input[type=text]{{
    width:120px;padding:6px 8px;border-radius:6px;border:1px solid {t['border']};
    background:{t['model_bg']};color:{t['text']};font-size:13px;text-align:center;
  }}
  .sett-row input:focus{{outline:none;border-color:{t['accent']}}}
  .sett-toggle{{
    width:44px;height:24px;border-radius:12px;border:none;cursor:pointer;
    background:rgba(128,128,128,.3);transition:background .2s;position:relative;
  }}
  .sett-toggle.on{{background:{t['accent']}}}
  .sett-toggle::after{{
    content:'';position:absolute;top:2px;left:2px;width:20px;height:20px;
    border-radius:50%;background:#fff;transition:transform .2s;
  }}
  .sett-toggle.on::after{{transform:translateX(20px)}}
  .sett-btn{{
    padding:8px 18px;border-radius:8px;border:1px solid {t['border']};
    background:{t['model_bg']};color:{t['text']};font-size:13px;cursor:pointer;
    transition:all .15s;
  }}
  .sett-btn:hover{{background:{t['model_hover']};border-color:{t['accent']}}}
  .sett-btn.active{{background:{t['accent']};color:#fff;border-color:{t['accent']}}}
  .sett-back{{display:flex;align-items:center;gap:6px;font-size:14px;color:{t['accent']};cursor:pointer;margin-bottom:16px}}
  .sett-back:hover{{opacity:.8}}
  .sett-result{{font-size:12px;margin-left:10px}}
  .sett-result.ok{{color:#2da44e}}
  .sett-result.err{{color:#cf222e}}
</style></head>
<body>
  <div class="wrap">
  <!-- ── main page ── -->
  <div class="page page-main">
  <div class="hd"><div class="hd-dot"></div><span class="hd-t">DeepSeek 用量</span>
    <span style="flex:1"></span>
    <button class="hb" id="btn-fold" title="折叠" onclick="var f=document.body.classList.toggle('folded');this.textContent=f?'▸':'▾';console.log(f?'__FOLD__':'__UNFOLD__')">▾</button>
    <button class="hb" id="btn-theme" title="切换深浅色" onclick="console.log('__THEME_TOGGLE__')">{'◑' if theme == 'dark' else '◐'}</button>
    <button class="hb" id="btn-lock" title="锁定位置" onclick="var b=document.getElementById('btn-lock');if(window.__locked){{window.__locked=false;b.textContent='◌';b.title='锁定位置';b.style.opacity='0.5'}}else{{window.__locked=true;b.textContent='◉';b.title='已锁定';b.style.opacity='1'}};console.log('__LOCK_TOGGLE__')" style="opacity:0.5">◌</button>
    <button class="hb" title="设置" onclick="openSettings()">⚙</button>
  </div>

  <div class="cards">
    <div class="card card-bal">
      <div class="card-l">总余额</div>
      <div class="card-v" id="bal-val">¥{snap.total_balance:.2f}</div>
      <div class="card-s" id="bal-sub">充值 ¥{snap.topped_up_balance:.2f}</div>
    </div>
    <div class="card card-cos">
      <div class="card-l">本月费用</div>
      <div class="card-v" id="cost-val">¥{snap.total_cost:.2f}</div>
      <div class="card-s" id="cost-sub">{_fmt(snap.total_tokens)} tokens</div>
    </div>
  </div>

  <div class="st">模型用量</div>
  <div class="grid" id="models-grid">{cards}</div>

  <div class="ft">
    <span><span class="ft-d {dot_class}" id="dot"></span><span id="footer-status">更新于 {ts}</span></span>
    <span class="spinner" id="fetch-spinner" style="display:none"></span>
  </div>
  </div><!-- /page-main -->

  <!-- ── settings page ── -->
  <div class="page page-settings page-hidden">
    <div class="sett-back" onclick="closeSettings()">← 返回</div>
    <div class="sett-row"><label>刷新间隔 (秒)</label><input type="number" id="cfg-interval" min="10" max="3600" onchange="cfgChanged('refresh_interval_seconds',this.value)"></div>
    <div class="sett-row"><label>窗口透明度</label><span style="display:flex;align-items:center;gap:8px"><input type="range" id="cfg-opacity" min="0.2" max="1.0" step="0.05" oninput="document.getElementById('cfg-opacity-val').textContent=this.value;cfgChanged('window_opacity',this.value)"><span id="cfg-opacity-val" style="font-size:12px;width:32px">0.85</span></span></div>
    <div class="sett-row"><label>始终置顶</label><button class="sett-toggle" id="cfg-ontop" onclick="toggleOnTop()"></button></div>
    <div class="sett-row"><label>配色方案</label><span><button class="sett-btn" id="cfg-dark" onclick="cfgChanged('color_theme','dark')">深色</button><button class="sett-btn" id="cfg-light" style="margin-left:6px" onclick="cfgChanged('color_theme','light')">浅色</button></span></div>
    <div style="margin:12px 0;height:1px;background:{t['border']}"></div>
    <div class="sett-row"><label>User Token</label></div>
    <input type="password" id="cfg-token" placeholder="粘贴 userToken..." style="width:100%;margin-bottom:8px" onchange="cfgChanged('user_token',this.value)">
    <button class="sett-btn" onclick="testToken()">测试连接</button>
    <span class="sett-result" id="test-result"></span>
  </div><!-- /page-settings -->

  <script>
    // model cards start collapsed
    window.__config = {{
      refresh_interval_seconds: {snap.total_balance}0 || 300,
      window_opacity: 0.85,
      color_theme: '{theme}',
      always_on_top: true,
    }};
    // populate config from Python later
    function openSettings() {{
      var m = document.querySelector('.page-main');
      var s = document.querySelector('.page-settings');
      m.classList.add('page-hidden');
      s.classList.remove('page-hidden');
      console.log('__OPEN_SETTINGS__');
      setTimeout(reportHeight, 150);
    }}
    function closeSettings() {{
      var m = document.querySelector('.page-main');
      var s = document.querySelector('.page-settings');
      m.classList.remove('page-hidden');
      s.classList.add('page-hidden');
      console.log('__CLOSE_SETTINGS__');
      setTimeout(reportHeight, 150);
    }}
    function cfgChanged(key, val) {{
      console.log('__CFG__:' + key + '=' + val);
    }}
    function toggleOnTop() {{
      var b = document.getElementById('cfg-ontop');
      var on = !b.classList.contains('on');
      b.classList.toggle('on', on);
      cfgChanged('always_on_top', on ? '1' : '0');
    }}
    function testToken() {{
      var tok = document.getElementById('cfg-token').value;
      if (!tok) {{ document.getElementById('test-result').textContent = '请先输入 Token'; return; }}
      document.getElementById('test-result').textContent = '测试中...';
      document.getElementById('test-result').className = 'sett-result';
      console.log('__TEST_TOKEN__:' + tok);
    }}
    function setTestResult(ok, msg) {{
      var el = document.getElementById('test-result');
      el.textContent = msg;
      el.className = 'sett-result ' + (ok ? 'ok' : 'err');
    }}
    function setConfig(cfg) {{
      window.__config = cfg;
      document.getElementById('cfg-interval').value = cfg.refresh_interval_seconds || 300;
      document.getElementById('cfg-opacity').value = cfg.window_opacity || 0.85;
      document.getElementById('cfg-opacity-val').textContent = cfg.window_opacity || 0.85;
      document.body.style.opacity = cfg.window_opacity || 0.85;
      var ontop = cfg.always_on_top !== false;
      document.getElementById('cfg-ontop').classList.toggle('on', ontop);
      var theme = cfg.color_theme || 'dark';
      document.getElementById('cfg-dark').classList.toggle('active', theme === 'dark');
      document.getElementById('cfg-light').classList.toggle('active', theme === 'light');
      document.getElementById('cfg-token').value = cfg.user_token || '';
    }}
  </script>
  </div>
  __UPDATE_JS_PLACEHOLDER__
</body></html>""".replace("__UPDATE_JS_PLACEHOLDER__", UPDATE_JS)
