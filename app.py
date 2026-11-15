import json
from flask import Flask, render_template,request
from validation import validate_order
from pathlib import Path
from itertools import count
from spoolman_client import SpoolmanClient
from dataclasses import asdict
from production import export_order, parameters_for_order

app = Flask(__name__)
spoolman = SpoolmanClient()
@app.get("/")

# Displays the pendulum order form
def show_order_form():
    spools = spoolman.get_spools(include_archived=False)
    return render_template("order.html", spools=spools)

@app.post("/orders")

# Save valid orders and pass validation errors to the order form
def create_order():

    spools = spoolman.get_spools(include_archived=False)
    available_spool_ids = {spool["id"] for spool in spools}

    try:
        order = validate_order(request.form, available_spool_ids)
        parameters = parameters_for_order(order)
    except ValueError as error:
        return render_template("order.html", error=str(error), spools=spools), 400

    order_number = save_order(order)

    try:
        export_order(order_number, parameters)
    except Exception:
        app.logger.exception("3MF export failed for order %s", order_number)
        return render_template(
            "order.html",
            error=f"Order {order_number} was saved. 3MF export failed.",
            spools=spools,
        ), 500

    return render_template(
        "order.html", order=order, order_number=order_number, spools=spools
    )

# Save orders as json-file in dir "orders" with unique id per order (counting from one and up)
def save_order(order):
    orders_dir = Path(__file__).resolve().parent / "orders"
    orders_dir.mkdir(exist_ok=True)

    for order_number in count(1):
        order_path = orders_dir / f"order-{order_number:01d}.json"

        try:
            with order_path.open("x", encoding="utf-8") as file:
                json.dump(asdict(order), file, indent=4)
        except FileExistsError:
            continue
        return order_number
