import sqlite3

def find_matching_buyers(produce, quantity, price, district):

    print("Searching for matching buyers...")

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

    remaining_quantity = quantity
    allocations = []

    for buyer in buyers:

        if remaining_quantity <= 0:
            break

        buyer_id, name, buyer_produce, buyer_quantity, max_price, buyer_district = buyer

        allocated_quantity = min(remaining_quantity, buyer_quantity)

        allocations.append({
            "buyer": name,
            "quantity": allocated_quantity,
            "max_price": max_price,
            "district": buyer_district
        })

        remaining_quantity -= allocated_quantity

    print("\nRescue Plan")
    print("-" * 40)

    for allocation in allocations:
        print(f"Buyer: {allocation['buyer']}")
        print(f"Quantity: {allocation['quantity']} kg")
        print(f"Maximum price: Rs. {allocation['max_price']}/kg")
        print(f"District: {allocation['district']}")
        print("-" * 40)

    print(f"Total quantity rescued: {quantity - remaining_quantity} kg")
    print(f"Remaining quantity: {remaining_quantity} kg")

    return allocations

find_matching_buyers("Carrot", 200, 200, "Colombo")
