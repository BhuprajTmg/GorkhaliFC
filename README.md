# Gurkhali FC

Official website for **Gurkhali FC** (Darwin, NT, Australia), built with
**Django** (backend) and plain **HTML/CSS/JS** templates (frontend). Rebuilt
from scratch to replace an earlier static HTML export, so the club can
manage players, fixtures, and gallery photos through a proper admin panel
instead of editing raw HTML files.

## Features

- **Home page** — hero banner (club name, motto, CTAs), quick stats, next
  match teaser, gallery preview.
- **About page** — editable club story, founding year, home ground.
- **Players page** — squad grouped by position (Goalkeepers, Defenders,
  Midfielders, Forwards); click through to a player's profile page (photo,
  jersey number, bio).
- **Schedule page** — upcoming fixtures and past results (home/away tags,
  scores).
- **Photos page** — gallery with category filters (Matches, Team Photos,
  Training, ...).
- **Contact page** — club contact details, social links, and a working
  contact form (messages are saved and viewable in the admin).
- **Django admin** — manage everything above (players, fixtures, gallery
  images, club info, contact messages) without touching code, at `/admin/`.

## Project layout

```
gurkhali_fc/         Django project settings & root URLs
club/                Main app: models, views, urls, forms, admin, management command
templates/club/      HTML templates (base layout + one per page)
static/css/          Site styling (style.css)
static/js/           Small JS (mobile nav toggle)
media/               User-uploaded images (players, gallery, logo) - gitignored
```

## Getting started

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # on Windows: venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Apply database migrations:

   ```bash
   python manage.py migrate
   ```

4. (Optional) Seed some placeholder club/squad data so the site isn't empty:

   ```bash
   python manage.py seed_demo
   ```

5. Create an admin user so you can log in to `/admin/`:

   ```bash
   python manage.py createsuperuser
   ```

6. Run the development server:

   ```bash
   python manage.py runserver
   ```

7. Visit `http://127.0.0.1:8000/` for the site and
   `http://127.0.0.1:8000/admin/` to manage content (players, gallery
   photos, news, club info).

## Managing content

Everything editable lives in the Django admin (`/admin/`):

- **Club Info** — club name, tagline, about text, logo, founded year, home
  ground, location, contact details, social links.
- **Players** — name, position, jersey number, photo, bio, captain flag,
  display order.
- **Matches** — fixtures/results: opponent, date, time, venue, home/away,
  score.
- **Gallery Categories / Gallery Images** — organize photos (e.g. Matches,
  Team Photos) and upload images with captions.
- **Contact Messages** — messages submitted through the Contact page form.

The `seed_demo` command creates a starting squad (Sohan Khadka - GK, Niroj
Shrestha - DF, Ujjwal Giri - DF, plus a few more with best-guess positions)
and a placeholder fixture list based on the club's original static site.
Correct positions/jersey numbers and add real photos and bios for
everyone once available.

## Notes

- Uploaded images are stored under `media/` and are only served directly by
  Django when `DEBUG=True` (fine for local development). For production,
  serve `media/` and `staticfiles/` (after running
  `python manage.py collectstatic`) via your web server or a storage
  service.
- Configuration is read from environment variables where useful:
  `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`.
