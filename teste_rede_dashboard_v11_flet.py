"""
AS TECH SOLUTIONS - Network Diagnostic Dashboard v11 - Flet Edition
Layout: gauge + 2x2 cards | info panels | log largo
Polling via thread dedicada (nao on_idle).
"""
from __future__ import annotations
import os, sys, subprocess, signal

# Aplicativos PyInstaller com --noconsole deixam stdout/stderr como None.
# O speedtest-cli antigo tenta chamar fileno() nesses objetos durante o import.
class _NullOutput:
    encoding = "utf-8"
    def write(self, _): return 0
    def flush(self): pass
    def fileno(self): raise OSError("saída de console indisponível")

if sys.stdout is None:
    sys.stdout = _NullOutput()
if sys.stderr is None:
    sys.stderr = _NullOutput()

def _ensure(name, pkg):
    try: return __import__(name)
    except ImportError:
        print(f"[INSTALL] Instalando {pkg}...")
        try:    subprocess.check_call([sys.executable,"-m","pip","install",pkg,"-q"])
        except: subprocess.check_call([sys.executable,"-m","pip","install",pkg,"-q","--break-system-packages"])
        return __import__(name)

_ensure("flet",     "flet")
_ensure("speedtest","speedtest-cli")

import asyncio, time, math, queue, threading, socket, statistics
import urllib.request
from dataclasses import dataclass
import flet as ft
import flet.canvas as fc
import speedtest as _spd

# ── Compatibilidade Flet 0.70-0.90+ ──────────────────────────────────────────
def _launch(fn):
    # Não capture TypeError gerado dentro do app: isso escondia o erro real e
    # tentava abrir uma segunda instância.
    if hasattr(ft, "run"):
        ft.run(fn)
    else:
        ft.app(target=fn)

async def _async_close(page):
    """Fecha a janela de forma assíncrona (compatível com qualquer versão)."""
    try:    await page.window.destroy(); return
    except: pass
    try:    await page.window.close();   return
    except: pass
    os.kill(os.getpid(), signal.SIGTERM)

def _close(page):
    """Dispara o fechamento via run_task para suportar coroutines."""
    try:
        page.run_task(_async_close, page)
    except Exception:
        os.kill(os.getpid(), signal.SIGTERM)

def _set_window(page, w, h, min_w, min_h):
    try:
        page.window.width=w; page.window.height=h
        page.window.min_width=min_w; page.window.min_height=min_h
    except:
        try:
            page.window_width=w; page.window_height=h
            page.window_min_width=min_w; page.window_min_height=min_h
        except: pass

def _border(w, c):
    try:    return ft.Border.all(w, c)
    except: return ft.border.all(w, c)  # type: ignore

def _border_b(w, c):
    try:    return ft.Border(bottom=ft.BorderSide(w, c))
    except: return ft.border.only(bottom=ft.BorderSide(w, c))  # type: ignore

def _pad(v=0, h=0):
    try:    return ft.Padding(left=h, right=h, top=v, bottom=v)
    except: return ft.padding.symmetric(vertical=v, horizontal=h)  # type: ignore

def _margin_l(n):
    try:    return ft.Margin(left=n, right=0, top=0, bottom=0)
    except: return ft.margin.only(left=n)  # type: ignore

def _filled(label, on_click, bg, fg):
    s = ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6))
    try:    return ft.FilledButton(label, on_click=on_click, bgcolor=bg, color=fg, style=s, height=34)
    except: return ft.ElevatedButton(label, on_click=on_click, bgcolor=bg, color=fg, style=s, height=34)  # type: ignore

def _outlined(label, on_click, bc, fg):
    s = ft.ButtonStyle(side=ft.BorderSide(1,bc), color=fg, shape=ft.RoundedRectangleBorder(radius=6))
    return ft.OutlinedButton(label, on_click=on_click, style=s, height=34)

# ── Paleta ────────────────────────────────────────────────────────────────────
BG="#080D17"; SRF="#101827"; CARD="#162235"; BRD="#26364D"
TXT="#F2F7FF"; MUT="#8EA2BE"; ACC="#38BDF8"; GRN="#34D399"
YLW="#FBBF24"; RED="#FB7185"; LOG="#A7F3D0"; LOG_BG="#070C14"

