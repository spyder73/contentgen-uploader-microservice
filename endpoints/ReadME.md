# Endpoints API

A Flask-based API server for managing social media video uploads, scheduling, and account management. Integrates with [Upload-Post](https://upload-post.com) for multi-platform video distribution.

## Overview

This API serves as the backend for the Piper social media automation system. It handles:

- **Video Uploads**: Direct and scheduled uploads to TikTok, Instagram, and other platforms
- **Auto-Scheduling**: Intelligent upload time calculation based on account settings
- **Job Tracking**: Monitor scheduled and async upload jobs
- **Account Management**: Store and manage social media account configurations
- **Video Library**: Track uploaded videos and their status

## Project Structure

```
endpoints/
├── app.py                 # Flask application entry point
├── auth.py                # Authentication middleware
├── scheduler.py           # APScheduler for periodic job checking
├── internal/              # Internal API routes (account, group, video management)
│   ├── account.py         # Account CRUD operations
│   ├── group.py           # Account grouping functionality
│   └── video.py           # Video library management
├── models/
│   └── db.py              # SQLite database models and queries
├── routes/
│   ├── upload_post.py     # Main upload endpoint
│   ├── job_checker.py     # Job status checking endpoint
│   ├── openrouter.py      # AI caption generation via OpenRouter
│   └── spoof.py           # Testing/mock endpoints
└── utils/
    ├── auto_schedule.py   # Auto-scheduling decorator and logic
    ├── determine_time.py  # Upload time calculation utilities
    ├── external_wrapper.py # Upload tracking decorator
    ├── job_checker.py     # Scheduled/async job monitoring
    ├── upload_handler.py  # Response parsing utilities
    └── json_parse.py      # JSON parsing helpers
```

## Installation

### Prerequisites

- Python 3.9+
- SQLite3
- Upload-Post API key

### Setup

1. **Install dependencies**:
   ```bash
   pip install flask python-dotenv apscheduler upload-post requests
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```

   Required variables:
   ```env
   API_TOKEN=your_api_token_here
   UPLOADPOST_API_KEY=your_uploadpost_api_key
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   OPENROUTER_API_KEY=your_openrouter_api_key
   ```

3. **Initialize the database**:
   ```bash
   python -c "from models.db import init_db; init_db()"
   ```

4. **Run the server**:
   ```bash
   python app.py
   ```

   Or with gunicorn:
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```

## API Endpoints

### Upload

#### `POST /upload-video`
Upload a video to social media platforms.

**Headers**:
- `Authorization: Bearer <API_TOKEN>`
- `X-Source: telegram` (optional, enables tracking)

**Form Data**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `video` | File | Yes | Video file to upload |
| `title` | String | Yes | Caption/title for the post |
| `user` | String | Yes | Account username |
| `user_id` | String | Yes | Telegram User ID, tied to the Account |
| `platforms` | JSON Array | Yes | Target platforms, e.g., `["tiktok", "instagram"]` |
| `video_id` | String | No | Video ID for tracking |
| `scheduled_date` | String | No | ISO 8601 date or `"auto"` for auto-scheduling, requires autoposting to be true in Telegram account settings |
| `params` | JSON Object | No | Additional parameters (e.g., `{"is_aigc": true}`) |

**Response Codes**:
- `200` - Immediate upload successful or async processing started
- `202` - Upload scheduled for later
- `207` - Partial success (some platforms failed)
- `500` - Complete failure

**Example Response (Scheduled)**:
```json
{
  "success": true,
  "job_id": "abc123",
  "scheduled_date": "2025-11-26T14:00:00+00:00",
  "warnings": []
}
```

**Example Response (Async)**:
```json
{
  "success": true,
  "request_id": "def456",
  "total_platforms": 2,
  "message": "Upload initiated successfully in background..."
}
```

### Job Management

#### `GET /jobs/pending`
Get all pending scheduled and async jobs.

**Headers**:
- `Authorization: Bearer <API_TOKEN>`

#### `POST /track-job`
Manually track a job.

**Body**:
```json
{
  "job_id": "abc123",
  "video_id": "video_file_id",
  "account_username": "myaccount",
  "user_id": "123456",
  "scheduled_date": "2025-11-26T14:00:00Z"
}
```

### Accounts

#### `GET /accounts/<user_id>`
Get all accounts for a user.

#### `POST /accounts/<user_id>`
Create a new account.

**Body**:
```json
{
  "username": "myaccount",
  "platforms": ["tiktok", "instagram"],
  "is_ai": true,
  "autoposting_properties": {
    "enabled": true,
    "start_time": "09:00",
    "end_time": "21:00",
    "interval_minutes": 180
  }
}
```

#### `PUT /accounts/<user_id>/<username>`
Update an account.

#### `DELETE /accounts/<user_id>/<username>`
Delete an account.

### Videos

#### `GET /videos/<user_id>`
Get all videos for a user.

#### `POST /videos/<user_id>`
Add a video to the library.

#### `DELETE /videos/<user_id>/<video_id>`
Delete a video from the library.

### AI Caption Generation

#### `POST /generate-caption`
Generate a caption using AI.

**Body**:
```json
{
  "prompt": "Generate a TikTok caption for a video about...",
  "model": "anthropic/claude-3-haiku"
}
```

## Database Schema

### `accounts`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| user_id | TEXT | Telegram user ID |
| username | TEXT | Account username |
| platforms | JSON | Array of platforms |
| is_ai | INTEGER | AI content flag |
| autoposting_properties | JSON | Auto-posting settings |
| scheduled_times | JSON | Array of scheduled upload times |
| next_upload_time | TEXT | Next calculated upload time |
| last_upload_time | TEXT | Last successful upload time |
| group_name | TEXT | Account group (optional) |

### `videos`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| user_id | TEXT | Telegram user ID |
| video_id | TEXT | Telegram file ID |
| caption | TEXT | Video caption |
| status | TEXT | pending/scheduled/uploading/posted/partial/failed |
| scheduled_at | TEXT | Scheduled upload time |
| posted_at | TEXT | Actual post time |
| platform_post_url | TEXT | URL(s) of posted content |

### `scheduled_jobs`
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| job_id | TEXT | Upload-Post job ID or request ID |
| video_id | TEXT | Associated video ID |
| account_username | TEXT | Account username |
| user_id | TEXT | User ID |
| scheduled_date | TEXT | Scheduled time or check time |
| status | TEXT | pending/completed/failed |
| is_async | INTEGER | 1 for async uploads, 0 for scheduled |
| platform_post_url | TEXT | Result URL |

## Auto-Scheduling Logic

When `scheduled_date=auto` is passed:

1. Checks account's `autoposting_properties` for enabled status
2. Calculates next available slot based on:
   - `start_time` and `end_time` window
   - `interval_minutes` between uploads
   - Existing `scheduled_times` to avoid conflicts
   - `last_upload_time` as baseline
3. Adds calculated time to `scheduled_times` array
4. Returns the calculated time for Upload-Post scheduling

## Job Checker

The scheduler runs every minute to:

1. **Check scheduled jobs**: Query Upload-Post `/history` endpoint for completion
2. **Check async jobs**: Query Upload-Post `/status` endpoint for background uploads
3. **Update statuses**: Mark jobs as completed/failed in database
4. **Notify users**: Send Telegram messages on completion/failure
5. **Cleanup**: Remove old scheduled times from accounts

## Error Handling

### Response Format

All errors follow this format:
```json
{
  "error": "Error message",
  "details": "Additional details (optional)"
}
```

### Common Errors

| Code | Error | Cause |
|------|-------|-------|
| 400 | Missing required fields | Form data incomplete |
| 401 | Unauthorized | Invalid or missing API token |
| 404 | Account not found | Username doesn't exist for user |
| 500 | Upload failed | Upload-Post API error |

## Logging

Logs are output to stdout with the format:
```
2025-11-26 14:00:00,000 - module_name - LEVEL - Message
```

Key log prefixes:
- `routes.upload_post` - Upload endpoint activity
- `utils.external_wrapper` - Upload tracking
- `utils.auto_schedule` - Auto-scheduling calculations
- `utils.job_checker` - Job status monitoring
- `scheduler` - APScheduler events

## Development

### Running Tests
```bash
python -m pytest tests/
```

### Adding New Endpoints

1. Create route file in `routes/` or `internal/`
2. Register blueprint in `app.py`
3. Add authentication with `@require_token` decorator

### Database Migrations

Manual migrations can be added to `init_db()` in `models/db.py`:
```python
try:
    cursor.execute('ALTER TABLE tablename ADD COLUMN newcol TYPE DEFAULT value')
    conn.commit()
except sqlite3.OperationalError:
    pass  # Column already exists
```

## License

Private - All rights reserved