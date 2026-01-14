import schedule
import time
import threading
import logging
from utils.job_checker import check_scheduled_jobs

logger = logging.getLogger(__name__)


def run_job_checker():
    """Wrapper for job checker with error handling"""
    try:
        logger.info("Running scheduled job check...")
        check_scheduled_jobs()
    except Exception as e:
        logger.error(f"Scheduled job check failed: {str(e)}", exc_info=True)


def start_scheduler():
    """Start the background scheduler"""
    # Run job checker every 5 minutes
    schedule.every(5).minutes.do(run_job_checker)
    
    def run_continuously():
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    # Run in background thread
    scheduler_thread = threading.Thread(target=run_continuously, daemon=True)
    scheduler_thread.start()
    logger.info("✅ Job scheduler started (checking every 5 minutes)")