from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime, timezone
import aiohttp, asyncio, json, math, time
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]; STATIC=ROOT/'static'; CACHE=ROOT/'cache'; CACHE.mkdir(exist_ok=True)
app=FastAPI(title='Understat Value Predictor V6'); app.mount('/static',StaticFiles(directory=str(STATIC)),name='static')
LEAGUES=['EPL','La_liga','Bundesliga','Serie_A','Ligue_1','RFPL']; TTL=900

def f(x,d=0.0):
    try:return float(x)
    except:return d
def pois(k,l): return math.exp(-l)*l**k/math.factorial(k)
def fair(p): return round(1/p,2) if p>0 else None
def ev(p,o): return round((p*o-1)*100,1) if o and o>1 else None
def kelly25(p,o):
    if not o or o<=1:return None
    b=o-1; q=1-p; full=max(0,(b*p-q)/b); return round(full*25,1)
def cache_path(kind,league,season): return CACHE/f'{kind}_{league}_{season}.json'
def cache_get(p):
    if p.exists() and time.time()-p.stat().st_mtime<TTL:
        try:return json.loads(p.read_text(encoding='utf8'))
        except:pass
    return None
def cache_put(p,data): p.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')

async def ucall(method,*args):
    # Understat's old Python package pins aiohttp 3.8.3. Query the same public
    # endpoints directly so this app can use the current aiohttp release.
    timeout=aiohttp.ClientTimeout(total=25)
    headers={'User-Agent':'Mozilla/5.0 (compatible; League5Edge/6.0)'}
    league, season = args[0], str(args[1])
    async with aiohttp.ClientSession(timeout=timeout,headers=headers) as session:
        if method == 'get_league_table':
            url=f'https://understat.com/league/{league}/{season}'
            async with session.get(url) as resp:
                resp.raise_for_status()
                html=await resp.text()
            soup=BeautifulSoup(html,'html.parser')
            script=next((x.string or x.get_text() for x in soup.find_all('script') if 'teamsData' in (x.string or x.get_text())), '')
            import re
            m=re.search(r"teamsData\s*=\s*JSON\.parse\('([^']+)'\)",script)
            if not m: raise RuntimeError('Could not parse Understat league table')
            raw=m.group(1).encode('utf-8').decode('unicode_escape')
            import json as _json
            teams=_json.loads(raw)
            headers=['Team','M','W','D','L','G','GA','PTS','xG','xGA','NPxG','NPxGA','xPTS']
            rows=[]
            for team in teams.values():
                h=team.get('history',[])
                rows.append([team.get('title',''),len(h),sum(1 for x in h if x.get('h_a')=='h' and x.get('result')=='w' or x.get('h_a')=='a' and x.get('result')=='l'),sum(1 for x in h if x.get('result')=='d'),sum(1 for x in h if x.get('result')=='l' and x.get('h_a')=='h' or x.get('result')=='w' and x.get('h_a')=='a'),sum(int(x.get('scored',0) or 0) for x in h),sum(int(x.get('missed',0) or 0) for x in h),sum(int(x.get('pts',0) or 0) for x in h),sum(float(x.get('xG',0) or 0) for x in h),sum(float(x.get('xGA',0) or 0) for x in h),sum(float(x.get('npxG',0) or 0) for x in h),sum(float(x.get('npxGA',0) or 0) for x in h),sum(float(x.get('xpts',0) or 0) for x in h)])
            rows.sort(key=lambda r:r[7], reverse=True)
            return [headers,*rows]
        if method == 'get_league_fixtures':
            url=f'https://understat.com/league/{league}/{season}'
            async with session.get(url) as resp:
                resp.raise_for_status()
                html=await resp.text()
            soup=BeautifulSoup(html,'html.parser')
            script=next((x.string or x.get_text() for x in soup.find_all('script') if 'datesData' in (x.string or x.get_text())), '')
            import re, json as _json
            m=re.search(r"datesData\s*=\s*JSON\.parse\('([^']+)'\)",script)
            if not m: return []
            raw=m.group(1).encode('utf-8').decode('unicode_escape')
            return _json.loads(raw)
        raise ValueError(f'Unsupported Understat method: {method}')

