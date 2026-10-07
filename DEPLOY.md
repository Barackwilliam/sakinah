# Kuhost Sakinah kwenye Render

Mradi una `render.yaml` (Render Blueprint) na `build.sh`. Database na picha zinakaa Supabase, kwa sababu diski ya Render (free plan) inafutwa kila deploy.

## 1. Andaa Supabase (mara moja)
1. **Database**: Supabase → Project Settings → Database → *Connection string* → chagua **Session pooler** → nakili URI (badilisha `[YOUR-PASSWORD]` kuwa password yako). Hii ndiyo `DATABASE_URL`.
2. **Storage**: Supabase → Storage → *New bucket* → jina `nusrah-media` → weka **Public bucket**.
3. **S3 keys**: Storage → Settings → *S3 Connection* → *New access key*. Nakili *Access key ID* (`SUPABASE_S3_KEY`), *Secret* (`SUPABASE_S3_SECRET`) na *Region* (`SUPABASE_REGION`). `SUPABASE_PROJECT_REF` ni sehemu ya kwanza ya URL ya project, mfano `abcd1234` kwenye `https://abcd1234.supabase.co`.

## 2. Unda service kwenye Render
1. Ingia https://dashboard.render.com → **New** → **Blueprint** → unganisha GitHub na uchague repo `Barackwilliam/sakinah` (branch `main`).
2. Render itasoma `render.yaml` na kukuuliza thamani hizi:
   | Key | Thamani |
   |---|---|
   | `DATABASE_URL` | URI ya Supabase (hatua 1.1) |
   | `SUPABASE_PROJECT_REF`, `SUPABASE_S3_KEY`, `SUPABASE_S3_SECRET`, `SUPABASE_REGION` | kutoka hatua 1.3 |
   | `ADMIN_EMAIL`, `ADMIN_PASSWORD` | akaunti ya Super Admin itakayoundwa kwenye deploy ya kwanza |
   | `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | domain yako, mfano `sakinah.co.tz,www.sakinah.co.tz` (acha tupu kama utatumia anwani ya `onrender.com` tu) |
3. Bofya **Apply**. Build inaendesha `build.sh`: inasakinisha packages, `collectstatic`, `migrate`, inaunda admin, na `seed` (maudhui ya mwanzo pamoja na picha).
4. Ikimaliza, fungua `https://<jina>.onrender.com`. Ingia `/login/` → **Admin Login** kwa `ADMIN_EMAIL` na `ADMIN_PASSWORD` → utapelekwa `/dashboard/`.

`SECRET_KEY` inatengenezwa na Render yenyewe. Usiiweke kwenye GitHub.

## 3. Domain yako (hiari)
Render → service → **Settings** → **Custom Domains** → ongeza domain, kisha weka DNS records unazopewa. Ongeza domain hiyo kwenye `ALLOWED_HOSTS` na `CSRF_TRUSTED_ORIGINS`.

## 4. Email (hiari, kwa "Forgot password")
Weka `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` (mfano Gmail SMTP: `smtp.gmail.com`, 587, na *App password*). Bila hizi, email zinaandikwa kwenye log tu, na Communication Center inatuma notifications na in-app messages pekee.

## Mambo ya kujua
- **Free plan** ya Render inalala baada ya dakika 15 bila wageni; ombi la kwanza linachukua takriban sekunde 30–60. Plan ya kulipia haina tatizo hili.
- Kuzima seed kwenye deploy: weka `SEED_ON_DEPLOY=False`.
- Bila Supabase Storage, picha zinazopakiwa zitapotea kila deploy. Ukitumia **Render Disk** badala yake, iweke kwenye `/var/data/media` na weka `MEDIA_ROOT=/var/data/media` na `SERVE_MEDIA=True`.

## Kuendesha kwenye PC (local)
```bat
copy .env.example .env
pip install -r requirements.txt
python manage.py migrate
python manage.py seed
python manage.py createsuperuser
python manage.py runserver
```
