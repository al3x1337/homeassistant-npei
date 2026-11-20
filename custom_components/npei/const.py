"""Constants for the Niagara Peninsula Energy Inc. (NPEI) integration."""

from datetime import timedelta

DOMAIN = "npei"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_ACCOUNT_ID = "account_id"
CONF_SERVICE_ID = "service_id"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL_MINUTES = 60
DEFAULT_SCAN_INTERVAL = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES)

# API Endpoints
IAM_BASE_URL = "https://iamapi-dot-npei-myaccount-prod.appspot.com/iamapi"
USAGE_BASE_URL = "https://usageapi-dot-npei-myaccount-prod.appspot.com"
MYACCOUNT_BASE_URL = "https://myaccountapi-dot-npei-myaccount-prod.appspot.com"
WEATHER_BASE_URL = "https://sharedservicesapi.lhsharedservices.com/weather/public/api/v1"

# Price plans
PRICE_PLAN_TOU = "TOU"
PRICE_PLAN_TIERED = "TIERED"
PRICE_PLAN_ULO = "ULO"