MC = {
    "ping":     {"l":"Latencia",  "i":"Ideal < 30ms",   "c":YLW,     "u":"ms",   "m":120.0,  "t":[0,10,30,60,90,120],       "ok":lambda v:v<30, "wn":lambda v:v<60},
    "jitter":   {"l":"Jitter",    "i":"Ideal < 5ms",    "c":"#b388ff","u":"ms",   "m":40.0,   "t":[0,5,10,20,30,40],         "ok":lambda v:v<5,  "wn":lambda v:v<12},
    "download": {"l":"Download",  "i":"Maior e melhor", "c":ACC,     "u":"Mbps", "m":1000.0, "t":[0,10,50,100,250,500,1000],"ok":lambda v:v>=50,"wn":lambda v:v>=20},
    "upload":   {"l":"Upload",    "i":"Maior e melhor", "c":"#ff9f43","u":"Mbps", "m":500.0,  "t":[0,10,50,100,250,500],     "ok":lambda v:v>=10,"wn":lambda v:v>=5},
}
KEYS = ["ping","jitter","download","upload"]
# Linhas 2x2: [linha0, linha1]
ROWS = [["ping","jitter"],["download","upload"]]

EST = {
    "Automatico":[],"Bahia-BA":["Bahia","Salvador","BA"],
    "Sao Paulo-SP":["Sao Paulo","Campinas","SP"],"Rio de Janeiro-RJ":["Rio de Janeiro","RJ"],
    "Minas Gerais-MG":["Minas Gerais","Belo Horizonte","MG"],"Parana-PR":["Parana","Curitiba","PR"],
    "Santa Catarina-SC":["Santa Catarina","Florianopolis","SC"],
    "Rio Grande do Sul-RS":["Porto Alegre","RS"],"Pernambuco-PE":["Pernambuco","Recife","PE"],
    "Ceara-CE":["Ceara","Fortaleza","CE"],"Goias-GO":["Goias","Goiania","GO"],
    "Distrito Federal-DF":["Distrito Federal","Brasilia","DF"],
}
ELST = list(EST.keys())

# ── Speedtest ────────────────────────────────────────────────────────────────
def _get_st():
    try:    return _spd.Speedtest(secure=True)
    except: return _spd.Speedtest()

def _friendly(e):
    s=str(e); return "HTTP 403 - tente outro servidor ou verifique o firewall." if "403" in s or "Forbidden" in s else s

def _cf_request(path, data=None, timeout=15):
    req = urllib.request.Request(
        f"https://speed.cloudflare.com{path}",
        data=data,
        headers={"User-Agent": "AS-Tech-Network-Diagnostic/12"},
        method="POST" if data is not None else "GET",
    )
    return urllib.request.urlopen(req, timeout=timeout)

def _cloudflare_metrics():
    """Teste alternativo enxuto usando a rede global da Cloudflare."""
    latency = []
    for _ in range(6):
        start = time.perf_counter()
        with _cf_request("/__down?bytes=0", timeout=5) as response:
            response.read()
        latency.append((time.perf_counter() - start) * 1000)
    ping = statistics.median(latency)
    jitter = statistics.fmean(
        abs(latency[i] - latency[i - 1]) for i in range(1, len(latency))
    )

    download_bytes = 12_000_000
    start = time.perf_counter()
    with _cf_request(f"/__down?bytes={download_bytes}", timeout=30) as response:
        payload = response.read()
    elapsed = max(time.perf_counter() - start, 0.001)
    download = len(payload) * 8 / elapsed / 1_000_000

    upload_payload = b"0" * 4_000_000
    start = time.perf_counter()
    with _cf_request("/__up", data=upload_payload, timeout=30) as response:
        response.read()
    elapsed = max(time.perf_counter() - start, 0.001)
    upload = len(upload_payload) * 8 / elapsed / 1_000_000
    return ping, jitter, download, upload

def _match(srv, terms):
    if not terms: return True
    txt=" ".join(str(srv.get(k,"")).lower() for k in ("name","sponsor","host","country"))
    return any(t.lower() in txt for t in terms)

