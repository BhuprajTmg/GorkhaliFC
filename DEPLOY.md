# Deploy Gurkhali FC for $0 (24/7-ish)

**Recommended free host: [PythonAnywhere](https://www.pythonanywhere.com/)**

| Need | Free PythonAnywhere |
|------|---------------------|
| Cost | **$0** |
| Always reachable | Yes, while the web app is extended |
| Speed | Slow is fine (1 worker, limited CPU) |
| SQLite + photo uploads | Yes (files stay on disk) |
| Monthly action | Click **Extend** when they email you (~every month) |

> Free web apps expire after about **1 month** unless you extend them (PythonAnywhere emails a reminder). That click is free. Your code and database are **not deleted**.

Other “free” hosts (Render, Railway free tiers) often **sleep** or wipe the disk on restart — bad for SQLite and uploaded photos. PythonAnywhere is the practical $0 choice for this project.

---

## 1. Prepare (on your computer)

1. Push this repo to GitHub (already done if you use `BhuprajTmg/GorkhaliFC`).
2. Create a long random secret (you’ll paste it on PythonAnywhere):

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(50))"
   ```

---

## 2. Create a free PythonAnywhere account

1. Sign up at https://www.pythonanywhere.com/ (Beginner / free).
2. Open a **Bash** console.

---

## 3. Clone the project on PythonAnywhere

In the Bash console (replace `YOUR_USERNAME` if paths differ):

```bash
cd ~
git clone https://github.com/BhuprajTmg/GorkhaliFC.git
cd GorkhaliFC
```

If the repo is **private**, use a GitHub [Personal Access Token](https://github.com/settings/tokens) as the password when `git clone` asks, or make the repo public for simpler deploys.

Create a virtualenv with **Python 3.12** (Django 6 needs 3.12+):

```bash
mkvirtualenv --python=/usr/bin/python3.12 gurkhali
pip install -r requirements.txt
```

---

## 4. Environment variables (production + email)

Still in Bash, with the venv active (`workon gurkhali`):

```bash
cd ~/GorkhaliFC
nano .env
```

Paste (edit values):

```env
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=paste-the-long-secret-from-step-1
DJANGO_ALLOWED_HOSTS=YOUR_USERNAME.pythonanywhere.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://YOUR_USERNAME.pythonanywhere.com

# Optional — Gmail App Password (often blocked on FREE PythonAnywhere;
# registrations still save in Admin even if mail fails)
EMAIL_HOST_USER=your-club-email@gmail.com
EMAIL_HOST_PASSWORD=your-16-character-app-password
DEFAULT_FROM_EMAIL=your-club-email@gmail.com
```

Save: `Ctrl+O`, Enter, `Ctrl+X`.

Then:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

(Optional demo data) `python manage.py seed_demo`

---

## 5. Configure the Web app

1. Go to the **Web** tab → **Add a new web app**.
2. Choose **Manual configuration** (not the “Django” wizard) → **Python 3.12**.
3. **Virtualenv** path:

   ```text
   /home/YOUR_USERNAME/.virtualenvs/gurkhali
   ```

4. Open the **WSGI configuration file** link. Delete everything and paste the contents of `pythonanywhere_wsgi.py.example` from this repo, with `YOUR_USERNAME` replaced by your real username. Save.
5. **Static files** mappings (Scroll to Static files):

   | URL | Directory |
   |-----|-----------|
   | `/static/` | `/home/YOUR_USERNAME/GorkhaliFC/staticfiles` |
   | `/media/` | `/home/YOUR_USERNAME/GorkhaliFC/media` |

6. Click **Reload** (green button).

Your site: `https://YOUR_USERNAME.pythonanywhere.com/`  
Admin: `https://YOUR_USERNAME.pythonanywhere.com/admin/`

---

## 6. Keep it free & online

1. When PythonAnywhere emails “your web app will expire”, log in → **Web** → **Extend** / renew. **$0.**
2. After code updates:

   ```bash
   cd ~/GorkhaliFC
   workon gurkhali
   git pull origin main
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

   Then **Web → Reload**.

3. **Email on free accounts:** outbound SMTP to Gmail is often blocked. New registrations still appear under **Admin → Team Registrations**. For reliable Gmail sending, a paid PythonAnywhere plan (or another host that allows SMTP) is needed — the site itself stays free either way.

---

## Quick checklist

- [ ] Free PythonAnywhere account  
- [ ] `git clone` + `mkvirtualenv --python=/usr/bin/python3.12 gurkhali`  
- [ ] `.env` with `DJANGO_DEBUG=False` and secret key  
- [ ] `migrate` + `collectstatic` + `createsuperuser`  
- [ ] WSGI file from `pythonanywhere_wsgi.py.example`  
- [ ] Static `/static/` → `staticfiles`, `/media/` → `media`  
- [ ] Reload web app  
- [ ] Bookmark the monthly **Extend** email  

---

## Alternatives (if PythonAnywhere doesn’t suit you)

| Host | $0? | Notes |
|------|-----|--------|
| **Oracle Cloud Always Free** | Yes (card often required to sign up) | Real 24/7 VM; harder setup (Linux + nginx + gunicorn) |
| **Render free web service** | Yes | Sleeps when idle; **disk not persistent** — SQLite/photos can vanish |
| **Fly.io** free allowance | Limited free credit | More DevOps; good later if you outgrow PA |

For this club site, start with **PythonAnywhere**.
