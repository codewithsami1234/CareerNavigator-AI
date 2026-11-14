# blitz.cloud notes (CareerNavigator AI)

Free plan: no card. App sleeps after 15 minutes idle. Memory: prefer **Medium** (256 MB reserved, 1 GB ceiling) because OpenCV + Tesseract + PyMuPDF are heavy; Small (512 MB ceiling) may OOM on OCR.

## Required app settings after deploy

| Setting | Value |
|--------|--------|
| Kept folder | `/app/data` (declared as `VOLUME` in Dockerfile) |
| `CAREERNAV_COOKIE_SECURE` | `1` |
| `CAREERNAV_STATIC_DIR` | `/app/frontend_dist` |
| `CAREERNAV_DATABASE_URL` | `sqlite:////app/data/careernavigator.sqlite` |
| `CAREERNAV_CORS_ORIGINS` | `https://<app>.<you>.prod.page` |
| App size | Medium if available on free pool |

## Persistence honesty

- SQLite in `/app/data` survives **container restarts** when the folder is kept.
- Free plan does **not** nightly-backup kept folders (only managed SQL/Redis DBs). Export the SQLite file yourself for durable backups.
