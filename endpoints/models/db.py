import sqlite3
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv('DB_PATH', 'data.db')


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Initialize database
def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            caption TEXT NOT NULL,
            user_id TEXT NOT NULL,
            status TEXT DEFAULT 'available',
            reusable INTEGER DEFAULT 0,
            created_at TEXT,
            scheduled_at TEXT,
            posted_at TEXT,
            post_url TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            platforms TEXT NOT NULL,
            created_at TEXT,
            is_ai INTEGER DEFAULT 0,
            autoposting_properties TEXT,
            last_upload_time TEXT,
            scheduled_times TEXT,
            next_upload_time TEXT,
            UNIQUE(user_id, username)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            group_name TEXT NOT NULL,
            account_usernames TEXT NOT NULL,
            created_at TEXT,
            UNIQUE(user_id, group_name)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL,
            video_id TEXT NOT NULL,
            added_at TEXT,
            FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE,
            UNIQUE(group_id, video_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT UNIQUE NOT NULL,
            video_id TEXT NOT NULL,
            account_username TEXT NOT NULL,
            user_id TEXT NOT NULL,
            scheduled_date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            is_async INTEGER DEFAULT 0,
            platform_post_url TEXT,
            created_at TEXT,
            completed_at TEXT
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ SQLite database initialized at", DB_PATH)


# Initialize on import
init_db()


def create_video(video_id, caption, user_id, status='available', reusable=False):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO videos (video_id, caption, user_id, status, reusable, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (video_id, caption, user_id, status, 1 if reusable else 0, datetime.utcnow().isoformat()))

        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_videos(user_id, status=None):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if status:
            cursor.execute('SELECT * FROM videos WHERE user_id = ? AND status = ? ORDER BY created_at DESC', (user_id, status))
        else:
            cursor.execute('SELECT * FROM videos WHERE user_id = ? ORDER BY created_at DESC', (user_id,))

        rows = cursor.fetchall()
        videos = []
        for row in rows:
            video = dict(row)
            video['_id'] = video['video_id']
            video['reusable'] = bool(video.get('reusable', 0))
            videos.append(video)

        return videos
    finally:
        conn.close()


def get_video_by_id(video_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM videos WHERE video_id = ?', (video_id,))
        row = cursor.fetchone()

        if row:
            video = dict(row)
            video['_id'] = video['video_id']
            video['reusable'] = bool(video.get('reusable', 0))
            return video
        return None
    finally:
        conn.close()


def update_video_status(video_id, status, scheduled_at=None, post_url=None):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if scheduled_at:
            if isinstance(scheduled_at, datetime):
                scheduled_at = scheduled_at.isoformat()
            cursor.execute('''
                UPDATE videos 
                SET status = ?, scheduled_at = ?, post_url = ?
                WHERE video_id = ?
            ''', (status, scheduled_at, post_url, video_id))
        else:
            cursor.execute('''
                UPDATE videos 
                SET status = ?, post_url = ?
                WHERE video_id = ?
            ''', (status, post_url, video_id))

        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
        

def update_video_post_url(video_id, post_url):
    """Update the post URL for a video"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            UPDATE videos 
            SET post_url = ?, posted_at = ?
            WHERE video_id = ?
        ''', (post_url, datetime.utcnow().isoformat(), video_id))

        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()

def create_account(user_id, username, platforms, is_ai=False, autoposting_properties=None):
    """
    Create account with autoposting properties.
    autoposting_properties structure:
    {
        'enabled': False,
        'posting_frequency': 'daily',  # 'hourly', 'daily', 'weekly'
        'daily_posts': {'tiktok': 10, 'instagram': 5},
        'downtime_hours': 8,  # Duration of downtime window
        'downtime_start': '22:30',  # Fixed HH:MM in CET
        'downtime_end': '06:30',  # Fixed HH:MM in CET
    }
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        platforms_json = json.dumps(platforms)
        
        # Default autoposting properties
        if autoposting_properties is None:
            autoposting_properties = {
                'enabled': False
            }
        
        autoposting_json = json.dumps(autoposting_properties)

        # here we set next_upload_time to NOW, because then the auto-schedule
        # route will upload immediately, and after upload the last_upload_time will also be set
        cursor.execute('''
            INSERT INTO accounts (user_id, username, platforms, created_at, is_ai, autoposting_properties, next_upload_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, platforms_json, datetime.utcnow().isoformat(), 1 if is_ai else 0, autoposting_json, datetime.utcnow().isoformat()))

        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def update_account_autoposting(user_id, username, autoposting_properties):
    """
    Update autoposting properties for an account
    
    Example usage:
    update_account_autoposting(user_id, username, {
        'enabled': True,
        'posting_frequency': 'daily',
        'daily_posts': 3,
        'last_upload_time': datetime.utcnow().isoformat()
    })
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        autoposting_json = json.dumps(autoposting_properties)
        
        cursor.execute('''
            UPDATE accounts
            SET autoposting_properties = ?
            WHERE user_id = ? AND username = ?
        ''', (autoposting_json, user_id, username))

        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_accounts(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM accounts WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        rows = cursor.fetchall()

        accounts = []
        for row in rows:
            account = dict(row)
            account['platforms'] = json.loads(account['platforms'])
            account['is_ai'] = bool(account['is_ai'])
            
            # Parse autoposting_properties
            if account.get('autoposting_properties'):
                account['autoposting_properties'] = json.loads(account['autoposting_properties'])
            else:
                account['autoposting_properties'] = {'enabled': False}
            
            if account.get('scheduled_times'):
                account['scheduled_times'] = json.loads(account['scheduled_times'])
            else:
                account['scheduled_times'] = []
            
            account['_id'] = str(account['id'])
            accounts.append(account)

        return accounts
    finally:
        conn.close()
        
        
def update_account(user_id, username, is_ai=None, autoposting_properties=None, platforms=None):
    """
    Update account settings
    Only updates fields that are not None
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        updates = []
        params = []
        
        if is_ai is not None:
            updates.append('is_ai = ?')
            params.append(1 if is_ai else 0)
        
        if autoposting_properties is not None:
            updates.append('autoposting_properties = ?')
            params.append(json.dumps(autoposting_properties))
            
        if platforms is not None:  # ADD THIS BLOCK
            updates.append('platforms = ?')
            params.append(json.dumps(platforms))
        
        if not updates:
            return 0
        
        params.extend([user_id, username])
        
        query = f'''
            UPDATE accounts
            SET {', '.join(updates)}
            WHERE user_id = ? AND username = ?
        '''
        
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
        
def update_account_last_upload_time(user_id, username, upload_time):
    """Update the last_upload_time column directly"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            UPDATE accounts 
            SET last_upload_time = ?
            WHERE user_id = ? AND username = ?
        ''', (upload_time, user_id, username))

        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_account_by_username(user_id, username):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM accounts WHERE user_id = ? AND username = ?', (user_id, username))
        row = cursor.fetchone()

        if row:
            account = dict(row)
            account['platforms'] = json.loads(account['platforms'])
            account['is_ai'] = bool(account['is_ai'])
            
            # Parse autoposting_properties
            if account.get('autoposting_properties'):
                account['autoposting_properties'] = json.loads(account['autoposting_properties'])
            else:
                account['autoposting_properties'] = {'enabled': False}
                
            if account.get('scheduled_times'):
                account['scheduled_times'] = json.loads(account['scheduled_times'])
            else:
                account['scheduled_times'] = []
            
            account['next_upload_time'] = account.get('next_upload_time')
            
            account['_id'] = str(account['id'])
            return account

        return None
    finally:
        conn.close()


def get_accounts_with_autoposting(user_id=None):
    """Get all accounts with autoposting enabled"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if user_id:
            cursor.execute('SELECT * FROM accounts WHERE user_id = ?', (user_id,))
        else:
            cursor.execute('SELECT * FROM accounts')
        
        rows = cursor.fetchall()

        accounts = []
        for row in rows:
            account = dict(row)
            account['platforms'] = json.loads(account['platforms'])
            account['is_ai'] = bool(account['is_ai'])
            
            if account.get('autoposting_properties'):
                autoposting = json.loads(account['autoposting_properties'])
                account['autoposting_properties'] = autoposting
                
                # Only include if autoposting is enabled
                if autoposting.get('enabled'):
                    account['_id'] = str(account['id'])
                    accounts.append(account)

        return accounts
    finally:
        conn.close()


def delete_account(user_id, username):
    """Delete an account by username"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('DELETE FROM accounts WHERE user_id = ? AND username = ?', (user_id, username))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()

# ===== SCHEDULING =====   

def get_scheduled_times(user_id, username):
    """Get all scheduled times for an account"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT scheduled_times FROM accounts WHERE user_id = ? AND username = ?', 
                      (user_id, username))
        row = cursor.fetchone()
        
        if row and row['scheduled_times']:
            return json.loads(row['scheduled_times'])
        return []
    finally:
        conn.close()
        
        
def add_scheduled_time(user_id, username, scheduled_time):
    """
    Add a scheduled time to the account's pending queue.
    Keeps the array sorted chronologically.
    
    Args:
        user_id: User ID
        username: Account username
        scheduled_time: ISO datetime string in UTC
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get current scheduled times
        cursor.execute('SELECT scheduled_times FROM accounts WHERE user_id = ? AND username = ?', 
                      (user_id, username))
        row = cursor.fetchone()
        
        if not row:
            return 0
        
        scheduled_times = json.loads(row['scheduled_times']) if row['scheduled_times'] else []
        
        # Add new time
        scheduled_times.append(scheduled_time)
        
        # Sort chronologically
        scheduled_times.sort()
        
        # Update
        cursor.execute('''
            UPDATE accounts 
            SET scheduled_times = ?
            WHERE user_id = ? AND username = ?
        ''', (json.dumps(scheduled_times), user_id, username))

        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def remove_scheduled_time(user_id, username, scheduled_time):
    """
    Remove a scheduled time when video is posted or cancelled.
    
    Args:
        user_id: User ID
        username: Account username
        scheduled_time: ISO datetime string in UTC
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT scheduled_times FROM accounts WHERE user_id = ? AND username = ?', 
                      (user_id, username))
        row = cursor.fetchone()
        
        if not row:
            return 0
        
        scheduled_times = json.loads(row['scheduled_times']) if row['scheduled_times'] else []
        
        # Remove the time
        if scheduled_time in scheduled_times:
            scheduled_times.remove(scheduled_time)
        
        # Update
        cursor.execute('''
            UPDATE accounts 
            SET scheduled_times = ?
            WHERE user_id = ? AND username = ?
        ''', (json.dumps(scheduled_times), user_id, username))

        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
        
        
def clear_old_scheduled_times(user_id, username):
    """
    Remove scheduled times that are in the past (already posted or missed).
    Should be called periodically by job_checker.
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT scheduled_times FROM accounts WHERE user_id = ? AND username = ?', 
                      (user_id, username))
        row = cursor.fetchone()
        
        if not row:
            return 0
        
        scheduled_times = json.loads(row['scheduled_times']) if row['scheduled_times'] else []
        
        # Filter out past times
        now = datetime.utcnow().isoformat()
        future_times = [t for t in scheduled_times if t > now]
        
        # Update
        cursor.execute('''
            UPDATE accounts 
            SET scheduled_times = ?
            WHERE user_id = ? AND username = ?
        ''', (json.dumps(future_times), user_id, username))

        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_next_upload_time(user_id, username):
    """Get the pre-calculated next upload time from DB"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT next_upload_time FROM accounts WHERE user_id = ? AND username = ?', 
                      (user_id, username))
        row = cursor.fetchone()
        
        if row:
            return row['next_upload_time']
        return None
    finally:
        conn.close()
        
def update_next_upload_time(user_id, username, next_upload_time):
    """Update the next upload time for an account"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            UPDATE accounts 
            SET next_upload_time = ?
            WHERE user_id = ? AND username = ?
        ''', (next_upload_time, user_id, username))

        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
        


# ===== GROUP MANAGEMENT =====

def create_group(user_id, group_name, account_usernames=None):
    """
    Create a new group
    
    Args:
        user_id: Telegram user ID
        group_name: Name of the group
        account_usernames: List of account usernames (optional)
    """
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if account_usernames is None:
            account_usernames = []
        
        usernames_json = json.dumps(account_usernames)
        
        cursor.execute('''
            INSERT INTO groups (user_id, group_name, account_usernames, created_at)
            VALUES (?, ?, ?, ?)
        ''', (user_id, group_name, usernames_json, datetime.utcnow().isoformat()))

        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_groups(user_id):
    """Get all groups for a user"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM groups WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
        rows = cursor.fetchall()

        groups = []
        for row in rows:
            group = dict(row)
            group['account_usernames'] = json.loads(group['account_usernames'])
            group['_id'] = str(group['id'])
            groups.append(group)

        return groups
    finally:
        conn.close()


def get_group_by_name(user_id, group_name):
    """Get a specific group by name"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT * FROM groups WHERE user_id = ? AND group_name = ?', (user_id, group_name))
        row = cursor.fetchone()

        if row:
            group = dict(row)
            group['account_usernames'] = json.loads(group['account_usernames'])
            group['_id'] = str(group['id'])
            return group
        return None
    finally:
        conn.close()


def add_accounts_to_group(user_id, group_name, account_usernames):
    """Add accounts to a group (append to existing)"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Get current accounts
        cursor.execute('SELECT account_usernames FROM groups WHERE user_id = ? AND group_name = ?', 
                      (user_id, group_name))
        row = cursor.fetchone()
        
        if not row:
            return 0
        
        current = json.loads(row['account_usernames'])
        
        # Add new accounts (avoid duplicates)
        for username in account_usernames:
            if username not in current:
                current.append(username)
        
        # Update
        cursor.execute('''
            UPDATE groups 
            SET account_usernames = ?
            WHERE user_id = ? AND group_name = ?
        ''', (json.dumps(current), user_id, group_name))

        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def delete_group(user_id, group_name):
    """Delete a group"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('DELETE FROM groups WHERE user_id = ? AND group_name = ?', (user_id, group_name))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# ===== GROUP VIDEOS =====

def add_video_to_group(group_id, video_id):
    """Add a video to a group"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO group_videos (group_id, video_id, added_at)
            VALUES (?, ?, ?)
        ''', (group_id, video_id, datetime.utcnow().isoformat()))

        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def get_group_videos(group_id):
    """Get all videos in a group"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT v.* FROM videos v
            INNER JOIN group_videos gv ON v.video_id = gv.video_id
            WHERE gv.group_id = ?
            ORDER BY gv.added_at DESC
        ''', (group_id,))
        
        rows = cursor.fetchall()
        videos = []
        for row in rows:
            video = dict(row)
            video['_id'] = video['video_id']
            video['reusable'] = bool(video.get('reusable', 0))
            videos.append(video)

        return videos
    finally:
        conn.close()


# ===== SCHEDULED JOBS =====

def create_scheduled_job(job_id, video_id, account_username, user_id, scheduled_date, is_async=False):
    """Track a scheduled job from upload-post"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT INTO scheduled_jobs (job_id, video_id, account_username, user_id, scheduled_date, is_async, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (job_id, video_id, account_username, user_id, scheduled_date, 1 if is_async else 0, datetime.utcnow().isoformat()))

        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


