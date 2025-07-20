import csv
import os
import random
from datetime import datetime, timedelta

customer_ids = list(range(1, 21))
store_ids = list(range(121, 124))
product_data = {
    "Iphone": 70000,
    "Ipad": 60000,
    "Iwatch": 25000,
    "IMac": 80000,
    "Mac mini": 50000,
    "Ipods": 15000,
    "Travel Adapter": 2500,
    "Adapter Cable": 1000
}
sales_persons = {
    121: [1, 2, 3, 4, 5],
    122: [11, 12 , 13, 14, 15],
    123: [21, 22, 23, 24, 25]
}

start_date = datetime(2025, 1, 1)
end_date = datetime(2025, 6, 30)

file_location = "/Users/parthambhorkar/Data_Engineering_Project/"
csv_file_path = os.path.join(file_location, "sales_data.csv")
with open(csv_file_path, "w", newline="") as csvfile:
    csvwriter = csv.writer(csvfile)
    csvwriter.writerow(["customer_id", "store_id", "product_name", "sales_date", "sales_person_id", "price", "quantity", "total_cost"])

    for _ in range(500):
        customer_id = random.choice(customer_ids)
        store_id = random.choice(store_ids)
        product_name = random.choice(list(product_data.keys()))
        sales_date = start_date + timedelta(days=random.randint(0, (end_date - start_date).days))
        sales_person_id = random.choice(sales_persons[store_id])
        quantity = random.randint(1, 10)
        price = product_data[product_name]
        total_cost = price * quantity

        csvwriter.writerow([customer_id, store_id, product_name, sales_date.strftime("%Y-%m-%d"), sales_person_id, price, quantity, total_cost])

print("CSV file generated successfully.")
