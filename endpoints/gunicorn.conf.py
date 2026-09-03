bind = "0.0.0.0:9000"
workers = 4
accesslog = "-"
errorlog = "-"

# Gunicorn's default sync-worker timeout (30s) killed workers mid-upload on
# large Telegram video sends: the outbound requests.post() to api.telegram.org
# (endpoints/routes/telegram.py, itself budgeted at 120s) routinely took longer
# than 30s to connect+transfer a ~44MB file, so the arbiter SIGABRT'd the
# worker before that 120s timeout ever got a chance to fire cleanly. The
# client saw an opaque 500 with no body instead of piper's own JSON error.
# Keep this comfortably above the 120s Telegram call.
timeout = 180

# `start_scheduler` spawns a daemon thread that polls every minute.
# Running it in `when_ready` pins it to the master process so 4 workers
# don't each spin up their own copy (which would fire check_scheduled_jobs
# 4x every 5 minutes and cause duplicate upload status flips).
def when_ready(server):
    from scheduler import start_scheduler
    start_scheduler()