async def league_bundle(league,season,force=False):
    if league not in LEAGUES: raise HTTPException(400,'Nepodržana liga')
    p=cache_path('bundle',league,season)
    if not force:
        c=cache_get(p)
        if c:return c
    try:
        table,fixtures=await asyncio.gather(ucall('get_league_table',league,season,True),ucall('get_league_fixtures',league,season))
        headers=table[0]; rows=[]
        for r in table[1:]:
            d=dict(zip(headers,r)); m=max(1,int(d.get('M',0)))
            rows.append({**d,'xG90':round(f(d.get('xG'))/m,2),'xGA90':round(f(d.get('xGA'))/m,2),'npxG90':round(f(d.get('NPxG'))/m,2),'npxGA90':round(f(d.get('NPxGA'))/m,2),'xGD90':round((f(d.get('xG'))-f(d.get('xGA')))/m,2),'ptsGap':round(f(d.get('PTS'))-f(d.get('xPTS')),2),'finishGap':round(f(d.get('G'))-f(d.get('xG')),2),'defGap':round(f(d.get('xGA'))-f(d.get('GA')),2)})
        fx=[]
        for x in fixtures:
            h=x.get('h',{}); a=x.get('a',{})
            fx.append({'id':str(x.get('id')),'datetime':x.get('datetime'),'home':h.get('title'),'away':a.get('title')})
        data={'league':league,'season':season,'updated':datetime.now(timezone.utc).isoformat(),'teams':rows,'fixtures':fx}
        cache_put(p,data); return data
    except Exception as e:
        if p.exists():
            try:
                data=json.loads(p.read_text(encoding='utf8')); data['stale']=True; data['warning']=f'Understat trenutno nije dostupan; zadnji cache. {type(e).__name__}'; return data
            except:pass
        raise HTTPException(502,f'Understat nije dostupan: {type(e).__name__}: {e}')

class Analyze(BaseModel):
    league:str='EPL'; season:int=2026; home:str; away:str
    home_odds:float|None=None; draw_odds:float|None=None; away_odds:float|None=None; over25_odds:float|None=None; under25_odds:float|None=None; over35_odds:float|None=None; under35_odds:float|None=None; btts_odds:float|None=None; btts_no_odds:float|None=None
class FixtureOdds(BaseModel):
    id:str; home:float|None=None; draw:float|None=None; away:float|None=None; over25:float|None=None; under25:float|None=None; over35:float|None=None; under35:float|None=None; btts:float|None=None; btts_no:float|None=None
class Scan(BaseModel):
    league:str='EPL'; season:int=2026; limit:int=20; odds:list[FixtureOdds]=[]

def rating(team,teams):
    if not teams:return 50
    def pct(key,val,reverse=False):
        arr=sorted(f(t.get(key)) for t in teams); rank=sum(x<=val for x in arr)/len(arr); return (1-rank if reverse else rank)*100
    s=.45*pct('xGD90',f(team['xGD90']))+.20*pct('xG90',f(team['xG90']))+.20*pct('xGA90',f(team['xGA90']),True)+.15*pct('NPxGD',f(team.get('NPxGD')))
    return round(max(0,min(100,s)))

def league_means(teams):
    n=max(1,len(teams))
    return {
        'xg':sum(f(t.get('xG90')) for t in teams)/n,
        'xga':sum(f(t.get('xGA90')) for t in teams)/n,
        'npxg':sum(f(t.get('npxG90')) for t in teams)/n,
        'npxga':sum(f(t.get('npxGA90')) for t in teams)/n,
    }

def shrink(value, mean, matches, prior_matches=8):
    # Early-season Bayesian-style shrinkage: 5 matches should not be treated like 30.
    w=max(0,min(1,matches/(matches+prior_matches)))
    return w*value+(1-w)*mean

