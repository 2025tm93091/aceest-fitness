"""
app.py — Flask REST API for ACEest Fitness & Gym.

This module wires together:
    - core.py    (business logic)
    - db.py      (SQLite persistence)
    - report.py  (PDF generation)

Run locally:
    python app.py
Then:
    http://localhost:5000
"""

from io import BytesIO

from flask import Flask, jsonify, request, send_file

import core
import db
from report import build_client_report

# ---------------------------------------------------------------------------
# App factory-ish setup
# ---------------------------------------------------------------------------
app = Flask(__name__)

# Ensure the DB schema exists on startup (idempotent)
db.init_db()


# ---------------------------------------------------------------------------
# Meta endpoints
# ---------------------------------------------------------------------------

@app.route("/")
def home():
    """Root endpoint — confirms the service is running."""
    return jsonify(
        {
            "service": "ACEest Fitness & Gym API",
            "version": "1.0.0",
            "status": "running",
        }
    )


@app.route("/health")
def health():
    """Health check — used by Docker HEALTHCHECK and load balancers."""
    return jsonify({"status": "healthy"}), 200


# ---------------------------------------------------------------------------
# Programs & calculations (stateless)
# ---------------------------------------------------------------------------

@app.route("/programs", methods=["GET"])
def list_programs():
    """Return all available training programs."""
    return jsonify(core.list_programs())


@app.route("/calculate/calories", methods=["POST"])
def calc_calories():
    """
    Calculate daily calorie target.

    Request JSON:
        {"weight": 65.0, "program": "Fat Loss (FL) - 3 day"}
    """
    data = request.get_json(silent=True) or {}
    try:
        kcal = core.calculate_calories(
            float(data["weight"]), data["program"]
        )
    except KeyError as e:
        return jsonify({"error": f"Missing field: {e.args[0]}"}), 400
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"calories": kcal})


@app.route("/calculate/bmi", methods=["POST"])
def calc_bmi():
    """
    Calculate BMI with category + risk note.

    Request JSON:
        {"weight": 70.0, "height": 175.0}
    """
    data = request.get_json(silent=True) or {}
    try:
        bmi = core.calculate_bmi(
            float(data["weight"]), float(data["height"])
        )
    except KeyError as e:
        return jsonify({"error": f"Missing field: {e.args[0]}"}), 400
    except (ValueError, TypeError) as e:
        return jsonify({"error": str(e)}), 400

    category = core.bmi_category(bmi)
    return jsonify({"bmi": bmi, **category})


# ---------------------------------------------------------------------------
# Client CRUD
# ---------------------------------------------------------------------------

@app.route("/clients", methods=["GET"])
def clients_list():
    """Return all clients."""
    return jsonify(db.list_clients())


@app.route("/clients", methods=["POST"])
def clients_create():
    """
    Create or update a client.

    Request JSON:
        {
          "name": "Alice",
          "age": 28,
          "height": 170,
          "weight": 65,
          "program": "Fat Loss (FL) - 3 day",
          "target_weight": 60,
          "target_adherence": 80
        }
    """
    data = request.get_json(silent=True) or {}

    if not data.get("name"):
        return jsonify({"error": "Field 'name' is required"}), 400
    if not data.get("program"):
        return jsonify({"error": "Field 'program' is required"}), 400

    # Auto-calculate calories if weight + program are supplied
    if data.get("weight") and not data.get("calories"):
        try:
            data["calories"] = core.calculate_calories(
                float(data["weight"]), data["program"]
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    saved = db.upsert_client(data)
    return jsonify(saved), 201


@app.route("/clients/<name>", methods=["GET"])
def clients_get(name):
    """Return a single client by name."""
    client = db.get_client(name)
    if not client:
        return jsonify({"error": f"Client '{name}' not found"}), 404
    return jsonify(client)


@app.route("/clients/<name>", methods=["DELETE"])
def clients_delete(name):
    """Delete a client by name."""
    if db.delete_client(name):
        return jsonify({"status": "deleted", "name": name}), 200
    return jsonify({"error": f"Client '{name}' not found"}), 404


# ---------------------------------------------------------------------------
# Progress tracking
# ---------------------------------------------------------------------------

@app.route("/clients/<name>/progress", methods=["POST"])
def progress_log(name):
    """
    Log a weekly adherence entry.

    Request JSON:
        {"week": "Week 01 - 2026", "adherence": 75}
    (week is optional — defaults to current ISO week)
    """
    if not db.get_client(name):
        return jsonify({"error": f"Client '{name}' not found"}), 404

    data = request.get_json(silent=True) or {}
    from datetime import datetime

    week = data.get("week") or datetime.now().strftime("Week %U - %Y")
    try:
        adherence = int(data["adherence"])
    except KeyError:
        return jsonify({"error": "Field 'adherence' is required"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "adherence must be an integer"}), 400

    try:
        entry = db.log_progress(name, week, adherence)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(entry), 201


@app.route("/clients/<name>/progress", methods=["GET"])
def progress_get(name):
    """Return all weekly progress entries for a client."""
    return jsonify(db.get_progress(name))


# ---------------------------------------------------------------------------
# PDF report
# ---------------------------------------------------------------------------

@app.route("/clients/<name>/report.pdf", methods=["GET"])
def client_report(name):
    """
    Generate and stream a PDF report for a client.

    Query params:
        ?download=1  → force download instead of inline display
    """
    client = db.get_client(name)
    if not client:
        return jsonify({"error": f"Client '{name}' not found"}), 404

    progress = db.get_progress(name)

    try:
        pdf_bytes = build_client_report(client, progress)
    except Exception as e:
        # Never leak stack traces to the client
        app.logger.exception("PDF generation failed")
        return jsonify({"error": f"PDF generation failed: {e}"}), 500

    buffer = BytesIO(pdf_bytes)
    buffer.seek(0)

    download = request.args.get("download") == "1"
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=download,
        download_name=f"{name}_report.pdf" if download else None,
    )


# ---------------------------------------------------------------------------
# Bonus: a tiny HTML demo page so graders can click a button
# ---------------------------------------------------------------------------

@app.route("/demo/<name>")
def demo(name):
    """Simple HTML preview of the PDF — useful for screenshots."""
    return f"""
    <!doctype html>
    <html>
      <head><title>ACEest Report Preview</title></head>
      <body style="font-family:sans-serif;background:#1a1a1a;color:#fff;
                   text-align:center;padding:40px;">
        <h1 style="color:#d4af37;">ACEest Report Preview</h1>
        <p>Client: <b>{name}</b></p>
        <iframe src="/clients/{name}/report.pdf"
                width="800" height="600"
                style="border:2px solid #d4af37;"></iframe>
        <p><a href="/clients/{name}/report.pdf?download=1"
              style="color:#d4af37;">Download PDF</a></p>
      </body>
    </html>
    """


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # host=0.0.0.0 so Docker can expose it outside the container
    app.run(host="0.0.0.0", port=5000, debug=False)
