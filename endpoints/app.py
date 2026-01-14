from dotenv import load_dotenv
from flask import Flask
from flask_cors import CORS
from routes.upload_post import upload_bp
from routes.openrouter import openrouter_bp
from routes.spoof import spoof_bp
from routes.job_checker import job_checker_bp
from internal.video import video_bp
from internal.account import account_bp
from internal.group import group_bp
import logging
from scheduler import start_scheduler
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

load_dotenv()

SERVER_URL = os.getenv('SERVER_URL', '')

app = Flask(__name__)
CORS(app)

app.register_blueprint(upload_bp)
app.register_blueprint(openrouter_bp)
app.register_blueprint(video_bp)
app.register_blueprint(account_bp)
app.register_blueprint(group_bp)
app.register_blueprint(spoof_bp)
app.register_blueprint(job_checker_bp)

if __name__ == '__main__':
    start_scheduler()

    # Using Nginx for SSL
    app.run(host='127.0.0.1', port=9000, debug=False)
