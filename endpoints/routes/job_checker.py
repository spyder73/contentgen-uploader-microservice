from flask import Blueprint, jsonify
from auth import require_token
from utils.job_checker import check_scheduled_jobs
import logging

logger = logging.getLogger(__name__)

job_checker_bp = Blueprint('job_checker', __name__)


@job_checker_bp.route('/check-jobs', methods=['POST'])
@require_token
def check_jobs_endpoint():
    """
    Manually trigger job checker.
    This will be called by a cron job or scheduler.
    """
    try:
        check_scheduled_jobs()
        return jsonify({
            'success': True,
            'message': 'Job check completed'
        }), 200
        
    except Exception as e:
        logger.error(f"Job check failed: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500