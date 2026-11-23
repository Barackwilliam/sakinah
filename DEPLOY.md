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

## 3b. Admin kwenye admin.sakinah.co.tz
Login ya admin iko `/dashboard/login/` (ukurasa wake peke yake; login ya wanachama haina tena kitufe cha admin). Kuiweka kwenye anwani yake:
1. Kwa mtoa huduma wa domain (DNS), ongeza **CNAME**: jina `admin`, thamani ni anwani ya Render (`xxxx.onrender.com`).
2. Render → service → **Settings → Custom Domains** → ongeza `admin.sakinah.co.tz`, subiri cheti (SSL) kiwe tayari.
3. Render → **Environment** → ongeza `ADMIN_HOST` = `admin.sakinah.co.tz` (na `SITE_URL` = `https://www.sakinah.co.tz` kama tovuti kuu iko kwenye anwani nyingine).
Baada ya hapo `admin.sakinah.co.tz` inafungua login ya admin moja kwa moja, na viungo vya `/dashboard/` kwenye tovuti kuu vinapelekwa huko. Usiweke `ADMIN_HOST` kabla hatua 1-2 hazijakamilika, la sivyo admin hataweza kufika kwenye dashboard.

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

## Voice call, video call na voice note

- **Voice note:** kitufe cha kipaza sauti kwenye chat (hadi dakika 2). Inafuata ruhusa zilezile za ujumbe. Haihitaji mpangilio wowote.
- **Voice na video call:** kitufe cha simu na video juu ya chat. Mpigaji lazima awe **Premium**, na wawe **mutual match** (wamependana wote wawili); block inaheshimiwa. Mpokeaji anaona dirisha la simu yenye mlio popote alipo kwenye site. Simu ambayo haijapokelewa ndani ya sekunde 45 inakuwa "Missed call", na inaonekana kwenye chat pamoja na notification.
- Sauti na video zinapita moja kwa moja kati ya members (WebRTC); server inapitisha tu taarifa za kuunganisha. Simu zinahitaji **https** (Render inayo) au `127.0.0.1` kwa majaribio.

