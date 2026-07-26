# Gurkhali FC

Official website for **Gurkhali FC** (Darwin, NT, Australia), built with
**Django** (backend) and plain **HTML/CSS/JS** templates (frontend). Rebuilt
from scratch to replace an earlier static HTML export, so the club can
manage players, fixtures, and gallery photos through a proper admin panel
instead of editing raw HTML files.

## Features

The site is a **single scrollable page** (like the original static site),
with the nav bar linking to in-page sections via anchors
(`/#about`, `/#players`, `/#schedule`, `/#register`, `/#photos`,
`/#contact`) instead of separate pages:

- **Home** — hero banner (club name, motto, CTAs), quick stats.
- **About** — editable club story, founding year, home ground.
- **Players** — squad grouped by position (Goalkeepers, Defenders,
  Midfielders, Forwards), shown as red/blue ID-badge style cards. Each card
  links out to its own dedicated profile page (photo, jersey number, bio)
  — the only page that isn't a section of the one-pager, similar to the
  original per-player HTML files.
- **Schedule** — driven by each match's **Status** (set from the admin:
  Scheduled / Live now / Finished):
  - Any match marked **Live now** shows in a "Live Now" section at the
    very top, with a pulsing red dot, a glowing highlighted border, and
    the live score.
  - The next **5 scheduled fixtures** are shown (first as Next Match,
    the rest as Upcoming).
  - Matches marked **Finished** (with a final score) appear under
    Results for **5 minutes**, then disappear. Finishing a match also
    syncs that score into the matching World Cup group table.
  - Interactive **knockout round cards** (Quarter-finals → Semi-finals →
    Final) with hover lift and click-to-expand overlays, matching the group
    table interaction. **Group tables** stay on a side **Tables** button.
    Edit groups/teams under **Competition groups** in the admin.
- **Register** — a "Register Your Team" button that opens a floating,
  semi-transparent form overlay (doesn't take up space on the page until
  clicked) with: team name, division, manager/coach contact, plus a
  **fixed 15-slot player roster** (name + jersey number per row — see
  `club.models.ROSTER_SIZE` to change the count). The player count is
  calculated automatically from how many roster rows have a name, not
  manually typed in. Submissions are saved to the database, emailed to
  the club with both a Word (`.docx`) and a PDF summary attached (full
  roster included), and manageable (approve / waitlist / reject) from
  the admin. If a submission has errors, the form re-opens automatically
  showing what needs fixing.
- **Photos** — gallery with category filters (Matches, Team Photos,
  Training, ...) filtered instantly with JS, no page reload.
- **Contact** — club contact details, social links, and a working contact
  form. Submitting it emails the club (see "Email setup" below) and saves
  a copy in the admin; it never leaves the page.
- **Success/error popups** — submitting the Contact or Register form shows
  a popup confirming success or explaining failure (e.g. a missing
  required field), on top of inline red error text under whichever
  field(s) need fixing.
- **Django admin** — manage everything above (players, fixtures,
  registrations + their player rosters, gallery images, club info,
  contact messages) without touching code, at `/admin/` — themed to
  match the club's brand colors.

## Project layout

