import json
from dataclasses import asdict
from itertools import count
from pathlib import Path
from tempfile import TemporaryDirectory

from flask import Flask, jsonify, render_template, request

from configurator import achievable_period_range
from production import (
    load_kit_parameters,
    order_lock,
    parameters_for_axle,
    parameters_for_order,
    process_order,
    remaining_weight,
)
from spoolman_client import SpoolmanClient, SpoolmanError, SpoolmanUnavailableError
from validation import validate_float, validate_order

app = Flask(__name__)
spoolman = SpoolmanClient()


# Error handling for Spoolman and the production result in create_order() are
# AI-assisted (Claude, Anthropic), reviewed and tested by the group.
def load_spools():
    """Active spools from Spoolman, or ([], message) if the stock is not available."""
    try:
        spools = spoolman.get_spools(include_archived=False)
        return [{**spool, "remaining_weight": remaining_weight(spool)} for spool in spools], None
    except SpoolmanError as error:
        return [], str(error)


def period_parameters(values, *, base_parameters=None):
    diameter = None
    if "axle_diameter_mm" in values:
        diameter = validate_float(values, "axle_diameter_mm", "Axle diameter")
    return parameters_for_axle(diameter, base_parameters=base_parameters)


def render_order_form(**context):
    base_parameters = load_kit_parameters()
    axle_diameter = request.form.get("axle_diameter_mm", "")
    period_range = None
    range_error = None
    try:
        parameters = period_parameters(request.form, base_parameters=base_parameters)
        axle_diameter = parameters["axle_diameter_mm"]
        period_range = achievable_period_range(parameters)
    except ValueError as error:
        range_error = str(error)
    return render_template("order.html", axle_diameter_mm=axle_diameter,
                           min_axle_diameter_mm=base_parameters["min_axle_diameter_mm"],
                           period_range=period_range, range_error=range_error, **context)


@app.get("/period-range")
def get_period_range():
    try:
        minimum, maximum = achievable_period_range(period_parameters(request.args))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    return jsonify(minimum_s=minimum, maximum_s=maximum)


# Displays the pendulum order form
@app.get("/")
def show_order_form():
    spools, error = load_spools()
    if not error and not spools:
        error = "The material stock is empty. No orders can be produced right now."
    return render_order_form(spools=spools, error=error), (503 if error else 200)


# Validate the order, save it, and run it through production
@app.post("/orders")
def create_order():
    spools, error = load_spools()
    if error:
        return render_order_form(error=error, spools=spools), 503

    available_spool_ids = {spool["id"] for spool in spools}
    try:
        order = validate_order(request.form, available_spool_ids)
        parameters_for_order(order)
    except ValueError as error:
        return render_order_form(error=str(error), spools=spools), 400

    order_number = save_order(order)

    try:
        result = process_order(order_number, order, spoolman)
    except SpoolmanUnavailableError as error:
        return render_order_form(
            spools=spools, error=f"Order {order_number} was saved, but {error}"
        ), 503
    except Exception:
        app.logger.exception("Production failed for order %s", order_number)
        return render_order_form(
            spools=spools,
            error=f"Order {order_number} was saved, but production failed. Check its status before retrying.",
        ), 500

    spools, error = load_spools()
    return render_order_form(order=order, order_number=order_number, result=result, spools=spools, error=error)


# Save orders as json-file in dir "orders" with unique id per order (counting from one and up)
def save_order(order):
    orders_dir = Path(__file__).resolve().parent / "orders"
    with order_lock(orders_dir):
        for order_number in count(1):
            order_path = orders_dir / f"order-{order_number}.json"
            if order_path.exists():
                continue
            with TemporaryDirectory(dir=orders_dir) as directory:
                temp_path = Path(directory) / order_path.name
                temp_path.write_text(json.dumps(asdict(order), indent=4), encoding="utf-8")
                temp_path.replace(order_path)
            return order_number
