from datetime import datetime
from io import BytesIO
from typing import Dict

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from sqlalchemy.exc import SQLAlchemyError

import auth
from database import delete_prediction_for_user, get_prediction_for_user, list_predictions_for_user


history_bp = Blueprint("history", __name__)


@history_bp.route("/history", methods=["GET"])
@auth.login_required
def history_index():
    """Display prediction history with pagination and server-side filtering."""
    query = _query_from_request(request.args)

    try:
        history_result = list_predictions_for_user(
            int(g.user["id"]),
            page=query["page"],
            limit=query["limit"],
            date_from=query["date_from"],
            date_to=query["date_to"],
            search=query["search"],
        )
    except SQLAlchemyError as exc:
        current_app.logger.error("Failed to load history page: %s", exc, exc_info=True)
        if _wants_json():
            return jsonify({"error": "Failed to load history"}), 500
        flash("Unable to load prediction history right now.", "danger")
        return render_template(
            "history.html",
            predictions=[],
            pagination={"page": 1, "limit": query["limit"], "total": 0, "total_pages": 1, "has_prev": False, "has_next": False},
            active_filters=_filter_values(query),
            prev_page_url=None,
            next_page_url=None,
        ), 500

    predictions = history_result["data"]
    pagination = history_result["pagination"]

    if _wants_json():
        return jsonify({"data": predictions, "pagination": pagination})

    active_filters = _filter_values(query)
    prev_page_url = None
    next_page_url = None

    if pagination.get("has_prev"):
        prev_page_url = url_for(
            "history.history_index",
            page=pagination["page"] - 1,
            **_query_without_page(active_filters),
        )

    if pagination.get("has_next"):
        next_page_url = url_for(
            "history.history_index",
            page=pagination["page"] + 1,
            **_query_without_page(active_filters),
        )

    return render_template(
        "history.html",
        predictions=predictions,
        pagination=pagination,
        active_filters=active_filters,
        prev_page_url=prev_page_url,
        next_page_url=next_page_url,
    )


@history_bp.route("/history/<int:prediction_id>", methods=["GET"])
@auth.login_required
def history_detail(prediction_id: int):
    """View details of one prediction record owned by current user."""
    prediction = get_prediction_for_user(int(g.user["id"]), prediction_id)
    if prediction is None:
        if _wants_json():
            return jsonify({"error": "Prediction not found"}), 404
        abort(404)

    if _wants_json():
        return jsonify(prediction)

    return render_template("history_detail.html", prediction=prediction)


@history_bp.route("/history/<int:prediction_id>/pdf", methods=["GET", "POST"])
@auth.login_required
def generate_prediction_report(prediction_id: int):
    """Generate PDF report on demand for one prediction."""
    prediction = get_prediction_for_user(int(g.user["id"]), prediction_id)
    if prediction is None:
        if _wants_json():
            return jsonify({"error": "Prediction not found"}), 404
        abort(404)

    try:
        output_json = prediction.get("output_json") or {}
        html = render_template(
            "pdf/results_full_report.html",
            data=output_json.get("inference_rows", []),
            decision_summary=output_json.get("decision_summary"),
            alex_guidance=output_json.get("alex_guidance"),
            patient_data=prediction.get("input_json") or {},
            prediction_id=prediction.get("id"),
            generated_at=datetime.utcnow(),
            prediction=prediction,
        )

        pdf_bytes = _render_pdf_bytes(html)
        created_at = prediction.get("created_at")
        date_fragment = (
            created_at.strftime("%Y%m%d")
            if created_at is not None
            else datetime.utcnow().strftime("%Y%m%d")
        )

        should_download = request.method == "POST" or request.args.get("download") == "1"
        return send_file(
            BytesIO(pdf_bytes),
            as_attachment=should_download,
            download_name=f"prediction_{prediction['id']}_{date_fragment}.pdf",
            mimetype="application/pdf",
        )
    except Exception as exc:
        current_app.logger.error("Failed to generate PDF for prediction %s: %s", prediction_id, exc, exc_info=True)
        if _wants_json():
            return jsonify({"error": "Failed to generate PDF"}), 500
        flash("Unable to generate PDF right now.", "danger")
        return redirect(url_for("history.history_detail", prediction_id=prediction_id))


@history_bp.route("/history/<int:prediction_id>/delete", methods=["POST"])
@auth.login_required
def delete_prediction(prediction_id: int):
    """Delete one prediction owned by current user."""
    try:
        deleted = delete_prediction_for_user(int(g.user["id"]), prediction_id)
    except SQLAlchemyError as exc:
        current_app.logger.error("Failed to delete prediction %s: %s", prediction_id, exc, exc_info=True)
        if _wants_json():
            return jsonify({"error": "Failed to delete prediction"}), 500
        flash("Unable to delete prediction right now.", "danger")
        return redirect(url_for("history.history_index"))

    if not deleted:
        if _wants_json():
            return jsonify({"error": "Prediction not found"}), 404
        flash("Prediction not found.", "warning")
        return redirect(url_for("history.history_index"))

    if _wants_json():
        return jsonify({"ok": True, "prediction_id": prediction_id})

    flash(f"Prediction #{prediction_id} deleted.", "success")
    return redirect(url_for("history.history_index"))


def _render_pdf_bytes(html: str) -> bytes:
    """Render PDF bytes from HTML using WeasyPrint with xhtml2pdf fallback."""
    try:
        from weasyprint import HTML

        return HTML(string=html, base_url=current_app.root_path).write_pdf()
    except Exception as weasy_exc:
        current_app.logger.warning("WeasyPrint failed, trying xhtml2pdf fallback: %s", weasy_exc)

    try:
        from xhtml2pdf import pisa

        out = BytesIO()
        result = pisa.CreatePDF(src=html, dest=out)
        if result.err:
            raise RuntimeError("xhtml2pdf failed to render document")
        return out.getvalue()
    except Exception as fallback_exc:
        raise RuntimeError(
            "PDF rendering failed in both WeasyPrint and xhtml2pdf backends. "
            "Install GTK/Pango/Cairo for WeasyPrint or ensure xhtml2pdf is installed."
        ) from fallback_exc


def _query_from_request(args) -> Dict[str, object]:
    return {
        "page": _safe_int(args.get("page"), 1),
        "limit": _safe_int(args.get("limit"), 10),
        "date_from": (args.get("date_from") or "").strip() or None,
        "date_to": (args.get("date_to") or "").strip() or None,
        "search": (args.get("search") or "").strip() or None,
    }


def _safe_int(raw_value, fallback: int) -> int:
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return fallback


def _filter_values(query: Dict[str, object]) -> Dict[str, str]:
    return {
        "page": str(query["page"]),
        "limit": str(query["limit"]),
        "date_from": str(query["date_from"] or ""),
        "date_to": str(query["date_to"] or ""),
        "search": str(query["search"] or ""),
    }


def _query_without_page(active_filters: Dict[str, str]) -> Dict[str, str]:
    return {
        key: value
        for key, value in active_filters.items()
        if key != "page" and value not in (None, "")
    }


def _wants_json() -> bool:
    if request.args.get("format") == "json":
        return True
    best = request.accept_mimetypes.best
    return best == "application/json"