def _pick(st, est):
    terms=EST.get(est,[])
    if terms:
        try:
            st.get_servers([])
            cands=[s for lst in getattr(st,"servers",{}).values() for s in lst if _match(s,terms)]
            if cands:
                ids=[int(s["id"]) for s in cands if str(s.get("id","")).isdigit()]
                if ids: st.get_servers(ids); return st.get_best_server()
        except: pass
    return st.get_best_server()

def _tcp_jitter(host, fallback=0.0, samples=7):
    """Mede variação real de latência até o servidor (handshake TCP)."""
    raw = (host or "").split("/")[0]
    if not raw:
        return max(float(fallback) * 0.05, 0.1)
    name, sep, port = raw.rpartition(":")
    if not sep:
        name, port = raw, "80"
    times = []
    for _ in range(samples):
        try:
            start = time.perf_counter()
            with socket.create_connection((name, int(port)), timeout=0.8):
                times.append((time.perf_counter() - start) * 1000)
        except (OSError, ValueError):
            continue
    if len(times) < 3:
        return max(float(fallback) * 0.05, 0.1)
    diffs = [abs(times[i] - times[i - 1]) for i in range(1, len(times))]
    return statistics.fmean(diffs)

def _cls(p,j,d,u):
    if p<25 and j<5 and d>=50 and u>=10: return "Excelente - ideal para jogos e chamadas 4K.","excelente"
    if p<60 and j<12 and d>=20:          return "Estavel, pode oscilar em horarios de pico.","boa"
    return "Instabilidade detectada. Reinicie o modem e fique proximo ao roteador.","alerta"

def _pf(k,v):
    if k=="ping":     return max(0,min(100,100-v/120*100))
    if k=="jitter":   return max(0,min(100,100-v/40*100))
    if k=="download": return max(0,min(100,v/100*100))
    if k=="upload":   return max(0,min(100,v/50*100))
    return 0.0

@dataclass
class Res:
    isp:str; ip:str; loc:str; sn:str; sh:str; sc:str; scn:str
    est:str; ping:float; jit:float; dl:float; ul:float; diag:str; niv:str