def engine(home,away,teams):
    lm=league_means(teams); hm=max(1,int(f(home.get('M'),1))); am=max(1,int(f(away.get('M'),1)))
    # V5 core: shrink volatile early-season rates toward league means.
    h_att=shrink(f(home['xG90']),lm['xg'],hm); h_def=shrink(f(home['xGA90']),lm['xga'],hm)
    a_att=shrink(f(away['xG90']),lm['xg'],am); a_def=shrink(f(away['xGA90']),lm['xga'],am)
    h_npx=shrink(f(home['npxG90']),lm['npxg'],hm); a_npx=shrink(f(away['npxG90']),lm['npxg'],am)
    # Attack/opponent defence blend + non-penalty quality. Home advantage is explicit.
    raw_h=.48*h_att+.17*h_npx+.35*a_def
    raw_a=.48*a_att+.17*a_npx+.35*h_def
    # Regression adjustment is deliberately capped: finishing/points gaps are signals, not destiny.
    h_reg=max(-.08,min(.08,(-f(home['finishGap'])/max(4,hm*2))*0.035 + (-f(home['ptsGap'])/max(5,hm*2))*0.025))
    a_reg=max(-.08,min(.08,(-f(away['finishGap'])/max(4,am*2))*0.035 + (-f(away['ptsGap'])/max(5,am*2))*0.025))
    lh=max(.2,min(3.8,raw_h*1.10*(1+h_reg)))
    la=max(.2,min(3.8,raw_a*.91*(1+a_reg)))
    probs={(i,j):pois(i,lh)*pois(j,la) for i in range(10) for j in range(10)}; z=sum(probs.values()); probs={k:v/z for k,v in probs.items()}
    ph=sum(v for (i,j),v in probs.items() if i>j); pd=sum(v for (i,j),v in probs.items() if i==j); pa=1-ph-pd
    o15=sum(v for (i,j),v in probs.items() if i+j>=2); o25=sum(v for (i,j),v in probs.items() if i+j>=3); o35=sum(v for (i,j),v in probs.items() if i+j>=4); btts=sum(v for (i,j),v in probs.items() if i>0 and j>0)
    scores=sorted(probs.items(),key=lambda x:x[1],reverse=True)[:5]
    def reg(t):
        score=f(t['ptsGap'])*.7+f(t['finishGap'])*.35+f(t['defGap'])*.25
        return 'OVERPERFORMING' if score>2 else ('UNDERPERFORMING' if score<-2 else 'NORMAL')
    reliability=round(min(100,35+min(hm,am)*2.5))
    return {'lh':lh,'la':la,'p':{'HOME':ph,'DRAW':pd,'AWAY':pa,'OVER 2.5':o25,'UNDER 2.5':1-o25,'OVER 3.5':o35,'UNDER 3.5':1-o35,'BTTS YES':btts,'BTTS NO':1-btts,'HOME +0.5':ph+pd,'AWAY +0.5':pa+pd},'goals':{'over15':o15,'over25':o25,'under25':1-o25,'over35':o35,'under35':1-o35,'btts':btts},'scores':scores,'hr':rating(home,teams),'ar':rating(away,teams),'hreg':reg(home),'areg':reg(away),'reliability':reliability,'model_info':{'home_attack_shrunk':round(h_att,2),'home_defence_shrunk':round(h_def,2),'away_attack_shrunk':round(a_att,2),'away_defence_shrunk':round(a_def,2),'home_reg_adj_pct':round(h_reg*100,1),'away_reg_adj_pct':round(a_reg*100,1),'league_xg90':round(lm['xg'],2)}}

def confidence(p,home,away):
    # Signal quality, not probability of winning: combines probability separation, sample size and xG strength differential.
    sep=abs(p-.5)*100; sample=min(1,(f(home.get('M'))+f(away.get('M')))/20); xgd=min(1,abs(f(home['xGD90'])-f(away['xGD90']))/1.5)
    return round(max(0,min(100,45+sep*.55+sample*20+xgd*15)))

