import requests
from .determine_time import utc_to_cet


def format_warnings(warnings: list) -> str:
    """Format warnings for Telegram display"""
    if not warnings:
        return ''
    
    warning_lines = []
    for warning in warnings:
        platform = warning.get('platform', 'Unknown').upper()
        message = warning.get('message', 'Unknown warning')
        hashtags = warning.get('hashtags', [])
        
        if hashtags:
            hashtags_str = ', '.join([f'#{h}' for h in hashtags])
            warning_lines.append(f"⚠️ {platform}: {message}\n   → {hashtags_str}")
        else:
            warning_lines.append(f"⚠️ {platform}: {message}")
    
    return '\n\n' + '\n'.join(warning_lines)


def response_formatting(response: requests.Response) -> str:
    try:
        result = response.json()
    except Exception:
        return f'❌ Error: HTTP {response.status_code}'
    
    # Extract warnings
    warnings = result.get('warnings', [])
    warnings_text = format_warnings(warnings)
    
    if response.status_code in [200, 202, 207]:
        # Check if this is a scheduled upload
        if result.get('scheduled') or (result.get('job_id') and result.get('scheduled_date')):
            scheduled_date = result.get('scheduled_date', 'Unknown')
            scheduled_date = utc_to_cet(scheduled_date)
            return f"📅 Scheduled!\n\nWill be posted at: {scheduled_date}{warnings_text}"
        
        # Check if this is an async background upload
        if result.get('async') or result.get('request_id'):
            total_platforms = result.get('total_platforms', 0)
            return (
                f"⏳ Upload Processing\n\n"
                f"Platforms: {total_platforms}\n"
                f"Status: Processing in background\n\n"
                f"Your upload is being processed asynchronously.\n"
                f"You'll be notified when complete!"
                f"{warnings_text}"
            )
        
        # Parse platform results from upload-post response
        platform_results = result.get('results', {})
        succeeded_platforms = []
        failed_platforms = []
        
        for platform, platform_result in platform_results.items():
            if platform_result.get('success'):
                url = platform_result.get('url', 'No URL')
                succeeded_platforms.append({
                    'platform': platform,
                    'url': url
                })
            else:
                error = platform_result.get('error', 'Unknown error')
                failed_platforms.append({
                    'platform': platform,
                    'error': error
                })
        
        # Format response
        if failed_platforms and succeeded_platforms:
            success_list = '\n'.join([
                f"  • {s['platform'].upper()}: {s['url']}"
                for s in succeeded_platforms
            ])
            failed_list = '\n'.join([
                f"  • {f['platform'].upper()}: {f['error']}"
                for f in failed_platforms
            ])
            return f"⚠️ Partial Upload\n\n✅ Succeeded:\n{success_list}\n\n❌ Failed:\n{failed_list}{warnings_text}"
        
        elif succeeded_platforms:
            success_list = '\n'.join([
                f"  • {s['platform'].upper()}: {s['url']}"
                for s in succeeded_platforms
            ])
            return f"✅ Uploaded!\n\n{success_list}{warnings_text}"
        
        elif failed_platforms:
            failed_list = '\n'.join([
                f"  • {f['platform'].upper()}: {f['error']}"
                for f in failed_platforms
            ])
            return f"❌ All uploads failed:\n\n{failed_list}{warnings_text}"
        
        else:
            if result.get('message') and 'background' in result.get('message', '').lower():
                return (
                    "⏳ Upload Processing\n\n"
                    "Status: Processing in background\n\n"
                    "Your upload is being processed asynchronously.\n"
                    "You'll be notified when complete!"
                    f"{warnings_text}"
                )
            else:
                return f"⚠️ Unknown response format{warnings_text}"
    
    else:
        error_msg = result.get('error', 'Unknown error')
        details = result.get('details', '')
        return f"❌ Error (HTTP {response.status_code}):\n{error_msg}\n{details}{warnings_text}"