# ── Gauge Canvas ──────────────────────────────────────────────────────────────
class Gauge(fc.Canvas):
    # A altura anterior cortava a base do arco, os rótulos e a unidade.
    W,H,SR,ER = 330,225,math.radians(215),math.radians(-250)

    def __init__(self):
        super().__init__(width=self.W, height=self.H)
        self.cx=self.W/2; self.cy=self.H*0.64; self.R=self.W*0.37
        self._k="download"; self._v=0.0; self._p=0.0; self._m="idle"; self._lp=0.0
        self._rebuild()

    def set(self, k, v=None):
        self._k=k; self._v=v or 0.0
        self._m="value" if v is not None else "idle"
        self._p=min(1.0,self._v/MC[k]["m"]) if v is not None else 0.0
        self._rebuild()

    def load(self, p): self._lp=p; self._p=p/100; self._m="loading"; self._rebuild()
    def reset(self):   self._v=0.0; self._p=0.0; self._m="idle"; self._rebuild()

    def _pol(self,r,a): return self.cx+r*math.cos(a), self.cy-r*math.sin(a)
    def _arc(self,r,sr,er,n=70): return [self._pol(r,sr+(er-sr)*i/n) for i in range(n+1)]

    def _rebuild(self):
        c=MC[self._k]; col=c["c"]; cx,cy,R=self.cx,self.cy,self.R
        sr=self.SR; er=sr+self.ER; sh=[]

        # trilho
        rail=self._arc(R,sr,er)
        for i in range(1,len(rail)):
            sh.append(fc.Line(rail[i-1][0],rail[i-1][1],rail[i][0],rail[i][1],
                paint=ft.Paint(color="#1e2d45",stroke_width=20,style=ft.PaintingStyle.STROKE)))

        # arco preenchido
        if self._p>0.002:
            fe=sr+self.ER*self._p; fa=self._arc(R,sr,fe,n=max(4,int(70*self._p)))
            for i in range(1,len(fa)):
                sh.append(fc.Line(fa[i-1][0],fa[i-1][1],fa[i][0],fa[i][1],
                    paint=ft.Paint(color=col,stroke_width=20,style=ft.PaintingStyle.STROKE)))
            for i in range(1,len(fa)):
                sh.append(fc.Line(fa[i-1][0],fa[i-1][1],fa[i][0],fa[i][1],
                    paint=ft.Paint(color="white",stroke_width=4,style=ft.PaintingStyle.STROKE,
                                   stroke_cap=ft.StrokeCap.ROUND)))

        # ticks
        for t in c["t"]:
            tp=min(1.0,t/c["m"]); ang=sr+self.ER*tp
            x0,y0=self._pol(R-11,ang); x1,y1=self._pol(R+3,ang); lx,ly=self._pol(R-27,ang)
            sh.append(fc.Line(x0,y0,x1,y1,
                paint=ft.Paint(color="#4a5568",stroke_width=1,style=ft.PaintingStyle.STROKE)))
            sh.append(fc.Text(lx-8,ly-7,str(t),style=ft.TextStyle(size=8,color="#6b7a96")))

        # ponteiro
        ang=sr+self.ER*self._p
        tx,ty=self._pol(R-38,ang)
        blx,bly=self._pol(11,ang+math.radians(92))
        brx,bry=self._pol(11,ang-math.radians(92))
        sh.append(fc.Path([fc.Path.MoveTo(blx,bly),fc.Path.LineTo(tx,ty),
                           fc.Path.LineTo(brx,bry),fc.Path.Close()],
            paint=ft.Paint(color="#d0ddf0",style=ft.PaintingStyle.FILL)))
        sh.append(fc.Circle(cx,cy,7,paint=ft.Paint(color="#d0ddf0",style=ft.PaintingStyle.FILL)))

        # valor central
        if self._m=="idle":
            sh.append(fc.Text(cx-11,cy+17,"--",style=ft.TextStyle(size=24,color="#7d8ea8",weight=ft.FontWeight.BOLD)))
            sh.append(fc.Text(cx-13,cy+46,c["u"],style=ft.TextStyle(size=11,color="#4a5568")))
        elif self._m=="loading":
            sh.append(fc.Text(cx-19,cy+17,f"{int(self._lp)}%",style=ft.TextStyle(size=24,color=TXT,weight=ft.FontWeight.BOLD)))
            sh.append(fc.Text(cx-22,cy+46,"MEDINDO",style=ft.TextStyle(size=10,color=col,weight=ft.FontWeight.BOLD)))
        else:
            v=self._v; vt=f"{v:.1f}" if v>=10 else f"{v:.2f}"
            vc=GRN if c["ok"](v) else (YLW if c["wn"](v) else RED)
            sh.append(fc.Text(cx-len(vt)*7,cy+15,vt,style=ft.TextStyle(size=24,color=vc,weight=ft.FontWeight.BOLD)))
            sh.append(fc.Text(cx-14,cy+44,c["u"],style=ft.TextStyle(size=11,color=col,weight=ft.FontWeight.BOLD)))

        lbl=c["l"].upper()
        sh.append(fc.Text(cx-len(lbl)*4,6,lbl,style=ft.TextStyle(size=11,color="#c8d8f0",weight=ft.FontWeight.BOLD)))

        self.shapes=sh
        try:
            if self.page: self.update()
        except: pass