# Add helper functions to get jobs by type:
def get_pending_scheduled_jobs(user_id=None):
    """Get pending scheduled (non-async) jobs"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if user_id:
            cursor.execute('SELECT * FROM scheduled_jobs WHERE user_id = ? AND status = ? AND is_async = 0', (user_id, 'pending'))
        else:
            cursor.execute('SELECT * FROM scheduled_jobs WHERE status = ? AND is_async = 0', ('pending',))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_pending_async_jobs(user_id=None):
    """Get pending async jobs"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if user_id:
            cursor.execute('SELECT * FROM scheduled_jobs WHERE user_id = ? AND status = ? AND is_async = 1', (user_id, 'pending'))
        else:
            cursor.execute('SELECT * FROM scheduled_jobs WHERE status = ? AND is_async = 1', ('pending',))
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def update_job_status(job_id, status, platform_post_url=None):
    """Update job status when completed"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        if platform_post_url:
            cursor.execute('''
                UPDATE scheduled_jobs 
                SET status = ?, platform_post_url = ?, completed_at = ?
                WHERE job_id = ?
            ''', (status, platform_post_url, datetime.utcnow().isoformat(), job_id))
        else:
            cursor.execute('''
                UPDATE scheduled_jobs 
                SET status = ?, completed_at = ?
                WHERE job_id = ?
            ''', (status, datetime.utcnow().isoformat(), job_id))

        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()