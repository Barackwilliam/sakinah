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
   | `ADMIN_EMAIL`, `ADMIN_PASSWORD` | akaunti ya **Super Admin wa mteja** itakayoundwa kwenye deploy ya kwanza (inasimamia kila kitu kupitia `/dashboard/`) |
   | `DJANGO_ADMIN_URL` | anwani ya siri ya Django admin yako wewe developer, mfano `sk-dev-7f3k2/` (usiitaje kwa mteja) |
   | `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | domain yako, mfano `sakinah.co.tz,www.sakinah.co.tz` (acha tupu kama utatumia anwani ya `onrender.com` tu) |
3. Bofya **Apply**. Build inaendesha `build.sh`: inasakinisha packages, `collectstatic`, `migrate`, inaunda admin, na `seed` (maudhui ya mwanzo pamoja na picha).
4. Ikimaliza, fungua `https://<jina>.onrender.com`. Ingia `/login/` → **Admin Login** kwa `ADMIN_EMAIL` na `ADMIN_PASSWORD` → utapelekwa `/dashboard/`.

`SECRET_KEY` inatengenezwa na Render yenyewe. Usiiweke kwenye GitHub.

## 2b. Django admin ni yako wewe developer tu
- Mteja (Super Admin na Administrators) anasimamia kila kitu kupitia `/dashboard/`; hakuna kiungo chochote kinachoelekea Django admin.
- Django admin iko kwenye `DJANGO_ADMIN_URL` (kwa default `devadmin/`). Mtu yeyote asiye **superuser** anapata 404 hata akiijua anwani, kama vile ukurasa haupo.
- Unda akaunti yako ya developer (superuser) kwa command, kwenye Render Shell au kwenye kompyuta yako huku `DATABASE_URL` ikielekeza Supabase:
  ```bash
  python manage.py createsuperuser
  ```
  Kisha ingia kupitia `/login/` na ufungue `https://<domain>/<DJANGO_ADMIN_URL>`.
- Usimpe mteja akaunti ya superuser. Staff wapya wanaongezwa na Super Admin kupitia **Dashboard → User Management**.

## 2c. Static files na picha (media)
- **CSS, JavaScript na picha za mfumo (static):** zinakusanywa na `collectstatic` wakati wa build na kutolewa na WhiteNoise. Hazihitaji mpangilio wowote.
- **Picha zinazopakiwa (media):** picha za wanachama, matukio, matangazo, n.k.
  - **Inapendekezwa: Supabase Storage** (hatua 1.3). Picha zinabaki salama hata baada ya deploy mpya.
  - **Bila Supabase:** Django yenyewe inatoa picha kutoka diski (`SERVE_MEDIA=True` ni default). Diski ya Render inafutika kila deploy, kwa hivyo `build.sh` inaendesha `restore_media`, inayorudisha picha za mwanzo (za seed). **Picha zilizopakiwa na watu zitapotea kila deploy**, kwa hivyo weka Supabase Storage kabla ya kuwapokea wateja.
- **Kuendesha kwenye kompyuta yako kwa `DEBUG=False`:** endesha kwanza `python manage.py collectstatic`. Tovuti itafanya kazi kwa `http://127.0.0.1:8000`, kwa sababu kulazimisha `https` kunawashwa kwenye Render tu (`HTTPS_ONLY`).

## 3. Domain yako (hiari)
Render → service → **Settings** → **Custom Domains** → ongeza domain, kisha weka DNS records unazopewa. Ongeza domain hiyo kwenye `ALLOWED_HOSTS` na `CSRF_TRUSTED_ORIGINS`.

## 4. Email (hiari, kwa "Forgot password")
**Render free plan inazuia SMTP** (ports 25, 465 na 587; tangu Septemba 2025), kwa hiyo Gmail SMTP haifanyi kazi huko. Tumia **Brevo** (bure, email 300 kwa siku):
1. Jisajili [brevo.com](https://www.brevo.com), kisha **Senders** → ongeza na uthibitishe email utakayotumia kutuma (mfano `no-reply@sakinah.co.tz` au Gmail yako).
2. **SMTP & API → API Keys** → tengeneza key.
3. Kwenye Render weka `BREVO_API_KEY` = key hiyo, na `DEFAULT_FROM_EMAIL` = `Sakinah <email-uliyothibitisha>`.

Mbadala: `RESEND_API_KEY` (resend.com), au `EMAIL_HOST`/`EMAIL_PORT`/`EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` kwa SMTP (inafanya kazi kwenye plan za kulipia tu). Bila hivi, email zinaandikwa kwenye log tu.

**Forgot password bila email:** member anaweza kuandika email, username au namba ya simu. Email ikishindwa kutumwa (au akaunti haina email), ombi linaingia **Support & Tickets** kama "Password reset help". Admin anafungua **Members Management → ⋮ → Password reset link**, ananakili link na kumtumia member kwa WhatsApp au SMS.

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

## Watermark kwenye picha

Kila picha inayowekwa kwenye mfumo (picha za members, adverts, events, honeymoon, makala n.k.) inawekewa maandishi **sakinah.co.tz** chini kidogo ya katikati, na inapunguzwa ukubwa isizidi 1600px. Logo ya tovuti, icons za mipango, logo za vendors na viambatisho vya support haviwekewi watermark.

- Kubadilisha maandishi: weka `WATERMARK_TEXT` kwenye Render (Environment). Ukiiacha tupu, watermark inazimwa.
- Picha zilizokuwepo kabla: endesha `python manage.py watermark_images` mara moja (kwenye Render weka `WATERMARK_EXISTING=True` kwa deploy moja, kisha uiondoe). Picha zenye watermark tayari hazirudiwi.

## Kuficha sura (Hide my face)

Kwenye **My Photos** na **Settings**, member anachagua mwenyewe swichi ya **Hide my face**. Ikiwa imewashwa, mfumo unagundua sura (YuNet, ndani ya `core/ml/`) na kuifunika kwa wingu laini kabla picha haijahifadhiwa. Picha isiyo na sura inakataliwa ili isionekane kimakosa. Kila picha iliyopakiwa ina kitufe cha **Hide face**: kinaficha sura na kufuta picha ya asili.