# ── App ───────────────────────────────────────────────────────────────────────
def main(page: ft.Page):
    page.title   = "AS Tech • Diagnóstico de conexão"
    page.bgcolor = BG
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(
        color_scheme_seed=ACC,
        font_family="Segoe UI",
        visual_density=ft.VisualDensity.COMFORTABLE,
    )
    page.padding = 0; page.spacing = 0
    _set_window(page, w=1120, h=760, min_w=920, min_h=640)

    q: queue.Queue = queue.Queue()
    running  = [False]
    stop_poll= [False]
    vals={}; act=["download"]; logs=[]
    gauge=Gauge()

    # ── Widgets dinâmicos ─────────────────────────────────────────────────────
    t_sts = ft.Text("●  Pronto",                  color=GRN, size=12, weight=ft.FontWeight.BOLD)
    t_org = ft.Text("Origem ainda não identificada", color=TXT, size=11)
    t_dst = ft.Text("Servidor ainda não selecionado", color=TXT, size=11)
    t_dg  = ft.Text("Inicie o teste para obter o diagnóstico.",
                     color=TXT, size=12, weight=ft.FontWeight.BOLD)
    t_hs  = ft.Text("Nenhum teste executado.",   color=MUT, size=11)
    t_lg  = ft.Text("Sistema pronto.",           color=LOG, size=12, font_family="Consolas",
                     selectable=True)
    t_gt  = ft.Text("Download  -  Maior e melhor",
                     color=MUT, size=10, text_align=ft.TextAlign.CENTER)
    t_clock = ft.Text("--:--:--", color=ACC, size=24, weight=ft.FontWeight.BOLD)
    t_date = ft.Text("", color="#A78BFA", size=10, weight=ft.FontWeight.W_600)
    clock_pulse = ft.Container(
        width=8, height=8, bgcolor=GRN, border_radius=8,
        animate_scale=ft.Animation(420, ft.AnimationCurve.EASE_OUT_BACK),
        animate_opacity=ft.Animation(420, ft.AnimationCurve.EASE_IN_OUT),
    )

    cmb = ft.Dropdown(
        options=[ft.dropdown.Option(e) for e in ELST],
        value=ELST[0], width=220,
        bgcolor=CARD, color=TXT, border_color=BRD,
        focused_border_color=ACC, text_size=11,
    )

    # refs por métrica
    vr={}; pr={}; pb={}; cc={}

    def log(txt):
        logs.append(f"[{time.strftime('%H:%M:%S')}] {txt}")
        if len(logs)>60: logs[:]=logs[-40:]
        t_lg.value="\n".join(logs[-14:])

    def sel(k):
        act[0]=k; c=MC[k]
        t_gt.value=f"{c['l']}  -  {c['i']}"
        gauge.set(k, vals.get(k))
        for kk,cont in cc.items():
            cont.border=_border(2, MC[kk]["c"] if kk==k else BRD)
        page.update()

    # ── Mini cards 2x2 ───────────────────────────────────────────────────────
    def mk_card(k):
        c=MC[k]
        vt=ft.Text("--",   color=TXT, size=22, weight=ft.FontWeight.BOLD)
        pt=ft.Text("",     color=MUT, size=10)
        pb_=ft.ProgressBar(value=0, color=c["c"], bgcolor=BRD, height=4)
        vr[k]=vt; pr[k]=pt; pb[k]=pb_
        cont=ft.Container(
            content=ft.Column([
                ft.Text(f"[ {c['l'].upper()} ]", color=c["c"], size=10, weight=ft.FontWeight.BOLD),
                ft.Row([vt, ft.Text(c["u"], color=c["c"], size=11)],
                       spacing=3, vertical_alignment=ft.CrossAxisAlignment.END),
                pb_, pt,
            ], spacing=3, tight=True),
            bgcolor=CARD, border=_border(1,BRD),
            border_radius=7, padding=10, expand=True,
            on_click=lambda e, kk=k: sel(kk),
        )
        cc[k]=cont; return cont

    # Duas linhas: [ping | jitter] e [download | upload]
    cards_grid=ft.Column([
        ft.Row([mk_card("ping"),   mk_card("jitter")],   spacing=6, expand=True),
        ft.Row([mk_card("download"),mk_card("upload")],  spacing=6, expand=True),
    ], spacing=6, expand=True)

    # ── Botões ────────────────────────────────────────────────────────────────
    bs = _filled("▶  Iniciar teste", None, ACC, BG)
    bc = _outlined("Limpar",         None, BRD, TXT)
    bx = _outlined("Fechar",      None, RED, RED)

    def do_start(_=None):
        if running[0]: return
        running[0]=True
        bs.disabled=True; bc.disabled=True; cmb.disabled=True
        t_sts.value="●  Iniciando..."; t_sts.color=YLW
        t_dg.value="Diagnóstico em execução..."; t_dg.color=TXT
        gauge.reset()
        for k in KEYS:
            vr[k].value="-"; vr[k].color=MUT
            pr[k].value="medindo..."; pb[k].value=0
        log("Teste iniciado.")
        page.update()
        threading.Thread(target=worker, daemon=True).start()

    def do_clear(_=None):
        if running[0]: return
        vals.clear()
        t_sts.value="●  Pronto"; t_sts.color=GRN
        t_org.value="Origem ainda não identificada"
        t_dst.value="Servidor ainda não selecionado"
        t_dg.value="Inicie o teste para obter o diagnóstico."; t_dg.color=TXT
        t_hs.value="Nenhum teste executado."
        for k in KEYS:
            vr[k].value="--"; vr[k].color=TXT
            pr[k].value=""; pb[k].value=0
        gauge.reset()
        logs.clear(); t_lg.value="Sistema pronto."
        sel("download")
        page.update()

    def do_close(_=None):
        stop_poll[0]=True
        _close(page)

    bs.on_click=do_start
    bc.on_click=do_clear
    bx.on_click=do_close

    # ── Painel helper ─────────────────────────────────────────────────────────
    def panel(title, content, height=None):
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(title.upper(), color=ACC, size=9, weight=ft.FontWeight.BOLD),
                    ft.Container(content=ft.Divider(color=BRD,height=1),
                                 expand=True, margin=_margin_l(6)),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                content,
            ], spacing=5, tight=True),
            bgcolor=SRF, border_radius=7, border=_border(1,BRD),
            padding=10, height=height,
        )

    # ── Header ────────────────────────────────────────────────────────────────
    clock_card=ft.Container(
        content=ft.Row([
            ft.Column([
                clock_pulse,
                ft.Container(width=4, height=28, bgcolor="#A78BFA", border_radius=4),
            ], spacing=4, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Column([
                t_clock,
                t_date,
            ], spacing=-3, tight=True,
               horizontal_alignment=ft.CrossAxisAlignment.END),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor="#111D31", border_radius=14, padding=_pad(8,14),
        border=_border(1, "#31415D"),
        animate_scale=ft.Animation(420, ft.AnimationCurve.EASE_OUT_BACK),
    )

    hdr=ft.Container(
        content=ft.Row([
            ft.Row([
                ft.Container(
                    content=ft.Text("⚡", color=ACC, size=28,
                                    weight=ft.FontWeight.BOLD),
                    width=48, height=48, bgcolor="#102840",
                    border_radius=14, alignment=ft.Alignment.CENTER,
                    border=_border(1, "#1E5675"),
                ),
                ft.Column([
                    ft.Text("AS TECH SOLUTIONS", color=TXT, size=22,
                            weight=ft.FontWeight.BOLD),
                    ft.Text("CENTRAL DE DIAGNÓSTICO DE REDE", color=ACC, size=10,
                            weight=ft.FontWeight.W_600),
                ], spacing=0, tight=True),
            ], spacing=14),
            ft.Container(expand=True),
            clock_card,
        ], alignment=ft.MainAxisAlignment.START,
           vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor="#0B1220", padding=_pad(16,22),
        border=_border_b(1, BRD))

    # ── Barra de controles ────────────────────────────────────────────────────
    ctrl=ft.Container(
        content=ft.Row([
            ft.Text("REGIÃO DO SERVIDOR", color=MUT, size=9, weight=ft.FontWeight.BOLD),
            cmb,
            ft.Container(expand=True),
            t_sts,
            ft.Container(expand=True),
            bs, bc, bx,
        ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=SRF, padding=_pad(9,16),
        border=_border_b(1,BRD))

    # ── Coluna esquerda: gauge + grid 2x2 ────────────────────────────────────
    left=ft.Column([
        ft.Container(
            content=ft.Column([t_gt, gauge],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            bgcolor=SRF, border_radius=14, border=_border(1,BRD), padding=12),
        ft.Container(height=6),
        ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("METRICAS - clique para alternar",
                            color=ACC, size=9, weight=ft.FontWeight.BOLD),
                    ft.Container(content=ft.Divider(color=BRD,height=1),
                                 expand=True, margin=_margin_l(6)),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                cards_grid,
            ], spacing=6, tight=True,
               horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            bgcolor=SRF, border_radius=14, border=_border(1,BRD),
            padding=10, expand=True),
    ], spacing=0, width=370, expand=False)

    # ── Coluna direita: painéis + log largo ──────────────────────────────────
    right=ft.Column([
        panel("Servidores",
              ft.Column([t_org, t_dst], spacing=4, tight=True), height=82),
        ft.Container(height=5),
        panel("Diagnostico", t_dg, height=68),
        ft.Container(height=5),
        panel("Historico",   t_hs, height=78),
        ft.Container(height=5),
        # Log: ocupa todo o espaço restante, texto maior
        ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("LOG DO SISTEMA", color=ACC, size=9, weight=ft.FontWeight.BOLD),
                    ft.Container(content=ft.Divider(color=BRD,height=1),
                                 expand=True, margin=_margin_l(6)),
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.Container(
                    content=t_lg,
                    expand=True,
                    bgcolor=LOG_BG, border_radius=5, padding=10,
                    alignment=ft.Alignment.TOP_LEFT,
                ),
            ], spacing=6, tight=True,
               horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            bgcolor=SRF, border_radius=7, border=_border(1,BRD),
            padding=10, expand=True,
            alignment=ft.Alignment.TOP_LEFT),
    ], spacing=0, expand=True)

    body=ft.Row([
        left,
        ft.Container(width=10),
        right,
    ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START)

    page.add(
        hdr, ctrl,
        ft.Container(content=body, expand=True, padding=_pad(10,12)),
    )
    sel("download")
    page.update()

    # ── Thread de polling (substitui on_idle — mais confiável) ───────────────
    async def poll_loop():
        while not stop_poll[0]:
            try:
                changed=False
                while True:
                    tp,pl=q.get_nowait(); changed=True
                    if tp=="sts":
                        t_sts.value=f"●  {pl}"; t_sts.color=YLW
                        log(pl)
                    elif tp=="org":
                        t_org.value=pl
                    elif tp=="dst":
                        t_dst.value=pl
                    elif tp=="gl":
                        k,p=pl
                        if act[0]==k: gauge._k=k; gauge.load(p)
                    elif tp=="mt":
                        k,v,pf=pl; vals[k]=v; c=MC[k]
                        vt=f"{v:.1f}" if v>=10 else f"{v:.2f}"
                        vc=GRN if c["ok"](v) else (YLW if c["wn"](v) else RED)
                        vr[k].value=vt; vr[k].color=vc
                        pr[k].value=f"{int(pf)}%"; pb[k].value=pf/100
                        if act[0]==k: gauge.set(k,v)
                        log(f"{c['l']}: {vt} {c['u']}")
                    elif tp=="fin":
                        _finish(pl); changed=True
                    elif tp=="err":
                        _error(pl); changed=True
            except queue.Empty:
                pass
            if changed:
                try: page.update()
                except: pass
            await asyncio.sleep(0.12)

    def _finish(r):
        running[0]=False
        bs.disabled=False; bc.disabled=False; cmb.disabled=False
        ic="[OK]" if r.niv=="excelente" else ("[~]" if r.niv=="boa" else "[!]")
        t_sts.value="●  Concluído"; t_sts.color=GRN
        t_dg.value=f"{ic}  {r.diag}"
        t_dg.color=GRN if r.niv=="excelente" else (YLW if r.niv=="boa" else RED)
        t_hs.value=(
            f"Ultimo: {time.strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"{r.sn} - {r.sc}/{r.scn}\n"
            f"Ping: {r.ping:.1f}ms  |  Jitter: {r.jit:.1f}ms\n"
            f"Download: {r.dl:.1f} Mbps  |  Upload: {r.ul:.1f} Mbps")
        log("Diagnóstico finalizado.")
        if act[0] in vals: gauge.set(act[0], vals[act[0]])

    def _error(m):
        running[0]=False
        bs.disabled=False; bc.disabled=False; cmb.disabled=False
        t_sts.value="●  Erro"; t_sts.color=RED
        t_dg.value=f"ERRO: {m}"; t_dg.color=RED
        log(f"ERRO: {m}")

    page.run_task(poll_loop)

    async def clock_loop():
        days = ("SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM")
        months = ("JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
                  "JUL", "AGO", "SET", "OUT", "NOV", "DEZ")
        while not stop_poll[0]:
            now = time.localtime()
            t_clock.value = time.strftime("%H:%M:%S", now)
            t_date.value = (
                f"{days[now.tm_wday]}  •  {now.tm_mday:02d} "
                f"{months[now.tm_mon - 1]} {now.tm_year}"
            )
            # Pulso de um segundo: o ponto acende e o cartão "respira".
            tick = now.tm_sec % 2 == 0
            clock_pulse.scale = 1.65 if tick else 0.75
            clock_pulse.opacity = 1.0 if tick else 0.45
            clock_pulse.bgcolor = GRN if tick else ACC
            clock_card.scale = 1.012 if tick else 1.0
            try:
                page.update()
            except Exception:
                break
            await asyncio.sleep(1)

    page.run_task(clock_loop)

    # ── Worker do speedtest ───────────────────────────────────────────────────
    def worker():
        est=cmb.value or ELST[0]
        try:
            q.put(("sts","Conectando ao speedtest..."))
            st=_get_st(); cli=st.config.get("client",{}) if hasattr(st,"config") else {}
            isp=str(cli.get("isp") or "Provedor nao identificado")
            ip=str(cli.get("ip")  or "IP desconhecido")
            loc=", ".join(x for x in [str(cli.get("city","")).strip(),
                                       str(cli.get("country","")).strip()] if x) or "?"
            q.put(("org",f"Origem: {isp}  |  {ip}  |  {loc}"))
            q.put(("sts",f"Servidor: {est}")); _anim("ping",0.9)
            srv=_pick(st,est); ping=float(srv.get("latency",0.0))
            sn=str(srv.get("sponsor") or "Servidor")
            sc=str(srv.get("name")    or "")
            scn=str(srv.get("country")or "")
            sh=str(srv.get("host")    or "")
            jit=_tcp_jitter(sh, ping)
            q.put(("dst",f"Destino: {sn}  |  {sc}/{scn}  |  {sh}"))
            q.put(("mt",("ping",ping,_pf("ping",ping))))
            q.put(("sts","Calculando jitter...")); _anim("jitter",0.8)
            q.put(("mt",("jitter",jit,_pf("jitter",jit))))
            q.put(("sts","Medindo download...")); _anim("download",1.1)
            dl=float(st.download())/1_000_000
            q.put(("mt",("download",dl,_pf("download",dl))))
            q.put(("sts","Medindo upload...")); _anim("upload",1.1)
            ul=float(st.upload())/1_000_000
            q.put(("mt",("upload",ul,_pf("upload",ul))))
            diag,niv=_cls(ping,jit,dl,ul)
            q.put(("fin",Res(isp,ip,loc,sn,sh,sc,scn,est,ping,jit,dl,ul,diag,niv)))
        except Exception as e:
            q.put(("sts","Speedtest indisponível. Alternando para Cloudflare..."))
            try:
                q.put(("dst","Destino: Cloudflare  |  Edge mais próximo  |  Automático"))
                q.put(("sts","Cloudflare: medindo latência e jitter..."))
                ping,jit,dl,ul=_cloudflare_metrics()
                q.put(("mt",("ping",ping,_pf("ping",ping))))
                q.put(("mt",("jitter",jit,_pf("jitter",jit))))
                q.put(("sts","Cloudflare: download concluído."))
                q.put(("mt",("download",dl,_pf("download",dl))))
                q.put(("sts","Cloudflare: upload concluído."))
                q.put(("mt",("upload",ul,_pf("upload",ul))))
                diag,niv=_cls(ping,jit,dl,ul)
                q.put(("fin",Res("Provedor local","IP local","Brasil",
                    "Cloudflare","speed.cloudflare.com","Edge","Global",
                    "Cloudflare",ping,jit,dl,ul,diag,niv)))
            except Exception as cf_error:
                q.put(("err",
                    f"Speedtest: {_friendly(e)} | Cloudflare: {_friendly(cf_error)}"))

    def _anim(k, s):
        n=40
        for i in range(n+1):
            if not running[0]: break
            q.put(("gl",(k,i*100/n))); time.sleep(s/n)

if __name__=="__main__":
    _launch(main)
