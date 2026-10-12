# League5Edge — Render dependency fix

The original `understat==0.1.14` package pins `aiohttp==3.8.3`, which conflicts with the project's modern `aiohttp==3.13.5` and can be problematic on current Python. This deployment package removes the legacy `understat` dependency and uses a small local compatibility implementation of the Understat endpoints with `aiohttp` and `BeautifulSoup`.

## Render settings
Build: `pip install --upgrade pip && pip install -r requirements.txt`
Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
Health check: `/api/health`

Use Python 3.12.8. Push the contents of this folder to GitHub, then redeploy. If Render still reports old settings, verify the repository and branch and use **Manual Deploy → Clear build cache & deploy**.
