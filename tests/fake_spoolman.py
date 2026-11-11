"""
A tiny in-memory imitation of the Spoolman REST API, for tests only.
It covers just the endpoints our client uses and runs on a free local port.

AI-assisted: first version generated with Claude (Anthropic).
"""
import threading

from flask import Flask, jsonify, request
from werkzeug.serving import make_server


def create_app():
    app = Flask("fake_spoolman")
    db = {"vendor": {}, "filament": {}, "spool": {}, "next": 1}

    def new_id():
        db["next"] += 1
        return db["next"] - 1

    def spool_view(s):
        out = dict(s)
        out["remaining_weight"] = s["initial_weight"] - s["used_weight"]
        out["filament"] = db["filament"][s["filament_id"]]
        return out

    @app.get("/api/v1/health")
    def health():
        return jsonify(status="healthy")

    @app.get("/api/v1/vendor")
    def vendors():
        name = request.args.get("name")
        return jsonify([v for v in db["vendor"].values() if name is None or v["name"] == name])

    @app.post("/api/v1/vendor")
    def add_vendor():
        v = {"id": new_id(), "name": request.json["name"]}
        db["vendor"][v["id"]] = v
        return jsonify(v)

    @app.get("/api/v1/filament")
    def filaments():
        name = request.args.get("name")
        return jsonify([f for f in db["filament"].values() if name is None or f["name"] == name])

    @app.get("/api/v1/filament/<int:fid>")
    def filament(fid):
        if fid not in db["filament"]:
            return jsonify(message="not found"), 404
        return jsonify(db["filament"][fid])

    @app.post("/api/v1/filament")
    def add_filament():
        data = dict(request.json)
        if "density" not in data or "diameter" not in data:
            return jsonify(detail="density and diameter are required"), 422
        vendor = db["vendor"].get(data.pop("vendor_id", None))
        f = {"id": new_id(), "vendor": vendor, **data}
        db["filament"][f["id"]] = f
        return jsonify(f)

    @app.get("/api/v1/spool")
    def spools():
        fid = request.args.get("filament.id", type=int)
        return jsonify([spool_view(s) for s in db["spool"].values()
                        if fid is None or s["filament_id"] == fid])

    @app.get("/api/v1/spool/<int:sid>")
    def spool(sid):
        if sid not in db["spool"]:
            return jsonify(message="not found"), 404
        return jsonify(spool_view(db["spool"][sid]))

    @app.post("/api/v1/spool")
    def add_spool():
        data = request.json
        if data.get("filament_id") not in db["filament"]:
            return jsonify(detail="unknown filament"), 400
        s = {"id": new_id(), "filament_id": data["filament_id"],
             "initial_weight": data.get("initial_weight", 1000), "used_weight": 0.0,
             "location": data.get("location")}
        db["spool"][s["id"]] = s
        return jsonify(spool_view(s))

    @app.put("/api/v1/spool/<int:sid>/use")
    def use(sid):
        if sid not in db["spool"]:
            return jsonify(message="not found"), 404
        db["spool"][sid]["used_weight"] += request.json["use_weight"]
        return jsonify(spool_view(db["spool"][sid]))

    @app.get("/api/v1/broken")
    def broken():
        return "boom", 500

    return app


class FakeSpoolman:
    """Context manager: `with FakeSpoolman() as url: ...`"""

    def __enter__(self):
        self.server = make_server("127.0.0.1", 0, create_app())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}"

    def __exit__(self, *exc):
        self.server.shutdown()