def value_label(E):
    if E is None: return '-'
    if E < 3: return 'NO BET'
    if E < 5: return 'WATCH'
    if E < 10: return 'VALUE'
    return 'STRONG EDGE'

def novig_probs(odds):
    if not odds or any(x is None or x <= 1 for x in odds): return None
    inv=[1/x for x in odds]; z=sum(inv)
    return [x/z for x in inv]

def adjusted_prob(raw, market, reliability):
    if market is None: return raw
    r=max(0,min(1,reliability/100))
    return market + r*(raw-market)

def mc_check(lh,la,n=50000,seed=20260925):
    # Deterministic Monte Carlo cross-check without numpy.
    import random
    rng=random.Random(seed)
    def draw_poisson(lam):
        L=math.exp(-lam); k=0; prod=1.0
        while prod>L:
            k+=1; prod*=rng.random()
        return k-1
    h=d=a=o25=o35=b=0
    for _ in range(n):
        x=draw_poisson(lh); y=draw_poisson(la)
        if x>y:h+=1
        elif x==y:d+=1
        else:a+=1
        if x+y>=3:o25+=1
        if x+y>=4:o35+=1
        if x>0 and y>0:b+=1
    return {'HOME':h/n,'DRAW':d/n,'AWAY':a/n,'OVER 2.5':o25/n,'OVER 3.5':o35/n,'BTTS YES':b/n}

def market_rows(e,o):
    reliability=e['reliability']
    mkt={}
    p3=novig_probs([o.home_odds,o.draw_odds,o.away_odds])
    if p3:
        for k,v in zip(['HOME','DRAW','AWAY'],p3):mkt[k]=v
    p25=novig_probs([o.over25_odds,o.under25_odds])
    if p25:mkt['OVER 2.5'],mkt['UNDER 2.5']=p25
    p35=novig_probs([o.over35_odds,o.under35_odds])
    if p35:mkt['OVER 3.5'],mkt['UNDER 3.5']=p35
    pb=novig_probs([o.btts_odds,o.btts_no_odds])
    if pb:mkt['BTTS YES'],mkt['BTTS NO']=pb
    specs=[('HOME',o.home_odds),('DRAW',o.draw_odds),('AWAY',o.away_odds),('OVER 2.5',o.over25_odds),('UNDER 2.5',o.under25_odds),('OVER 3.5',o.over35_odds),('UNDER 3.5',o.under35_odds),('BTTS YES',o.btts_odds),('BTTS NO',o.btts_no_odds)]
    rows=[]
    for name,odd in specs:
        raw=e['p'][name]; mp=mkt.get(name); adj=adjusted_prob(raw,mp,reliability)
        raw_ev=ev(raw,odd); adj_ev=ev(adj,odd)
        divergence=round((raw-mp)*100,1) if mp is not None else None
        review=abs(divergence)>=10 if divergence is not None else False
        rows.append({'market':name,'p':round(raw*100,1),'market_p':round(mp*100,1) if mp is not None else None,'adjusted_p':round(adj*100,1),'fair':fair(raw),'adjusted_fair':fair(adj),'odds':odd,'raw_ev':raw_ev,'ev':adj_ev,'kelly25':kelly25(adj,odd) if adj_ev is not None and adj_ev>=3 else 0 if odd else None,'label':value_label(adj_ev),'divergence_pp':divergence,'review':review})
    return rows

