import sqlite3

def calculate_match_score(farmer_district, buyer_district, farmer_price, buyer_max_price, buyer_quantity, required_quantity):

    score = 0

    # 1. District match
    if farmer_district.lower() == buyer_district.lower():
        score += 40

    # 2. Price suitability
    if buyer_max_price >= farmer_price:
        score += 30

    # 3. Quantity suitability
    if buyer_quantity >= required_quantity:
        score += 20

    # 4. Produce match
    score += 10

    return score

def explain_buyer_match(produce, farmer_price, farmer_district, buyer_quantity, buyer_max_price, buyer_district, allocated_quantity):

    reasons = []

    reasons.append(f"Requires {produce}")

    if buyer_max_price >= farmer_price:
        reasons.append(f"Accepts the farmer's price of Rs. {farmer_price}/kg")

    if farmer_district.lower() == buyer_district.lower():
        reasons.append("Located in the farmer's district")
    else:
        reasons.append(f"Located in {buyer_district}")

    reasons.append(f"Can purchase {allocated_quantity} kg")

    explanation = ", ".join(reasons)

    return explanation

def calculate_urgency(produce):

    produce = produce.lower()

    urgency_levels = {
        "spinach": 5,
        "lettuce": 5,
        "cabbage": 4,
        "tomato": 4,
        "carrot": 3,
        "potato": 2,
        "onion": 1
    }

    urgency = urgency_levels.get(produce, 3)

    return urgency

def calculate_rescue_priority(match_score, urgency):

    priority_score = match_score + (urgency * 5)

    return min(priority_score, 100) 

def find_matching_buyers(produce, quantity, price, district):

    print("Searching for matching buyers...")

    urgency = calculate_urgency(produce)

    if urgency >= 5:
        urgency_label = "CRITICAL"
    elif urgency >= 4:
        urgency_label = "HIGH"
    elif urgency >= 3:
        urgency_label = "MEDIUM"
    elif urgency >= 2:
        urgency_label = "LOW"
    else:
        urgency_label = "VERY LOW"

    conn = sqlite3.connect("market.db")
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            buyer_requirements.id,
            users.name,
            buyer_requirements.produce,
            buyer_requirements.quantity_kg,
            buyer_requirements.max_price_per_kg,
            buyer_requirements.district

        FROM buyer_requirements

        JOIN users
        ON buyer_requirements.buyer_id = users.id

        WHERE buyer_requirements.produce = ?
        AND buyer_requirements.max_price_per_kg >= ?

        ORDER BY
            CASE
                WHEN buyer_requirements.district = ? THEN 0
                ELSE 1
            END,
            buyer_requirements.max_price_per_kg DESC

    """, (produce, price, district))

    buyers = cursor.fetchall()
    conn.close()

    buyers.sort(
    key=lambda buyer: calculate_match_score(
        district,
        buyer[5],
        price,
        buyer[4],
        buyer[3],
        quantity
    ),
    reverse=True
)

    remaining_quantity = quantity
    allocations = []

    for buyer in buyers:

        if remaining_quantity <= 0:
            break

        buyer_id, name, buyer_produce, buyer_quantity, max_price, buyer_district = buyer

        score = calculate_match_score(
            district,
            buyer_district,
            price,
            max_price,
            buyer_quantity,
            quantity
        )

        priority_score = calculate_rescue_priority(score, urgency)

        allocated_quantity = min(remaining_quantity, buyer_quantity)

        explanation = explain_buyer_match(
            produce,
            price,
            district,
            buyer_quantity,
            max_price,
            buyer_district,
            allocated_quantity
        )

        allocations.append({
            "buyer": name,
            "quantity": allocated_quantity,
            "max_price": max_price,
            "district": buyer_district,
            "match_score": score,
            "priority_score": priority_score,
            "explanation": explanation
        })

        remaining_quantity -= allocated_quantity

    print("\nRescue Plan")
    print("-" * 40)
    print(f"Produce: {produce}")
    print(f"Urgency: {urgency_label} ({urgency}/5)")
    print("-" * 40)

    for allocation in allocations:
        print(f"Buyer: {allocation['buyer']}")
        print(f"Quantity: {allocation['quantity']} kg")
        print(f"Maximum price: Rs. {allocation['max_price']}/kg")
        print(f"District: {allocation['district']}")
        print(f"Matching score: {allocation['match_score']}/100")
        print(f"Rescue priority: {allocation['priority_score']}/100")
        print(f"Reason: {allocation['explanation']}")
        print("-" * 40)

    total_rescued = sum(
        allocation["quantity"] for allocation in allocations
    )

    remaining_quantity = quantity - total_rescued

    potential_recovery = total_rescued * price

    print("\nRescue Summary")
    print("=" * 40)

    print(f"Available quantity: {quantity} kg")
    print(f"Successfully matched: {total_rescued} kg")
    print(f"Unsold quantity: {remaining_quantity} kg")
    print(f"Farmer's price: Rs. {price}/kg")
    print(f"Potential recovery: Rs. {potential_recovery:,.2f}")

    if remaining_quantity > 0:
        print("\nNext Recovery Recommendation")

        if total_rescued > 0:
            print(f"{remaining_quantity} kg still needs to be rescued.")
            print("Recommendation: Search for additional buyers or negotiate a lower price.")
        else:
            print("No suitable buyers were found.")
            print("Recommendation: Expand the search to nearby districts or reconsider the price.")
    else:
        print("\nRecommendation: All produce has been successfully allocated.")

    return allocations

find_matching_buyers("Carrot", 200, 200, "Colombo")

print(calculate_rescue_priority(80, 4))
print(calculate_rescue_priority(40, 3))
print(calculate_rescue_priority(70, 5))

