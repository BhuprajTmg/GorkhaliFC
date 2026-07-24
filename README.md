# Gurkhali FC

Official website for **Gurkhali FC** (Darwin, NT, Australia), built with
**Django** (backend) and plain **HTML/CSS/JS** templates (frontend). Rebuilt
from scratch to replace an earlier static HTML export, so the club can
manage players, fixtures, and gallery photos through a proper admin panel
instead of editing raw HTML files.

## Features

The site is a **single scrollable page** (like the original static site),
with the nav bar linking to in-page sections via anchors
(`/#about`, `/#players`, `/#schedule`, `/#photos`, `/#contact`) instead of
separate pages:

- **Home** — hero banner (club name, motto, CTAs), quick stats.
- **About** — editable club story, founding year, home ground.
- **Players** — squad grouped by position (Goalkeepers, Defenders,
  Midfielders, Forwards). Each player card links out to its own dedicated
  profile page (photo, jersey number, bio) — the only page that isn't a
  section of the one-pager, similar to the original per-player HTML files.
- **Schedule** — upcoming fixtures and past results (home/away tags,
  scores).
- **Photos** — gallery with category filters (Matches, Team Photos,
  Training, ...) filtered instantly with JS, no page reload.
- **Contact** — club contact details, social links, and a working contact
  form (submits without leaving the page; messages are saved and viewable
  in the admin).
- **Django admin** — manage everything above (players, fixtures, gallery
  images, club info, contact messages) without touching code, at `/admin/`.

## Project layout

```
gurkhali_fc/            Django project settings & root URLs
club/                   Main app: models, views, urls, forms, admin, management command
templates/club/         base.html (layout + nav) and home.html (assembles sections)
templates/club/includes/  One partial per section: _hero, _about, _players, _schedule, _photos, _contact
static/css/             Site styling (style.css) — includes a commented-out alternate theme
static/js/               Mobile nav toggle + gallery category filter (main.js, gallery-filter.js)
media/                  User-uploaded images (players, gallery, logo) - gitignored
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
   `http://127.0.0.1:8000/admin/` to manage content (players, fixtures,
   gallery photos, club info).

## Adding player photos & descriptions

This is the main thing to do once you have the real squad details:

1. Go to `http://127.0.0.1:8000/admin/` and log in.
2. Click **Players**.
3. Click an existing player (e.g. "Sohan Khadka") to edit them, or
   **Add player** to create a new one.
4. Fill in:
   - **Name**, **Position**, **Jersey number** — shown on the squad card.
   - **Photo** — upload a square headshot (roughly 500x500px works best).
     A live preview shows up once you save.
   - **Bio** — a short paragraph about the player; shown on their profile
     page (the page you get to by clicking their card).
   - **Is captain** — ticks a "C" badge on their card.
   - **Order** — lower numbers appear first within their position group.
5. Click **Save**. The change appears immediately on the live site (no
   restart needed) — refresh `http://127.0.0.1:8000/#players`.

To remove a placeholder player instead of editing them, open them in the
admin and use the **Delete** button, or untick **Is active** to hide them
without deleting their record.

The **Gallery Images** section works the same way for match/team photos,
and **Club Info** is where you set the club logo, about text, and contact
details.

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
- **Contact Messages** — messages submitted through the Contact section
  form.

The `seed_demo` command creates a starting squad (Sohan Khadka - GK, Niroj
Shrestha - DF, Ujjwal Giri - DF, plus a few more with best-guess positions)
and a placeholder fixture list based on the club's original static site.
Correct positions/jersey numbers and add real photos and bios for
everyone once available.

## Changing the color theme

`static/css/style.css` defines all colors as CSS variables in a `:root`
block at the top of the file. Right below the active navy/gold/crimson
theme there's a second, **commented-out** `:root` block using a red/blue
palette (`#FF0000` / `#0055DA`). To switch themes: comment out the active
block and uncomment the alternate one (keep exactly one `:root` block
active at a time), then refresh the page.

## Notes

- Uploaded images are stored under `media/` and are only served directly by
  Django when `DEBUG=True` (fine for local development). For production,
  serve `media/` and `staticfiles/` (after running
  `python manage.py collectstatic`) via your web server or a storage
  service.
- Configuration is read from environment variables where useful:
  `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`.
