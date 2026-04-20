from dotenv import load_dotenv
from flask import Flask, g, request
from flask_cors import CORS
from routes.upload_post import upload_bp
from routes.openrouter import openrouter_bp
from routes.spoof import spoof_bp
from routes.job_checker import job_checker_bp
from routes.telegram import telegram_bp
from internal.video import video_bp
from internal.account import account_bp
from internal.group import group_bp
import logging
import time
from logging_config import init_logging, new_request_id, set_request_id, set_user_id
from scheduler import start_scheduler
import os

init_logging("uploader")
logger = logging.getLogger(__name__)

load_dotenv()

SERVER_URL = os.getenv('SERVER_URL', '')

app = Flask(__name__)
CORS(app)


@app.before_request
def _attach_request_context():
    rid = request.headers.get("X-Request-ID") or new_request_id()
    set_request_id(rid)
    set_user_id(request.headers.get("X-User-ID", ""))
    g._request_id = rid
    g._request_start = time.perf_counter()


@app.after_request
def _log_and_release_context(response):
    rid = getattr(g, "_request_id", "")
    start = getattr(g, "_request_start", None)
    elapsed_ms = int((time.perf_counter() - start) * 1000) if start else 0
    logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "latency_ms": elapsed_ms,
        },
    )
    if rid:
        response.headers["X-Request-ID"] = rid
    set_request_id("")
    set_user_id("")
    return response

app.register_blueprint(upload_bp)
app.register_blueprint(openrouter_bp)
app.register_blueprint(video_bp)
app.register_blueprint(account_bp)
app.register_blueprint(group_bp)
app.register_blueprint(spoof_bp)
app.register_blueprint(job_checker_bp)
app.register_blueprint(telegram_bp)

if __name__ == '__main__':
    # Local dev only. In production the systemd unit runs
    # `gunicorn -c gunicorn.conf.py app:app` — the `when_ready` hook in
    # gunicorn.conf.py starts the scheduler in the master process so it
    # only runs once regardless of worker count.
    start_scheduler()
    app.run(host='127.0.0.1', port=9000, debug=False)
