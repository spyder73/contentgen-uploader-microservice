bind = "0.0.0.0:9000"
workers = 4
accesslog = "-"
errorlog = "-"

# `start_scheduler` spawns a daemon thread that polls every minute.
# Running it in `when_ready` pins it to the master process so 4 workers
# don't each spin up their own copy (which would fire check_scheduled_jobs
# 4x every 5 minutes and cause duplicate upload status flips).
def when_ready(server):
    from scheduler import start_scheduler
    start_scheduler()
