"""Harvest Marketplace: farmer-to-buyer marketplace (no agents yet).

Run:  pip install -r requirements.txt && uvicorn main:app --reload
Docs: http://localhost:8000/docs     App: http://localhost:8000
"""
import json, sqlite3, time
from contextlib import contextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
DB = ROOT / "market.db"
app = FastAPI(title="Harvest Marketplace")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY, name TEXT, role TEXT, phone TEXT, district TEXT);
CREATE TABLE IF NOT EXISTS listings(
  id INTEGER PRIMARY KEY, farmer_id INTEGER, produce TEXT, quantity_kg REAL,
  price_per_kg REAL, district TEXT, available_until TEXT,
  status TEXT DEFAULT 'open', created_at REAL);
CREATE TABLE IF NOT EXISTS orders(
  id INTEGER PRIMARY KEY, listing_id INTEGER, buyer_id INTEGER, quantity_kg REAL,
  price_per_kg REAL, status TEXT DEFAULT 'pending', created_at REAL, updated_at REAL);
-- Append-only log of everything that happens. Agents will read from this.
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY, ts REAL, type TEXT, entity TEXT, entity_id INTEGER, payload TEXT);
"""


@contextmanager
def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def log(c, type_, entity, entity_id, **payload):
    c.execute("INSERT INTO events(ts,type,entity,entity_id,payload) VALUES(?,?,?,?,?)",
              (time.time(), type_, entity, entity_id, json.dumps(payload)))


def rows(cur):
    return [dict(r) for r in cur.fetchall()]


def need_user(c, uid):
    u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone() if uid else None
    if not u:
        raise HTTPException(401, "Send a valid X-User-Id header (demo login).")
    return dict(u)


# ---------- models ----------
class UserIn(BaseModel):
    name: str
    role: Literal["farmer", "buyer"]
    phone: str = ""
    district: str = ""


class ListingIn(BaseModel):
    produce: str
    quantity_kg: float = Field(gt=0)
    price_per_kg: float = Field(gt=0)
    district: str
    available_until: Optional[str] = None  # ISO datetime, optional


class OrderIn(BaseModel):
    listing_id: int
    quantity_kg: float = Field(gt=0)


# ---------- users (demo auth: swap for real auth later) ----------
@app.post("/api/users")
def create_user(u: UserIn):
    with conn() as c:
        cur = c.execute("INSERT INTO users(name,role,phone,district) VALUES(?,?,?,?)",
                        (u.name, u.role, u.phone, u.district))
        log(c, "user_created", "user", cur.lastrowid, role=u.role)
        return {"id": cur.lastrowid, **u.model_dump()}


@app.get("/api/users")
def list_users():
    with conn() as c:
        return rows(c.execute("SELECT * FROM users"))


# ---------- listings ----------
@app.get("/api/listings")
def browse(produce: str = "", district: str = "", max_price: float = 0,
           farmer_id: int = 0, include_closed: bool = False):
    q = ("SELECT l.*, u.name AS farmer_name, u.phone AS farmer_phone FROM listings l "
         "JOIN users u ON u.id=l.farmer_id WHERE 1=1")
    p = []
    if not include_closed:
        q += " AND l.status='open'"
    if produce:
        q += " AND lower(l.produce) LIKE ?"; p.append(f"%{produce.lower()}%")
    if district:
        q += " AND lower(l.district)=?"; p.append(district.lower())
    if max_price:
        q += " AND l.price_per_kg<=?"; p.append(max_price)
    if farmer_id:
        q += " AND l.farmer_id=?"; p.append(farmer_id)
    with conn() as c:
        return rows(c.execute(q + " ORDER BY l.created_at DESC", p))


@app.post("/api/listings")
def create_listing(l: ListingIn, x_user_id: Optional[int] = Header(None)):
    with conn() as c:
        u = need_user(c, x_user_id)
        if u["role"] != "farmer":
            raise HTTPException(403, "Only farmers can list produce.")
        cur = c.execute(
            "INSERT INTO listings(farmer_id,produce,quantity_kg,price_per_kg,district,"
            "available_until,created_at) VALUES(?,?,?,?,?,?,?)",
            (u["id"], l.produce, l.quantity_kg, l.price_per_kg, l.district,
             l.available_until, time.time()))
        log(c, "listing_created", "listing", cur.lastrowid, **l.model_dump())
        return {"id": cur.lastrowid}


@app.delete("/api/listings/{lid}")
def close_listing(lid: int, x_user_id: Optional[int] = Header(None)):
    with conn() as c:
        u = need_user(c, x_user_id)
        r = c.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
        if not r:
            raise HTTPException(404, "Listing not found.")
        if r["farmer_id"] != u["id"]:
            raise HTTPException(403, "Not your listing.")
        c.execute("UPDATE listings SET status='closed' WHERE id=?", (lid,))
        log(c, "listing_closed", "listing", lid)
        return {"ok": True}


# ---------- orders ----------
@app.post("/api/orders")
def place_order(o: OrderIn, x_user_id: Optional[int] = Header(None)):
    with conn() as c:
        u = need_user(c, x_user_id)
        if u["role"] != "buyer":
            raise HTTPException(403, "Only buyers can place orders.")
        l = c.execute("SELECT * FROM listings WHERE id=?", (o.listing_id,)).fetchone()
        if not l or l["status"] != "open":
            raise HTTPException(404, "Listing is not available.")
        if o.quantity_kg > l["quantity_kg"]:
            raise HTTPException(409, f"Only {l['quantity_kg']} kg available.")
        now = time.time()
        cur = c.execute(
            "INSERT INTO orders(listing_id,buyer_id,quantity_kg,price_per_kg,created_at,updated_at)"
            " VALUES(?,?,?,?,?,?)", (l["id"], u["id"], o.quantity_kg, l["price_per_kg"], now, now))
        log(c, "order_placed", "order", cur.lastrowid, listing_id=l["id"], qty=o.quantity_kg)
        return {"id": cur.lastrowid}


@app.get("/api/orders")
def my_orders(x_user_id: Optional[int] = Header(None)):
    with conn() as c:
        u = need_user(c, x_user_id)
        col = "l.farmer_id" if u["role"] == "farmer" else "o.buyer_id"
        return rows(c.execute(
            f"SELECT o.*, l.produce, l.district, l.farmer_id, fu.name AS farmer_name, "
            f"bu.name AS buyer_name FROM orders o JOIN listings l ON l.id=o.listing_id "
            f"JOIN users fu ON fu.id=l.farmer_id JOIN users bu ON bu.id=o.buyer_id "
            f"WHERE {col}=? ORDER BY o.created_at DESC", (u["id"],)))


# action -> (who acts, allowed current statuses, new status)
RULES = {
    "accept":          ("farmer", ("pending",), "confirmed"),
    "decline":         ("farmer", ("pending",), "declined"),
    "cancel":          ("buyer", ("pending", "confirmed"), "cancelled"),
    "reject_delivery": ("buyer", ("confirmed",), "rejected"),
    "complete":        ("buyer", ("confirmed",), "completed"),
}


@app.post("/api/orders/{oid}/{action}")
def order_action(oid: int, action: str, x_user_id: Optional[int] = Header(None)):
    if action not in RULES:
        raise HTTPException(400, f"Unknown action. Use one of {list(RULES)}.")
    who, allowed, new = RULES[action]
    with conn() as c:
        u = need_user(c, x_user_id)
        o = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        if not o:
            raise HTTPException(404, "Order not found.")
        l = c.execute("SELECT * FROM listings WHERE id=?", (o["listing_id"],)).fetchone()
        owner = l["farmer_id"] if who == "farmer" else o["buyer_id"]
        if u["id"] != owner:
            raise HTTPException(403, f"Only the {who} on this order can {action}.")
        if o["status"] not in allowed:
            raise HTTPException(409, f"Can't {action} an order that is {o['status']}.")

        if action == "accept":
            if l["quantity_kg"] < o["quantity_kg"]:
                raise HTTPException(409, "Not enough stock left to accept this order.")
            left = l["quantity_kg"] - o["quantity_kg"]
            c.execute("UPDATE listings SET quantity_kg=?, status=? WHERE id=?",
                      (left, "open" if left > 0 else "sold", l["id"]))

        if o["status"] == "confirmed" and action in ("cancel", "reject_delivery"):
            # Stock returns to the farmer. This is the "failed sale" moment.
            c.execute("UPDATE listings SET quantity_kg=quantity_kg+?, status='open' WHERE id=?",
                      (o["quantity_kg"], l["id"]))
            log(c, "sale_disrupted", "order", oid, reason=action, produce=l["produce"],
                quantity_kg=o["quantity_kg"], farmer_id=l["farmer_id"],
                district=l["district"], price_per_kg=o["price_per_kg"],
                available_until=l["available_until"])

        c.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?", (new, time.time(), oid))
        log(c, f"order_{new}", "order", oid, by=u["id"])
        return {"id": oid, "status": new}


@app.get("/api/events")
def events(type: str = "", limit: int = 100):
    q, p = "SELECT * FROM events", []
    if type:
        q += " WHERE type=?"; p.append(type)
    with conn() as c:
        return rows(c.execute(q + " ORDER BY id DESC LIMIT ?", p + [limit]))


# ---------- startup + sample data (fictional) ----------
@app.on_event("startup")
def init():
    with conn() as c:
        c.executescript(SCHEMA)
        if c.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            return
        for n, r, ph, d in [
            ("Nimal Perera (farmer)", "farmer", "0710000001", "Nuwara Eliya"),
            ("Kamala Silva (farmer)", "farmer", "0710000002", "Badulla"),
            ("Green Mart (buyer)", "buyer", "0770000001", "Colombo"),
            ("Fresh Juice Co. (buyer)", "buyer", "0770000002", "Kandy"),
            ("Lanka Wholesale (buyer)", "buyer", "0770000003", "Colombo")]:
            c.execute("INSERT INTO users(name,role,phone,district) VALUES(?,?,?,?)", (n, r, ph, d))
        for f, p, q, pr, d in [(1, "Tomato", 200, 170, "Nuwara Eliya"),
                               (1, "Carrot", 120, 210, "Nuwara Eliya"),
                               (2, "Tomato", 80, 160, "Badulla"),
                               (2, "Spinach", 40, 120, "Badulla")]:
            c.execute("INSERT INTO listings(farmer_id,produce,quantity_kg,price_per_kg,district,"
                      "created_at) VALUES(?,?,?,?,?,?)", (f, p, q, pr, d, time.time()))
        soon = time.strftime("%Y-%m-%dT%H:%M", time.localtime(time.time() + 30 * 3600))
        c.execute("UPDATE listings SET available_until=? WHERE id IN (2,3)", (soon,))


app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
