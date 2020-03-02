from environs import Env

env = Env()
env.read_env()

# CENSUS_API_KEY is required
FRA_DOT_GOV_CERT_PATH = env.str("FRA_DOT_GOV_CERT_PATH", default="fra-dot-gov-chain.pem")

# Only relevant in development for flask development server
DEBUG = env.bool("DEBUG", default=False)
HOST = env.str("HOST", default="0.0.0.0")
PORT = env.int("PORT", default=5000)

SECONDS = 1000
MINUTES = 60 * SECONDS
UPDATE_INTERVAL = 15 * MINUTES  # in milliseconds

# Use filesystem for cache
CACHE_DIR = env.str("CACHE_DIR", default="/tmp/cache")
CACHE_TYPE = "filesystem"
CACHE_DEFAULT_TIMEOUT = 13 * 60  # in seconds
