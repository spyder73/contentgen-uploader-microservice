from datetime import datetime
import random
import pytz
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv('API_URL')
API_TOKEN = os.getenv('API_TOKEN')

def generate_downtime_window(downtime_hours):
    """
    Generate a random downtime window of specified duration
    Centered around 20:00 - 08:00 (CET) with ±1 hour randomness
    
    Args:
        downtime_hours (int): Duration of downtime in hours
        
    Returns:
        tuple: (downtime_start, downtime_end) in HH:MM format (CET times)
    """
    # Base center time: 02:00 (middle of 20:00-08:00)
    base_center_hour = 2
    
    # Add random offset (±1 hour)
    random_offset = random.uniform(-1, 1)
    center_hour = base_center_hour + random_offset
    
    # Calculate start and end
    half_duration = downtime_hours / 2
    start_hour = (center_hour - half_duration) % 24
    end_hour = (center_hour + half_duration) % 24
    
    # Add random minutes
    start_min = random.randint(0, 59)
    end_min = random.randint(0, 59)
    
    # Format as HH:MM (CET times)
    downtime_start = f"{int(start_hour):02d}:{start_min:02d}"
    downtime_end = f"{int(end_hour):02d}:{end_min:02d}"
    
    return downtime_start, downtime_end


def cet_to_utc(cet_time_str):
    """
    Convert CET time string to UTC
    
    Args:
        cet_time_str (str): Time in CET (e.g., '2025-11-18T17:30:00')
        
    Returns:
        str: Time in UTC ISO format (e.g., '2025-11-18T16:30:00Z')
    """
    cet = pytz.timezone('Europe/Berlin')
    # Parse as naive datetime, then localize to CET
    naive_dt = datetime.fromisoformat(cet_time_str.replace('Z', ''))
    cet_dt = cet.localize(naive_dt)
    # Convert to UTC
    utc_dt = cet_dt.astimezone(pytz.UTC)
    return utc_dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def utc_to_cet(utc_time_str):
    """
    Convert UTC time string to CET
    
    Args:
        utc_time_str (str): Time in UTC (e.g., '2025-11-18T16:30:00Z')
        
    Returns:
        str: Time in CET (e.g., '2025-11-18T17:30:00')
    """
    cet = pytz.timezone('Europe/Berlin')
    # Parse as UTC
    utc_dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
    # Convert to CET
    cet_dt = utc_dt.astimezone(cet)
    return cet_dt.strftime('%Y-%m-%dT%H:%M:%S')