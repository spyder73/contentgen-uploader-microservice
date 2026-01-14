import logging

logger = logging.getLogger(__name__)


def parse_upload_response(response):
    """
    Parse upload-post API response and determine success/failure status.
    Also extracts post URLs from successful uploads.
    
    Returns:
        tuple: (status_code, response_dict)
        - 200: Full success
        - 202: Scheduled
        - 207: Partial success/failure
        - 500: Complete failure
    """
    logger.info(f"parse_upload_response received: type={type(response)}, value={response}")
    
    # Extract warnings if present
    warnings = response.get('warnings', [])
    if warnings:
        logger.warning(f"Upload warnings: {warnings}")
    
    # Check if this is a scheduled upload (no results yet)
    if response.get('scheduled_date') and response.get('job_id'):
        logger.info(f"Scheduled upload with job_id: {response.get('job_id')}")
        return 202, {
            'success': True,
            'scheduled': True,
            'job_id': response.get('job_id'),
            'scheduled_date': response.get('scheduled_date'),
            'warnings': warnings
        }
    
    # Check if this is an async background upload
    if response.get('request_id') and response.get('message') and 'background' in response.get('message', '').lower():
        logger.info(f"Background upload with request_id: {response.get('request_id')}")
        return 200, {
            'success': True,
            'async': True,
            'request_id': response.get('request_id'),
            'total_platforms': response.get('total_platforms'),
            'message': response.get('message'),
            'warnings': warnings
        }
    
    # Regular upload - parse platform results
    platform_results = response.get('results', {})
    failed_platforms = []
    succeeded_platforms = []
    post_urls = {}
    
    for platform, result in platform_results.items():
        if result.get('success'):
            succeeded_platforms.append(platform)
            url = result.get('url', '')  
            if url:
                post_urls[platform] = url  
        else:
            error = result.get('error', 'Unknown error')
            failed_platforms.append({
                'platform': platform,
                'error': error
            })
    
    # Determine overall status
    if failed_platforms and not succeeded_platforms:
        logger.error(f"All platforms failed: {failed_platforms}")
        return 500, {
            'success': False,
            'error': response.get('error', 'Upload failed on all platforms'),
            'failed_platforms': failed_platforms,
            'warnings': warnings
        }
    
    elif failed_platforms:
        logger.warning(f"Partial upload success. Succeeded: {succeeded_platforms}, Failed: {failed_platforms}")
        return 207, {
            'success': True,
            'partial': True,
            'succeeded_platforms': succeeded_platforms,
            'failed_platforms': failed_platforms,
            'post_urls': post_urls,
            'warnings': warnings
        }
    
    else:
        logger.info(f"All platforms succeeded: {succeeded_platforms}")
        return 200, {
            'success': True,
            'uploaded': True,
            'succeeded_platforms': succeeded_platforms,
            'post_urls': post_urls,
            'warnings': warnings
        }

