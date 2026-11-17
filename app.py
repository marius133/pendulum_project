import json
from dataclasses import asdict
from itertools import count
from pathlib import Path

from flask import Flask, render_template, request

from production import process_order
from spoolman_client import SpoolmanClient, SpoolmanError, SpoolmanUnavailableError
from validation import validate_order

app = Flask(__name__)
spoolman = SpoolmanClient()


# Error handling for Spoolman and the production result in create_order() are
# AI-assisted (Claude, Anthropic), reviewed and tested by the group.
def load_spools():
    """Active spools from Spoolman, or ([], message) if the stock is not available."""
    try:
        return spoolman.get_spools(include_archived=False), None
    except SpoolmanError as error:
        return [], str(error)


# Displays the pendulum order form
@app.get("/")
def show_order_form():
    spools, error = load_spools()
    if not error and not spools:
        error = "The material stock is empty. No orders can be produced right now."
    return render_template("order.html", spools=spools, error=error), (503 if error else 200)


# Validate the order, save it, and run it through production
@app.post("/orders")
def create_order():
    spools, error = load_spools()
    if error:
        return render_template("order.html", error=error, spools=spools), 503

    available_spool_ids = {spool["id"] for spool in spools}
    try:
        order = validate_order(request.form, available_spool_ids)
    except ValueError as error:
        return render_template("order.html", error=str(error), spools=spools), 400

    order_number = save_order(order)

    try:
        result = process_order(order_number, order, spoolman)
    except SpoolmanUnavailableError as error:
        return render_template("order.html", spools=spools,
                               error=f"Order {order_number} was saved, but {error}"), 503
    except Exception:
        app.logger.exception("Production failed for order %s", order_number)
        return render_template("order.html", spools=spools,
                               error=f"Order {order_number} was saved, but production failed. "
                                     f"Run 'python production.py' to try again."), 500

    spools, _ = load_spools()   # show the new remaining weights
    return render_template("order.html", order=order, order_number=order_number,
                           result=result, spools=spools)


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
