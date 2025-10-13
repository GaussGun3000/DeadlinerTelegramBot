import os

TOKEN = os.getenv("BOT_TOKEN", "")

# verification process is manual for safety. Just add needed id to this list to give user add right (and redeploy)
VERIFIED_USERS = [405810751,]
OWNER_ID = 405810751
ADMINS = [405810751, ]
PERIOD = 180  # time between periodic tasks in sec
GROUP_CHAT_ID = -1002717878878
DEADLINES_TOPIC = 2017
ANNOUNCE_TOPIC = 2025