@app.get('/')
def root():return FileResponse(STATIC/'index.html')
@app.get('/api/meta')
def meta():return {'leagues':LEAGUES,'default_season':2026,'cache_minutes':TTL//60,'version':'6.0'}
@app.get('/api/league/{league}/{season}')
async def league(league:str,season:int,refresh:bool=False):return await league_bundle(league,season,refresh)
@app.post('/api/analyze')
async def analyze(d:Analyze):
    b=await league_bundle(d.league,d.season); by={x['Team']:x for x in b['teams']}
    if d.home not in by or d.away not in by:raise HTTPException(404,'Ekipa nije pronađena')
    e=engine(by[d.home],by[d.away],b['teams'])
    mc=mc_check(e['lh'],e['la'])
    max_mc_diff=max(abs(e['p'][k]-mc[k]) for k in mc)
    return {'home':by[d.home],'away':by[d.away],'lambda_home':round(e['lh'],2),'lambda_away':round(e['la'],2),'home_rating':e['hr'],'away_rating':e['ar'],'home_regression':e['hreg'],'away_regression':e['areg'],'model_reliability':e['reliability'],'model_info':e['model_info'],'mc_check':{k:round(v*100,1) for k,v in mc.items()},'mc_max_diff_pp':round(max_mc_diff*100,2),'mc_status':'OK' if max_mc_diff<=0.01 else 'REVIEW','markets':market_rows(e,d),'goals':{k:round(v*100,1) for k,v in e['goals'].items()},'scores':[{'score':f'{i}-{j}','p':round(v*100,1)} for (i,j),v in e['scores']],'updated':b['updated'],'stale':b.get('stale',False)}
@app.post('/api/scan')
async def scan(d:Scan):
    b=await league_bundle(d.league,d.season); by={x['Team']:x for x in b['teams']}; om={x.id:x for x in d.odds}; out=[]
    for fx in b['fixtures'][:40]:
        if fx['home'] not in by or fx['away'] not in by:continue
        h,a=by[fx['home']],by[fx['away']]; e=engine(h,a,b['teams']); oo=om.get(fx['id'])
        odds={'HOME':getattr(oo,'home',None) if oo else None,'DRAW':getattr(oo,'draw',None) if oo else None,'AWAY':getattr(oo,'away',None) if oo else None,'OVER 2.5':getattr(oo,'over25',None) if oo else None,'UNDER 2.5':getattr(oo,'under25',None) if oo else None,'OVER 3.5':getattr(oo,'over35',None) if oo else None,'UNDER 3.5':getattr(oo,'under35',None) if oo else None,'BTTS YES':getattr(oo,'btts',None) if oo else None,'BTTS NO':getattr(oo,'btts_no',None) if oo else None}
        for m in ['HOME','DRAW','AWAY','OVER 2.5','UNDER 2.5','OVER 3.5','UNDER 3.5','BTTS YES','BTTS NO']:
            p=e['p'][m]; odd=odds[m]; E=ev(p,odd); conf=confidence(p,h,a)
            if odd is not None and E is not None and E>0:
                out.append({'fixture_id':fx['id'],'datetime':fx['datetime'],'home':fx['home'],'away':fx['away'],'market':m,'p':round(p*100,1),'fair':fair(p),'odds':odd,'ev':E,'kelly25':kelly25(p,odd),'label':value_label(E),'signal':conf,'lambda':f"{e['lh']:.2f}–{e['la']:.2f}"})
        # If no odds supplied, expose strongest model signals separately, never call them value bets.
        if oo is None:
            candidates=['HOME','DRAW','AWAY','OVER 2.5','UNDER 2.5','OVER 3.5','UNDER 3.5','BTTS YES','BTTS NO']
            m=max(candidates,key=lambda x:e['p'][x]); p=e['p'][m]
            out.append({'fixture_id':fx['id'],'datetime':fx['datetime'],'home':fx['home'],'away':fx['away'],'market':m,'p':round(p*100,1),'fair':fair(p),'odds':None,'ev':None,'kelly25':None,'signal':confidence(p,h,a),'lambda':f"{e['lh']:.2f}–{e['la']:.2f}"})
    valued=[x for x in out if x['ev'] is not None]; signals=[x for x in out if x['ev'] is None]
    valued.sort(key=lambda x:(x['ev'],x['signal']),reverse=True); signals.sort(key=lambda x:(x['signal'],x['p']),reverse=True)
    return {'value_bets':valued[:d.limit],'model_signals':signals[:d.limit],'fixtures_checked':min(40,len(b['fixtures'])),'updated':b['updated'],'stale':b.get('stale',False)}
@app.get('/api/health')
def health():return {'ok':True,'version':'6.0'}
