from flask import Blueprint, jsonify, current_app, request
from sqlalchemy import text, create_engine
from ...modules.auth.decorators import basic_auth_required

pull_bp = Blueprint("pull_api", __name__)
_engine = None

def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(current_app.config["PULL_API_TARGET_DB_URI"])
    return _engine

@pull_bp.route("/clients", methods=["GET"])
@basic_auth_required
def clients():
    """
    Get one or many client_v2 rows
    ---
    tags: 
      - client
    security:
      - basicAuth: []
    parameters:
      - name: ids
        in: query
        type: array
        items: 
          type: string
        collectionFormat: csv
        description: Comma-separated list of client IDs. Omit to fetch by other filters.
      - name: simprintsId
        in: query
        type: array
        items: 
          type: string
        collectionFormat: csv
        description: Comma-separated list of simprints IDs.
      - name: empty_subjectActions
        in: query
        type: boolean
        description: "true => rows where subjectActions is NULL or empty"
      - name: empty_simprintsId
        in: query
        type: boolean
        description: "true => rows where simprintsId is NULL or empty"
    responses:
      200:
        description: Array of client objects
        schema:
          type: array
          items: 
            $ref: '#/definitions/Client'
      401:
        description: Unauthorized
    """
    ids          = request.args.get("ids")
    simprint_ids = request.args.get("simprintsId")

    empty_sa     = (request.args.get("empty_subjectActions") or "").lower()
    empty_simp   = (request.args.get("empty_simprintsId") or "").lower()

    clauses, params = [], {}

    # Handle id and simprintsId filters using OR
    or_clauses = []
    if ids:
        id_list = [i.strip() for i in ids.split(",")]
        or_clauses.append("id = ANY(:ids)")
        params["ids"] = id_list

    if simprint_ids:
        simp_list = [s.strip() for s in simprint_ids.split(",")]
        or_clauses.append("\"simprintsId\" = ANY(:simprints_ids)")
        params["simprints_ids"] = simp_list

    if or_clauses:
        clauses.append(f"({' OR '.join(or_clauses)})")

    # Handle subjectActions filter
    if empty_sa == "true":
        clauses.append("(\"subjectActions\" IS NULL OR \"subjectActions\" = '')")
    elif empty_sa == "false":
        clauses.append("(\"subjectActions\" IS NOT NULL AND \"subjectActions\" != '')")

    # Handle simprintsId empty filter
    if empty_simp == "true":
        clauses.append("(\"simprintsId\" IS NULL OR \"simprintsId\" = '')")
    elif empty_simp == "false":
        clauses.append("(\"simprintsId\" IS NOT NULL AND \"simprintsId\" != '')")

    where = " AND ".join(clauses) if clauses else "TRUE"
    sql = f'SELECT "simprintsId", id, "subjectActions" FROM client_v2 WHERE {where}'

    with engine().connect() as conn:
        rows = conn.execute(text(sql), params).fetchall()

    return jsonify([dict(r._mapping) for r in rows]) if rows else ("Not found", 404)

@pull_bp.route("/biometric_identity/<string:bio_id>", methods=["GET"])
@basic_auth_required
def biometric_identity(bio_id):
    """
    Get one biometric_identity row
    ---
    tags: 
      - biometric_identity
    security:
      - basicAuth: []
    parameters:
      - name: bio_id
        in: path
        required: true
        type: string
        description: The biometric identity ID
    responses:
      200:
        description: A biometric_identity object
        schema: 
          $ref: '#/definitions/BiometricIdentity'
      404:
        description: Not found
      401:
        description: Unauthorized
    """
    sql = "SELECT * FROM biometric_identity WHERE id=:id"
    with engine().connect() as conn:
        row = conn.execute(text(sql), {"id": bio_id}).fetchone()

    return jsonify(dict(row._mapping)) if row else ("Not found", 404)
