import json
from flask import Flask, render_template,request
from validation import validate_order
from pathlib import Path
from itertools import count

app = Flask(__name__)
@app.get("/")

# Displays the pendulum order form
def show_order_form():
    return render_template("order.html")

@app.post("/orders")

# Save valid orders and pass validation errors to the order form
def create_order():
    try:
        order = validate_order(request.form)
    except ValueError as error:
        return render_template("order.html", error=str(error)), 400
    save_order(order)
    return render_template("order.html",order=order)

# Save orders as json-file in dir "orders" with unique id per order (counting from one and up)
def save_order(order):
    orders_dir = Path(__file__).resolve().parent / "orders"
    orders_dir.mkdir(exist_ok=True)

    for order_number in count(1):
        order_path = orders_dir / f"order-{order_number:01d}.json"

        try:
            with order_path.open("x", encoding="utf-8") as file:
                json.dump(order, file, indent=4)
        except FileExistsError:
            continue
        return
