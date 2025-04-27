import multiprocessing

# Gunicorn configuration
bind = "0.0.0.0:10000"
workers = multiprocessing.cpu_count() * 2 + 1
timeout = 120  # 2 minutes timeout
keepalive = 5
worker_class = "sync"
accesslog = "-"
errorlog = "-"
loglevel = "info" 