```
gurkhali_fc/            Django project settings & root URLs
club/                   Main app: models, views, urls, forms, admin, emails.py, management command
templates/club/         base.html (layout + nav) and home.html (assembles sections)
templates/club/includes/  One partial per section: _hero, _about, _players, _schedule, _register, _photos, _contact
templates/admin/        Minimal override to load the custom admin theme CSS
static/css/             Site styling (style.css) + admin-custom.css — includes a commented-out alternate theme
static/js/               Mobile nav toggle + theme toggle + gallery filter (main.js, gallery-filter.js)
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

## Email setup (contact form + registrations)

Submitting the Contact form or the tournament Register form always saves
the message/registration to the database (visible in the admin either
way), and additionally tries to **email the club** at whatever address is
set in **Club Info → Email** (falls back to `CONTACT_NOTIFICATION_EMAIL` if
Club Info has no email set). Registration emails also attach both a Word
(`.docx`) and a PDF document summarising the team's details and full
player roster.

**Without any setup**, that email is just printed to your terminal/console
window (look for lines starting with `[club.emails] ...`) — nothing
breaks, but no real email is sent, which is why "the form works but I
never receive an email" usually means this hasn't been set up yet. To
send real emails:

1. Copy `.env.example` to a new file named `.env` in the project root (same
   folder as `manage.py`).
2. If using Gmail: turn on 2-Step Verification on the Google account, then
   create an **App Password** at
   [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   (a normal Gmail password won't work for this).
3. Fill in `.env`:

   ```
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=your-16-character-app-password
   ```

4. Restart the server (`python manage.py runserver`). Emails will now
   actually be sent via Gmail's SMTP server, from that address, to whatever
   email is set in Club Info.

Other email providers work too — just set `EMAIL_HOST`, `EMAIL_PORT`, and
`EMAIL_USE_TLS` in `.env` to match (defaults are Gmail's).

**On Cursor Cloud Agents:** add `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` as
secrets in the Cursor Dashboard (Cloud Agents → Secrets) instead of a
`.env` file — they'll be injected the same way.

`.env` is git-ignored, so your credentials never get committed.

### Troubleshooting "I'm not receiving emails"

1. **Check the terminal running `python manage.py runserver`** right after
   submitting a form. Any send attempt prints a line there:
   - `[club.emails] Email sent to ...` — it was sent successfully by
     whatever backend is configured. If you still don't see it in your
     inbox, check **Spam/Junk**, and double-check the address set on
     **Club Info → Email** in the admin is correct.
   - `[club.emails] Failed to send email to ...` followed by the real
     error (e.g. an SMTP authentication error) — this tells you exactly
     what's wrong (usually: wrong/missing App Password, or `.env` not
     picked up because the server wasn't restarted after creating it).
   - Nothing printed at all — the request likely didn't reach the view
     (e.g. the migration error covered below), or **Club Info → Email**
     is empty and `CONTACT_NOTIFICATION_EMAIL` isn't set either.
2. Make sure you restarted `runserver` after creating/editing `.env` —
   Django only reads it once, on startup.
3. Run `python manage.py migrate` after every `git pull` — a missing
   migration causes a database error before the email code even runs.

### "OperationalError: no such table: club_teamregistration" (or similar)

This means the database is missing a table for a model that was added
after your last `python manage.py migrate`. Fix:

```bash
pip install -r requirements.txt   # in case a new package was added too
python manage.py migrate
```

Do this after every `git pull` — new features in this project sometimes
come with new database migrations and/or new packages in
`requirements.txt`, and Git doesn't apply either of those for you.

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
- **Matches** — group stage: pick **Group**, then Home/Away from that
  group. Knockout: set **Stage** to QF/SF/Final (or use admin actions to
  **Generate World Cup knockout bracket** from group standings and
  **Advance knockout winners**). Finish matches with both scores to sync
  tables / progress the bracket.
- **Competition groups** — World Cup–style groups of up to four teams
  each. After the lucky draw, add teams to a group, then click
  **Generate World Cup fixtures** to auto-create round-robin matches.
- **Knockout** — dedicated admin page listing the top 2 from each group
  table. When the group stage is finished, click **Generate knockout
  fixtures** to build QF → SF → Final (+ 3rd place) automatically, then
  **Advance knockout winners** after each round.
- **Gallery Categories / Gallery Images** — organize photos (e.g. Matches,
  Team Photos) and upload images with captions.
- **Contact Messages** — messages submitted through the Contact section
  form.
- **Team Registrations** — teams that signed up via the Register section,
  including their player roster shown inline (jersey number + name) on
  the registration's detail page. Change **Status** (Pending review /
  Approved / Waitlisted / Rejected) to triage entries; filter by division
  or tournament name.

The `seed_demo` command creates a starting squad (Sohan Khadka - GK, Niroj
Shrestha - DF, Ujjwal Giri - DF, plus a few more with best-guess positions)
and a placeholder fixture list based on the club's original static site.
Correct positions/jersey numbers and add real photos and bios for
everyone once available.

## Light / dark theme toggle

There's a sun/moon button in the header (next to the mobile menu icon) that
switches the whole site between the dark navy theme and a light theme,
without a page reload. The choice is remembered per-browser via
`localStorage`, so returning visitors keep their preference.

This is implemented with CSS custom properties: `static/css/style.css`
defines the dark palette on `:root` and a light override on
`html[data-theme="light"]`; `static/js/main.js` flips that attribute on
click, and a small inline script in `base.html` applies the saved choice
before the page paints (so there's no flash of the wrong theme).

## Changing the color theme

Independently of the light/dark toggle above, `static/css/style.css` also
has a second, **commented-out** `:root` block near the top of the file
using a red/blue palette (`#FF0000` / `#0055DA`) instead of the default
navy/gold/crimson brand colors. To try it: comment out the active `:root`
block and uncomment the alternate one (keep exactly one default `:root`
block active at a time — the light-theme override can stay as-is either
way), then refresh the page.

## Admin theme

The Django admin at `/admin/` is re-colored to match the club's brand
(navy header, gold branding, crimson buttons/links) via
`static/css/admin-custom.css`, loaded through a small override at
`templates/admin/base_site.html`. It works with the admin's built-in
light/dark mode (based on your OS preference) — both are re-themed. To
change these colors, edit the CSS variables at the top of
`admin-custom.css`.

## Notes

- Uploaded images are stored under `media/` and are only served directly by
  Django when `DEBUG=True` (fine for local development). For production,
  serve `media/` and `staticfiles/` (after running
  `python manage.py collectstatic`) via your web server or a storage
  service.
- Configuration is read from environment variables where useful:
  `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`.
