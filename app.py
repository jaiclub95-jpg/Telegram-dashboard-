
import os, hmac, secrets, time, asyncio
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from supabase import create_client
import httpx

ENV = ["SUPABASE_URL","SUPABASE_SERVICE_ROLE_KEY","WEB_ADMIN_USERNAME","WEB_ADMIN_PASSWORD","SESSION_SECRET"]
missing = [k for k in ENV if not os.getenv(k)]
if missing: raise RuntimeError("Missing environment variables: " + ", ".join(missing))
db = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
token = os.getenv("BOT_TOKEN","")
username, password = os.environ["WEB_ADMIN_USERNAME"], os.environ["WEB_ADMIN_PASSWORD"]
signer = URLSafeTimedSerializer(os.environ["SESSION_SECRET"], salt="support-dashboard")
app = FastAPI(title="Support Control")
app.mount("/static", StaticFiles(directory="static"), name="static")

def logged(request):
    try: return signer.loads(request.cookies.get("support_session",""), max_age=43200).get("u") == username
    except (BadSignature, SignatureExpired): return False

def auth(request):
    if not logged(request): raise HTTPException(401, "Please login")

@app.get("/health")
def health(): return {"status":"ok"}

@app.get("/login", response_class=HTMLResponse)
def login_page(): return open("templates/login.html",encoding="utf-8").read()

@app.post("/login")
def login(user: str=Form(...), secret: str=Form(...)):
    if not (hmac.compare_digest(user,username) and hmac.compare_digest(secret,password)):
        return HTMLResponse(open("templates/login.html",encoding="utf-8").read().replace("<!--ERR-->","<p class='err'>Invalid login</p>"),status_code=401)
    r=RedirectResponse("/",303)
    r.set_cookie("support_session",signer.dumps({"u":user,"n":secrets.token_hex(12)}),httponly=True,secure=True,samesite="strict",max_age=43200)
    return r

@app.post("/logout")
def logout():
    r=RedirectResponse("/login",303); r.delete_cookie("support_session"); return r

@app.get("/",response_class=HTMLResponse)
def home(request:Request):
    if not logged(request): return RedirectResponse("/login",303)
    return open("templates/index.html",encoding="utf-8").read()

def count(table, status=None):
    q=db.table(table).select("id",count="exact")
    if status=="open": q=q.in_("status",["pending","in_progress","reopened"])
    elif status: q=q.eq("status",status)
    return q.execute().count or 0

@app.get("/api/overview")
def overview(request:Request):
    auth(request)
    try:return {"users":count("customers"),"tickets":count("tickets"),"open":count("tickets","open"),"resolved":count("tickets","resolved")}
    except Exception: raise HTTPException(500,"Supabase overview failed; check table schema.")

@app.get("/api/users")
def users(request:Request,q:str=""):
    auth(request)
    x=db.table("customers").select("*").order("telegram_id",desc=True).limit(100)
    if q: x=x.eq("telegram_id",int(q)) if q.isdigit() else x.ilike("username",f"%{q.lstrip('@')}%")
    return x.execute().data or []

@app.post("/api/users")
async def add_user(request:Request):
    auth(request); d=await request.json()
    try:
        uid=int(d["telegram_id"])
        db.table("customers").upsert({"telegram_id":uid,"username":d.get("username") or None,"first_name":d.get("name") or None,"full_name":d.get("name") or None,"notes":d.get("notes") or None,"user_status":d.get("status","active"),"is_manual":True},on_conflict="telegram_id").execute()
        return {"ok":True}
    except Exception: raise HTTPException(400,"User save failed. Check UID and customers columns.")

@app.patch("/api/users/{uid}")
async def edit_user(uid:int,request:Request):
    auth(request); d=await request.json()
    fields={k:d[k] for k in ("notes","user_status","allow_new_complaint") if k in d}
    if not fields: raise HTTPException(400,"No supported fields")
    db.table("customers").update(fields).eq("telegram_id",uid).execute()
    return {"ok":True}

@app.get("/api/tickets")
def tickets(request:Request,status:str="all"):
    auth(request); q=db.table("tickets").select("*").order("id",desc=True).limit(200)
    if status!="all": q=q.eq("status",status)
    return q.execute().data or []

@app.patch("/api/tickets/{tid}")
async def edit_ticket(tid:int,request:Request):
    auth(request); d=await request.json(); s=d.get("status")
    if s not in ["pending","in_progress","reopened","resolved"]: raise HTTPException(400,"Invalid status")
    payload={"status":s}
    if s=="resolved": payload["resolved_at"]=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
    db.table("tickets").update(payload).eq("id",tid).execute()
    return {"ok":True}

async def tg_send(uid,text):
    if not token: raise HTTPException(500,"BOT_TOKEN missing in dashboard app")
    async with httpx.AsyncClient(timeout=25) as c:
        r=await c.post(f"https://api.telegram.org/bot{token}/sendMessage",json={"chat_id":uid,"text":text})
        if not r.json().get("ok"): raise HTTPException(400,"Telegram send failed; customer may not have started bot.")
        return r.json()["result"]["message_id"]

@app.post("/api/send")
async def send(request:Request):
    auth(request); d=await request.json()
    try:return {"ok":True,"message_id":await tg_send(int(d["telegram_id"]),str(d["text"]).strip())}
    except (KeyError,ValueError): raise HTTPException(400,"Valid UID and text required")

@app.post("/api/broadcast")
async def broadcast(request:Request):
    auth(request); d=await request.json(); text=str(d.get("text","")).strip()
    if not text: raise HTTPException(400,"Message required")
    ids=[int(x["telegram_id"]) for x in (db.table("customers").select("telegram_id").execute().data or []) if x.get("telegram_id")]
    sent=failed=0
    for uid in ids:
        try: await tg_send(uid,text); sent+=1
        except Exception: failed+=1
        await asyncio.sleep(.05)
    return {"total":len(ids),"sent":sent,"failed":failed}

@app.get("/api/activity")
def activity(request:Request):
    auth(request)
    try:return db.table("admin_activity_logs").select("*").order("id",desc=True).limit(100).execute().data or []
    except Exception: raise HTTPException(500,"Activity log table unavailable")
