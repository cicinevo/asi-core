from app.routes.command import router as command_router
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import httpx
from datetime import datetime

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ALPACA_API_KEY_ID = os.getenv("ALPACA_API_KEY_ID", "")
ALPACA_API_SECRET_KEY = os.getenv("ALPACA_API_SECRET_KEY", "")
ALPACA_BASE = os.getenv("ALPACA_PAPER_BASE_URL", "https://paper-api.alpaca.markets")

PG_USER=os.getenv("POSTGRES_USER","evo")
PG_PASS=os.getenv("POSTGRES_PASSWORD","evopass")
PG_DB  =os.getenv("POSTGRES_DB","evo")
DB_URL=f"postgresql://{PG_USER}:{PG_PASS}@db:5432/{PG_DB}"

engine = create_engine(DB_URL, future=True)
app = FastAPI(title="Evo Core API", version="0.1")

app.include_router(command_router)

# init tables
with engine.begin() as conn:
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS logs(
      id SERIAL PRIMARY KEY,
      ts TIMESTAMP NOT NULL,
      kind TEXT NOT NULL,
      message TEXT NOT NULL
    );"""))
    conn.execute(text("""
    CREATE TABLE IF NOT EXISTS trades(
      id SERIAL PRIMARY KEY,
      ts TIMESTAMP NOT NULL,
      symbol TEXT NOT NULL,
      side TEXT NOT NULL,
      qty NUMERIC NOT NULL,
      status TEXT NOT NULL,
      broker_id TEXT
    );"""))

class ChatIn(BaseModel):
    prompt: str

@app.get("/health")
def health():
    return {"ok": True, "time": datetime.utcnow().isoformat()}

@app.post("/chat")
async def chat(body: ChatIn):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=400, detail="OPENAI_API_KEY missing")
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":"You are Evo, a helpful operations cofounder."},
                  {"role":"user","content": body.prompt}],
        temperature=0.3,
    )
    text_out = resp.choices[0].message.content
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO logs(ts,kind,message) VALUES (NOW(),'chat', :m)"),
                     {"m": f"User: {body.prompt}\nEvo: {text_out}"})
    return {"reply": text_out}

class TradeIn(BaseModel):
    symbol: str
    side: str   # "buy" or "sell"
    qty: float

@app.post("/trade/paper")
async def trade_paper(order: TradeIn):
    if not (ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY):
        raise HTTPException(status_code=400, detail="Alpaca keys missing")
    if order.side not in {"buy","sell"}:
        raise HTTPException(status_code=400, detail="side must be 'buy' or 'sell'")
    url = f"{ALPACA_BASE}/v2/orders"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY_ID,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "symbol": order.symbol.upper(),
        "qty": order.qty,
        "side": order.side,
        "type": "market",
        "time_in_force": "day",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(url, headers=headers, json=payload)
    if r.status_code >= 300:
        raise HTTPException(status_code=502, detail=f"Alpaca error: {r.text}")
    data = r.json()
    with engine.begin() as conn:
        conn.execute(text(
          "INSERT INTO trades(ts,symbol,side,qty,status,broker_id) "
          "VALUES (NOW(), :s, :side, :q, :st, :bid)"
        ), {"s":order.symbol.upper(), "side":order.side, "q":order.qty,
            "st":data.get("status","submitted"), "bid":data.get("id")})
    return {"ok": True, "alpaca": data}

@app.get("/trades")
def list_trades():
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, ts, symbol, side, qty, status FROM trades ORDER BY id DESC LIMIT 100")).mappings().all()
    return {"trades":[dict(r) for r in rows]}

@app.get("/logs")
def list_logs():
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT id, ts, kind, message FROM logs ORDER BY id DESC LIMIT 100")).mappings().all()
    return {"logs":[dict(r) for r in rows]}