**TURN (muhimu kwa mitandao ya simu):** bila TURN, simu nyingi zinaunganika kwenye Wi-Fi lakini mara nyingi zinashindwa kwenye data ya simu (Vodacom, Airtel, Tigo). Weka TURN ya bure:
1. Ingia [dash.cloudflare.com](https://dash.cloudflare.com) → **Realtime** → **TURN Server** → **Create**.
2. Nakili **Turn Token ID** na **API Token**.
3. Kwenye Render weka `CLOUDFLARE_TURN_KEY_ID` na `CLOUDFLARE_TURN_API_TOKEN`. (GB 1,000 kwa mwezi ni bure.)

Mbadala: huduma yoyote ya TURN yenye username/password (mfano metered.ca) — weka `TURN_URLS` (zitenganishwe kwa koma), `TURN_USERNAME` na `TURN_CREDENTIAL`.

## Lugha nne (English, Kiswahili, العربية, Français)
- Kila ukurasa (tovuti, eneo la wanachama na `/dashboard/`) una menyu ya lugha (kitufe cha dunia 🌐 juu). Mgeni akichagua lugha inakumbukwa kwa mwaka mmoja; mwanachama akichagua inahifadhiwa pia kwenye wasifu wake, hivyo inamfuata kwenye simu au kompyuta nyingine. Asipochagua, tovuti inatumia lugha ya kivinjari chake.
- Kiarabu kinaonyeshwa kutoka kulia kwenda kushoto (RTL) na kwa herufi za Kiarabu (Tajawal).
- Tafsiri ziko kwenye `locale/<sw|ar|fr|en>/LC_MESSAGES/django.po`. Faili za `.mo` zilizokusanywa zimewekwa kwenye GitHub, kwa hiyo Render haihitaji kitu cha ziada.
- Maudhui ya mwanzo (vifurushi, aina za huduma, maandishi ya ukurasa wa mwanzo) yanatafsiriwa mradi hayajabadilishwa. Ukiyaandika upya kwenye `/dashboard/`, yanaonyeshwa kama ulivyoandika kwa lugha zote. Makala, matukio na wasifu wa wanachama vinaonyeshwa kama vilivyoandikwa.
- Ukiongeza maandishi mapya kwenye templates au code, sasisha tafsiri (inahitaji GNU gettext: `apt install gettext`):
  ```bash
  python manage.py form_labels
  python manage.py makemessages -l sw -l ar -l fr -l en --no-location --ignore=venv --ignore=staticfiles
  ```
  Jaza `msgstr` mpya kwenye faili za `.po`, kisha:
  ```bash
  python manage.py compilemessages
  ```

## Tangaza Nasi (Advertise with us)
- Ukurasa: `/advertise/`. Mtoa huduma anachagua kifurushi, anajaza maelezo na picha (anaona tangazo likijitengeneza), kisha analipa kwa M-Pesa / Mixx by Yas / Airtel Money / benki na kuweka namba ya muamala.
- Admin anapata taarifa na beji kwenye **Dashboard → Masoko na Matangazo → Advert Requests**. Akibofya **Confirm payment & publish**, tangazo linachapishwa mara moja kwa siku za kifurushi na kujificha lenyewe likiisha. Kuthibitisha malipo kwenye ukurasa wa Malipo kunachapisha pia.
- Watangazaji wana **akaunti zao peke yao**, tofauti na za wanachama: usajili `/advertise/register/` (jina kamili, simu, email, nenosiri na kukubali sera ya matangazo), login `/advertise/login/`, na dashboard yao `/advertise/dashboard/` (matangazo yao, kutengeneza tangazo, malipo, taarifa, akaunti). Mtangazaji hawezi kuingia kwenye kurasa za kutafuta wenzi, na mwanachama hawezi kuingia kwa login ya watangazaji. Kitufe **Post Ad** kwenye menu kinapeleka huko.
- Bei ni za mfano: zibadilishe kwenye **Advert Packages**. Namba ya malipo (Lipa Namba) iandike kwenye **Mipangilio ya Tovuti → Payments → Ad payment instructions**.
- Malipo yanathibitishwa na admin. Ukipata akaunti ya mfanyabiashara (Selcom, AzamPay, Pesapal), malipo ya moja kwa moja (push kwenye simu) yanaweza kuunganishwa baadaye bila kubadilisha kurasa hizi.

## Malipo kupitia Pesapal (live)
- Kwenye Render → Environment, weka **`PESAPAL_CONSUMER_KEY`** na **`PESAPAL_CONSUMER_SECRET`** (kutoka kwenye akaunti yako ya Pesapal: *Settings → API keys*). Usiziweke kwenye GitHub.
- Ukishaziweka, malipo yote (vifurushi vya uanachama na matangazo) yanakwenda Pesapal: mteja anapelekwa ukurasa salama wa Pesapal (M-Pesa, Airtel Money, Mixx by Yas, HaloPesa, kadi), kisha anarudishwa. Malipo yakithibitishwa, kifurushi kinawashwa / tangazo linachapishwa **lenyewe**, bila admin.
- Mfumo unasajili wenyewe anwani ya IPN (`/payments/pesapal/ipn/`) kwa Pesapal mara ya kwanza mtu anapolipa. Tunathibitisha kila malipo kwa kuuliza Pesapal moja kwa moja, kwa hiyo hakuna anayeweza kudanganya kwa kufungua kiungo.
- Bila funguo hizo, tovuti inarudi kwenye fomu ya zamani (mteja anaweka namba ya muamala, admin anathibitisha).

## Hali ya majaribio (sasa hivi)
- Bei ni ndogo za kujaribu: vifurushi TSh 50 / 100 / 150 / 200, matangazo TSh 50 / 100 / 150.
- Dakika za simu (sauti na video) kwa kila mwezi wa kifurushi: Basic 5, Silver 10, Gold 15, Tanzanite 20 (Dashboard → *Membership Plans* → *Call minutes per month*). Zikiisha, mwanachama hawezi kupiga simu hadi arudie kifurushi; huduma nyingine zinaendelea. Anapata taarifa dakika zikiisha na kifurushi kikiisha.
- **Mwezi mmoja = siku 3** (Dashboard → Mipangilio ya Tovuti → Payments → *Days in one month*). Mkimaliza majaribio: weka **30** hapo, na bei halisi kwenye *Membership Plans* na *Advert Packages*.

## Lugha ya msingi na uthibitisho wa barua pepe
- Tovuti inafunguka kwa **Kiswahili** kwa kila mtu mpaka achague lugha nyingine kwenye menyu (lugha ya kivinjari haitumiki). Kubadilisha: weka `SITE_LANGUAGE=en` (au `ar`, `fr`) kwenye Render.
- Anayejisajili anatumiwa barua pepe yenye **code ya tarakimu 6** na **kiungo cha kuwezesha**; hawezi kuingia kwenye akaunti yake mpaka atumie mojawapo. Hii inafanya kazi tu ikiwa seva inaweza kutuma barua pepe (`BREVO_API_KEY` au `RESEND_API_KEY` au `EMAIL_HOST`); vinginevyo uthibitisho unaachwa ili watu wasikwame.
