import logging

app_logger = logging.getLogger("url-shortener")
logging.basicConfig(level=logging.INFO)

# Prevent duplicate logs if this module gets imported multiple times
if not app_logger.handlers:
  # Console handler
  console_handler = logging.StreamHandler()
  console_handler.setLevel(logging.INFO)

  # Formatter
  formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
  console_handler.setFormatter(formatter)

  # Add handlers to logger
  app_logger.addHandler(console_handler)

# Optional: prevent log propagation to root logger
app_logger.propagate = False
