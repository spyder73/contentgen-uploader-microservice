from datetime import datetime, timedelta
import random
import pytz


def parse_iso_datetime(dt_string):
    """Parse ISO datetime string to timezone-aware datetime"""
    if dt_string.endswith('Z'):
        return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
    elif '+' in dt_string or dt_string.count('-') > 2:
        return datetime.fromisoformat(dt_string)
    else:
        return datetime.fromisoformat(dt_string).replace(tzinfo=pytz.UTC)


def calculate_next_upload_time(account):
    """
    Calculate the next optimal upload time for an account.
    """
    autopost = account.get('autoposting_properties', {})
    
    if not autopost.get('enabled'):
        raise ValueError("Autoposting not enabled for this account")
    
    cet = pytz.timezone('Europe/Berlin')
    now = datetime.now(cet)
    
    # Determine the base time to calculate from
    base_time_dt = now
    
    # Get scheduled times and find the latest one
    scheduled_times = account.get('scheduled_times', [])
    if scheduled_times:
        # Parse all times and find the max
        parsed_times = [parse_iso_datetime(t) for t in scheduled_times]
        latest_scheduled_dt = max(parsed_times)
        base_time_dt = latest_scheduled_dt.astimezone(cet)
    else:
        # Fall back to last_upload_time
        last_upload = account.get('last_upload_time')
        if last_upload:
            last_upload_dt = parse_iso_datetime(last_upload).astimezone(cet)
            base_time_dt = last_upload_dt
    
    # Ensure base_time is not in the past
    if base_time_dt < now:
        base_time_dt = now
    
    # Get daily posts
    daily_posts = autopost.get('daily_posts', {})
    
    # For now we just take the minimum of the specified platforms
    total_daily_posts = min(daily_posts.values()) if daily_posts else 10
    
    # Calculate interval
    downtime_hours = autopost.get('downtime_hours', 8)
    active_hours = 24 - downtime_hours
    minutes_per_post = (active_hours * 60) / total_daily_posts
    
    # Add random fluctuation (±20%)
    fluctuation = random.uniform(-0.2, 0.2)
    minutes_until_next = minutes_per_post * (1 + fluctuation)
    
    # Calculate next upload time
    next_upload = base_time_dt + timedelta(minutes=minutes_until_next)
    
    # Check downtime
    downtime_start_str = autopost.get('downtime_start')
    downtime_end_str = autopost.get('downtime_end')
    
    if downtime_start_str and downtime_end_str:
        next_upload = _avoid_downtime(next_upload, downtime_start_str, downtime_end_str, cet)
    
    # Convert to UTC
    next_upload_utc = next_upload.astimezone(pytz.UTC)
    return next_upload_utc.strftime('%Y-%m-%dT%H:%M:%SZ')


def _avoid_downtime(upload_time, downtime_start, downtime_end, timezone):
    """Check if upload_time falls in downtime window and adjust if needed"""
    start_hour, start_min = map(int, downtime_start.split(':'))
    end_hour, end_min = map(int, downtime_end.split(':'))
    
    upload_date = upload_time.date()
    downtime_start_dt = timezone.localize(datetime.combine(upload_date, datetime.min.time().replace(hour=start_hour, minute=start_min)))
    downtime_end_dt = timezone.localize(datetime.combine(upload_date, datetime.min.time().replace(hour=end_hour, minute=end_min)))
    
    # Handle overnight downtime
    if downtime_end_dt < downtime_start_dt:
        downtime_end_dt += timedelta(days=1)
    
    if downtime_start_dt <= upload_time < downtime_end_dt:
        random_delay = random.randint(5, 30)
        upload_time = downtime_end_dt + timedelta(minutes=random_delay)
    elif upload_time < downtime_start_dt:
        prev_downtime_start = downtime_start_dt - timedelta(days=1)
        prev_downtime_end = downtime_end_dt - timedelta(days=1)
        
        if prev_downtime_start <= upload_time < prev_downtime_end:
            random_delay = random.randint(5, 30)
            upload_time = prev_downtime_end + timedelta(minutes=random_delay)
    
    return upload_time


def cet_to_utc(cet_time_str):
    """Convert CET time string to UTC"""
    cet = pytz.timezone('Europe/Berlin')
    naive_dt = datetime.fromisoformat(cet_time_str.replace('Z', ''))
    cet_dt = cet.localize(naive_dt)
    utc_dt = cet_dt.astimezone(pytz.UTC)
    return utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def utc_to_cet(utc_time_str):
    """Convert UTC time string to CET"""
    cet = pytz.timezone('Europe/Berlin')
    utc_dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
    cet_dt = utc_dt.astimezone(cet)
    return cet_dt.strftime('%Y-%m-%dT%H:%M:%S')