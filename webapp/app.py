"""
Project AD — Web console (Flask)
================================
Wraps the generator as a project-based tool. Key features:
  - Add project: enter brand data (colors, identity, agenda, products, target
    interest), upload logo / product cutout / reference ads -> generates a
    personalized minimal poster.
  - View past projects: gallery of projects + per-project detail and regenerate.

Run:
    pip install -r requirements.txt        # includes flask
    python3 webapp/app.py                  # http://localhost:5000
Storage is local: webapp/projects.db (SQLite) + webapp/uploads + webapp/generated.
"""
import os
import sys
import json
import uuid
import sqlite3
import datetime

from flask import (Flask, request, redirect, url_for, render_template,
                   send_from_directory, abort)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generator          # webapp/generator.py
import reference_style    # repo-root module (path added by generator import)

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE, "projects.db")
UPLOADS = os.path.join(BASE, "uploads")
GENERATED = os.path.join(BASE, "generated")
os.makedirs(UPLOADS, exist_ok=True)
os.makedirs(GENERATED, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024   # 16 MB upload cap

FIELDS = ["name", "brand_primary", "brand_secondary", "description", "identity",
          "brand_values", "agenda", "products", "target_interest", "headline", "subhead"]


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY, name TEXT, created_at TEXT, description TEXT,
        brand_primary TEXT, brand_secondary TEXT, brand_values TEXT, identity TEXT, agenda TEXT,
        products TEXT, target_interest TEXT, headline TEXT, subhead TEXT,
        logo_path TEXT, product_path TEXT, ref_ads TEXT, poster_path TEXT, hero_seed INTEGER)""")
    # Migrate older DBs that predate the wizard fields.
    for col in ("description", "brand_values"):
        try:
            con.execute(f"ALTER TABLE projects ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    con.commit()
    con.close()


init_db()


@app.route("/")
def index():
    con = db()
    projects = con.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    con.close()
    return render_template("index.html", projects=projects)


@app.route("/new")
def new():
    return render_template("new.html")


@app.route("/create", methods=["POST"])
def create():
    pid = uuid.uuid4().hex[:12]
    pdir = os.path.join(UPLOADS, pid)
    os.makedirs(pdir, exist_ok=True)

    def save_one(field, name):
        f = request.files.get(field)
        if f and f.filename:
            path = os.path.join(pdir, name + os.path.splitext(f.filename)[1])
            f.save(path)
            return path
        return None

    logo_path = save_one("logo", "logo")
    product_path = save_one("product", "product")
    ref_paths = []
    for f in request.files.getlist("ref_ads"):
        if f and f.filename:
            p = os.path.join(pdir, "ref_" + uuid.uuid4().hex[:6] + os.path.splitext(f.filename)[1])
            f.save(p)
            ref_paths.append(p)

    proj = {k: request.form.get(k, "") for k in FIELDS}
    proj.update({"logo_path": logo_path, "product_path": product_path, "ref_ads": ref_paths})
    proj["name"] = proj["name"] or "Untitled"
    proj["brand_primary"] = proj["brand_primary"] or "#00704A"

    poster = os.path.join(GENERATED, pid + ".png")
    _, seed = generator.generate_poster(proj, poster)

    con = db()
    con.execute(
        """INSERT INTO projects (id,name,created_at,description,brand_primary,brand_secondary,brand_values,
           identity,agenda,products,target_interest,headline,subhead,logo_path,product_path,ref_ads,poster_path,hero_seed)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pid, proj["name"], datetime.datetime.now().isoformat(timespec="seconds"), proj["description"],
         proj["brand_primary"], proj["brand_secondary"], proj["brand_values"], proj["identity"], proj["agenda"],
         proj["products"], proj["target_interest"], proj["headline"], proj["subhead"],
         logo_path, product_path, json.dumps(ref_paths), poster, seed))
    con.commit()
    con.close()
    return redirect(url_for("project", pid=pid))


@app.route("/project/<pid>")
def project(pid):
    con = db()
    row = con.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    con.close()
    if not row:
        abort(404)
    refs = json.loads(row["ref_ads"] or "[]")
    style = reference_style.analyze_references([r for r in refs if r and os.path.exists(r)]) if refs else None
    return render_template("project.html", p=row, ref_ads=refs, style=style)


@app.route("/regenerate/<pid>", methods=["POST"])
def regenerate(pid):
    con = db()
    row = con.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not row:
        con.close()
        abort(404)
    poster = os.path.join(GENERATED, pid + ".png")
    _, seed = generator.generate_poster(dict(row), poster)   # new random seed -> new design
    con.execute("UPDATE projects SET hero_seed=? WHERE id=?", (seed, pid))
    con.commit()
    con.close()
    return redirect(url_for("project", pid=pid))


@app.route("/generated/<pid>.png")
def generated(pid):
    return send_from_directory(GENERATED, pid + ".png")


@app.route("/file")
def file():
    """Serve an uploaded asset, restricted to the uploads directory."""
    path = os.path.abspath(request.args.get("p", ""))
    if not path.startswith(os.path.abspath(UPLOADS)) or not os.path.exists(path):
        abort(404)
    return send_from_directory(os.path.dirname(path), os.path.basename(path))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
