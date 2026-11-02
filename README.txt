SUPPORT CONTROL — SEPARATE FASTAPI WEB DASHBOARD

Upload this ZIP to a NEW separate FastAPI app. It does not replace your Telegram bot.

Environment variables to add to this new dashboard app:
SUPABASE_URL = same Supabase project URL
SUPABASE_SERVICE_ROLE_KEY = same service-role key (server-side only; never put in frontend)
BOT_TOKEN = same Telegram bot token (server-side only)
WEB_ADMIN_USERNAME = your dashboard login username
WEB_ADMIN_PASSWORD = your strong dashboard password
SESSION_SECRET = a long random secret (32+ random characters)

Install requirements.txt.
Start command (if Pella asks):
uvicorn app:app --host 0.0.0.0 --port $PORT

If Pella requires a fixed port, use the port it assigns/shows.
Open the app's HTTPS URL and log in.

Included in this first build:
- Login with signed HttpOnly secure cookie
- Overview counts
- User search and manual add
- Grant/revoke allow_new_complaint
- Ticket list and status update
- One-to-one TEXT Telegram messages
- TEXT broadcast with sent/failed summary
- Activity log viewer

Limitations:
- Broadcast and direct messaging currently support text only, not media/files.
- Actual ticket/customer column names must match your Supabase schema. The app reports errors if they differ.
- This dashboard is separate from the Telegram bot and does not replace its main.py.
- Keep the service role key, bot token, password and session secret only in Pella environment variables.
- Free hosting may sleep or have uptime limits.
