# Harvest Marketplace (no agents yet)

Run: `pip install -r requirements.txt && uvicorn main:app --reload` then open http://localhost:8000
(API docs at /docs). Delete `market.db` to reset the sample data.

## What it does
- Farmers publish listings (produce, kg, LKR/kg, district, optional deadline) and close them.
- Buyers browse/filter listings and place orders.
- Order lifecycle: pending -> confirmed -> completed, with decline / cancel / reject_delivery.
- Accepting an order reserves stock; a cancel or rejected delivery returns it to the listing.
- Every action is appended to an `events` table.
- "Login" is a demo user switcher (X-User-Id header). Replace with real auth before real use.

## Where agents plug in later
1. **Trigger:** a `sale_disrupted` event is written whenever a confirmed order is cancelled or a delivery
   is rejected. Its payload holds produce, quantity, district, price and deadline: this is your incident.
   Poll `GET /api/events?type=sale_disrupted` or call your agent from `order_action()` in main.py.
2. **Perceive tools:** `GET /api/listings` and the users/orders tables are your buyer and transport data.
   Add `min_price` / capacity fields to buyers when the Recovery agent needs them.
3. **Act tools:** `place_order` and `order_action` are the only write paths. Keep the agent proposing
   plans only; the farmer's click must call them (human approval boundary from the proposal).
4. **Voice input:** add a `POST /api/incidents/voice` endpoint beside the listing routes.
5. **Suggested layout when it grows:** `agents/` (planner + tools), `routers/`, `db.py`.
