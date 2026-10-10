"""Starter content for `manage.py seed`. Everything here can be edited or replaced in /admin."""
from datetime import date, time

PLANS = [  # name, price, period, tagline, popular, features ("-" = not included)
    ("Free", 0, "Forever", "Get started and explore Sakinah.", False,
     "Create profile\nBrowse profiles (limited)\nSend likes (limited)\nView basic profiles\n-Messaging (limited)\n-Advanced search\n-See who likes you\n-Priority support"),
    ("Basic", 10000, "per month", "More visibility and better connections.", False,
     "All Free features\nFull profile access\nSend and receive messages\nAdvanced search filters\n-See who likes you\n-Profile boost (limited)\n-Featured in search\n-Priority support"),
    ("Silver", 25000, "per month", "Connect more and get better matches.", False,
     "All Basic features\nSee who likes you\nPriority in search results\n5 Profile boosts per month\nRead receipts (message seen)\n-Featured profile\n-Incognito mode\n-Priority support"),
    ("Gold", 50000, "per month", "Maximum visibility and serious connections.", True,
     "All Silver features\nUnlimited messages\nFeatured profile (top results)\n10 Profile boosts per month\nAdvanced matching filters\nIncognito mode (browse privately)\nSee who viewed your profile\nPriority support"),
    ("Tanzanite", 100000, "per month", "Ultimate experience for serious marriage seekers.", False,
     "All Gold features\nUnlimited profile boosts\nPersonal match recommendations\nDedicated account support\nEarly access to new features\nInvitation to premium events\nProfile verification badge\nVIP priority support"),
]

EVENT_CATEGORIES = [("Seminars", "seminars"), ("Workshops", "workshops"), ("Meetups", "meetups"), ("Community Events", "community-events")]

EVENTS = [  # title, date, start, end, city, category slug, description, image
    ("Preparing for a Successful Marriage", date(2026, 12, 15), time(10), time(13), "Arusha", "seminars",
     "Learn Islamic guidance and practical steps for a successful marriage.", "event1"),
    ("Singles & Marriage Meeting", date(2026, 12, 22), time(14), time(17), "Arusha", "meetups",
     "A friendly and guided meeting for single brothers and sisters.", "event2"),
    ("Nikah Preparation Workshop", date(2027, 1, 10), time(9), time(13), "Arusha", "workshops",
     "Guidance on the nikah process, rights and responsibilities.", "event3"),
    ("Women's Empowerment & Marriage", date(2027, 1, 18), time(10), time(12, 30), "Arusha", "seminars",
     "Building confidence, values and skills for a happy family life.", "event4"),
    ("Men's Role in a Successful Marriage", date(2027, 1, 25), time(14), time(17), "Arusha", "seminars",
     "Leadership, responsibilities and building a strong family.", "event5"),
    ("Community Outdoor Meetup", date(2027, 2, 5), time(9), time(14), "Arusha", "community-events",
     "A supervised outdoor social for verified members.", "event6"),
]

VENUE_INCLUDES = "Spacious hall with elegant decoration\nTables, chairs and VIP seating\nSound system and microphone\nBridal room (private)\nAir conditioning\nClean prayer area\nAmple parking space\nSecurity and event support staff"
VENUE_EXTRAS = "Catering (Halal food)\nDecoration (custom themes)\nPhotography and video coverage\nMC / Event coordination\nTransport arrangement\nLive streaming (for remote family)"
VENUE_HIGHLIGHTS = "people|Up to 300 Guests\nparking|Spacious Parking\nsnow|Air Conditioning\nfood|Catering Available"
WHY_VENDOR = "Verified and trusted vendor\nProfessional and experienced team\nCustomizable packages\nGood customer reviews\nHalal and Islamic-compliant services"

ADVERTS = [  # title, vendor, price, featured, image, photos
    ("Al-Noor Wedding Hall", "Al-Noor Events", 1500000, True, "advert_main", ["advert_thumb2", "advert_thumb3", "advert_thumb4", "advert_thumb5"]),
    ("Baraka Gardens", "Baraka Gardens", 1200000, False, "related1", []),
    ("Raha Wedding Hall", "Raha Halls", 2000000, False, "related2", []),
    ("Amani Gardens", "Amani Gardens", 1800000, False, "related3", []),
]
AL_NOOR_TEXT = ("Al-Noor Wedding Hall offers a beautiful, spacious and elegant venue for Islamic weddings (Nikah and Walima).\n"
                "Our hall is designed to provide a comfortable, modest and memorable environment for your special day, with modern facilities and professional services.\n"
                "We cater for small and large gatherings, ensuring your event runs smoothly with full support from our experienced team.")

ARTICLE_CATEGORIES = [("Marriage Guidance", "marriage-guidance", "people"), ("Relationships", "relationships", "heart-f"),
    ("Islamic Teachings", "islamic-teachings", "mosque"), ("Family Life", "family-life", "home"),
    ("Personal Development", "personal-development", "spark"), ("Health & Wellbeing", "health-wellbeing", "shield-c"),
    ("Success Stories", "success-stories", "star8"), ("Tips & How To", "tips-how-to", "doc"), ("News & Updates", "news-updates", "mega")]

ARTICLES = [  # title, category slug, image, published, featured, tags, excerpt, body
    ("Islamic Guidelines for a Successful Marriage", "marriage-guidance", "article1", date(2026, 9, 25), False, "Nikah, Marriage Tips",
     "Key principles from the Qur'an and Sunnah to build a strong and lasting marriage.",
     "Marriage in Islam is built on mercy, tranquillity and mutual respect. The Qur'an describes spouses as garments for one another: they protect, comfort and beautify each other.\n"
     "Start with sincere intentions, choose a partner for their faith and character, and keep both families involved with honesty.\n"
     "After the nikah, keep the relationship alive with kindness, consultation (shura) and regular prayer together. Small daily acts of care matter more than grand gestures."),
    ("How to Build Effective Communication in Marriage", "relationships", "article2", date(2026, 9, 20), False, "Communication, Trust",
     "Practical tips to improve understanding, trust and love between spouses.",
     "Most disagreements in marriage come from misunderstanding rather than bad intentions.\n"
     "Listen to understand, not to reply. Repeat back what you heard before you share your view, and speak about how something made you feel instead of blaming.\n"
     "Agree on a calm time to discuss serious matters, never in front of the children, and close every difficult conversation with a sincere dua for each other."),
    ("Raising Righteous Children in Today's World", "family-life", "article3", date(2026, 9, 18), False, "Family, Parenting",
     "Guidance for parents on nurturing Islamic values in the modern era.",
     "Children learn far more from what they see at home than from what they are told.\n"
     "Make the home a place of prayer, reading and gentle conversation. Limit screens together as a family and replace them with shared activities.\n"
     "Praise good character often, correct with mercy, and pray for your children by name every day."),
    ("Becoming a Better Version of Yourself Before Marriage", "personal-development", "article4", date(2026, 9, 15), False, "Personal Growth, Happiness",
     "Self-improvement steps to prepare mentally, spiritually and emotionally for marriage.",
     "The best preparation for marriage is working on yourself.\n"
     "Strengthen your relationship with Allah, learn the basic rights and duties of spouses, and build healthy habits with money, time and health.\n"
     "Reflect on your past relationships and family patterns honestly so you can bring maturity and patience into your new home."),
    ("The Virtues and Blessings of Marriage in Islam", "islamic-teachings", "article5", date(2026, 9, 10), False, "Islamic Guidance, Nikah",
     "Discover the rewards and wisdom behind marriage in the light of Islamic teachings.",
     "The Prophet (peace be upon him) called marriage half of the deen, and the Qur'an calls it a sign of Allah's mercy.\n"
     "Marriage protects chastity, brings companionship and builds the family that carries faith to the next generation.\n"
     "Every kind word, every meal shared and every sacrifice made for your spouse can be an act of worship when done for the sake of Allah."),
    ("How to Plan a Simple and Meaningful Nikah", "tips-how-to", "article6", date(2026, 9, 5), False, "Nikah, Financial Planning",
     "Step by step guide to organizing a beautiful and halal wedding within your means.",
     "A blessed nikah does not need to be expensive. The most blessed marriages are those with the least burden.\n"
     "Agree on the mahr and a realistic budget early, keep the guest list to family and close friends, and choose trusted vendors who respect Islamic values.\n"
     "Spend on what will last: counselling, a home and savings for the first years of marriage."),
    ("The Importance of Marriage in Islam", "islamic-teachings", "article_featured", date(2026, 8, 28), True, "Islamic Guidance, Marriage Tips",
     "Marriage is a Sunnah, a source of peace and a means to build a righteous society.",
     "Allah created spouses so that we may find tranquillity in them, and placed love and mercy between them.\n"
     "Marriage is a Sunnah of the prophets, a shield for the heart and the foundation of a righteous society.\n"
     "Approach it with knowledge, patience and good character, and it becomes a path to Jannah for both partners."),
    ("Dealing with Conflicts in Marriage", "relationships", "recent1", date(2026, 9, 22), False, "Conflict Resolution, Communication",
     "How to handle disagreements calmly, fairly and with mercy.",
     "Conflict is normal; how you handle it decides the health of your marriage.\n"
     "Pause before reacting, address the issue rather than the person, and look for a solution you can both accept.\n"
     "If you are stuck, seek advice from a trusted elder or counsellor from both families."),
    ("Islamic Financial Planning for Newlyweds", "tips-how-to", "recent2", date(2026, 9, 17), False, "Financial Planning, Family",
     "Simple, halal money habits for your first years together.",
     "Talk openly about income, debts and goals before and after the wedding.\n"
     "Avoid interest-based loans, set a monthly budget together, give sadaqah regularly and build an emergency fund.\n"
     "Clear agreement about money removes one of the most common sources of stress at home."),
    ("Maintaining Love and Respect", "marriage-guidance", "recent3", date(2026, 9, 12), False, "Happiness, Trust",
     "Keep the warmth of the early days alive for a lifetime.",
     "Love grows with attention. Thank each other, keep your promises and make time for each other every week.\n"
     "Respect shows in how you speak about your spouse when they are not in the room.\n"
     "Remember that you are a team working towards the same goal: pleasing Allah together."),
    ("Benefits of a Supportive Spouse", "family-life", "recent4", date(2026, 9, 8), False, "Family, Happiness",
     "Why encouragement at home helps both partners grow.",
     "A supportive spouse believes in your goals and helps you reach them.\n"
     "Support looks like sharing responsibilities, celebrating small wins and standing together in hard times.\n"
     "Couples who support each other report more peace at home and more patience with life's tests."),
]

ZAHRA = dict(height_cm=165, body_type="Average", languages="Swahili, English", workplace="Private School",
    income_range="TSh 500,000 - 1,000,000", willing_to_relocate="Yes", food_preference="Halal",
    hobbies="Reading, traveling, community service, cooking", exercise="Occasionally", prayer="Regularly (Alhamdulillah)",
    hijab="Yes", quran_reading="Regularly", values="Honesty, kindness, family, respect, Islamic principles",
    father_status="Alive", mother_status="Alive", siblings=4, family_type="Moderate", family_location="Dar es Salaam",
    about_family="Supportive and God-fearing family", pref_age_min=25, pref_age_max=35, pref_marital="Never Married",
    pref_location="Tanzania (Any)", pref_education="Diploma or higher", pref_occupation="Any", pref_prayer="Practices regularly",
    pref_values="Islamic values, honesty, respect", pref_relocate="Open", pref_more="Serious, family-oriented, good character",
    bio="I am a kind, respectful and family-oriented woman who values Islam, honesty and mutual respect. I enjoy learning, community work, and spending time with family. I am looking for a serious and committed partner to build a happy and peaceful Islamic marriage, InshaAllah.")

MESSAGE_TEMPLATES = [  # name, description, subject, body, icon, color
    ("Welcome New Member", "Welcome message for new registrations.", "Karibu Sakinah, {name}!",
     "Assalaam alaikum {name},\n\nWelcome to Sakinah. Complete your profile and add a clear photo so others can get to know you.\n\nMay Allah make it easy for you.", "heart-f", "#2546a8"),
    ("Profile Verification", "Notify member about verification status.", "Your profile is verified",
     "Hello {name}, your profile has been verified and now shows the Imethibitishwa badge.", "check-c", "#16a05a"),
    ("Match Suggestion", "Notify members about new matches.", "New matches for you",
     "Hello {name}, new members who match your preferences have joined. Visit Find a Match to see them.", "heart-f", "#e23d5a"),
    ("Event Invitation", "Invite members to upcoming events.", "You're invited: upcoming Sakinah event",
     "Hello {name}, join our next seminar and meet verified members in a respectful environment. Register on the Events page.", "cal-f", "#e23d5a"),
    ("Premium Plan Promotion", "Promote premium membership plans.", "Get more matches with Premium",
     "Hello {name}, upgrade to Premium to see who likes you, message without limits and get featured.", "crown", "#16a05a"),
    ("Newsletter", "Monthly newsletter with latest updates.", "Sakinah monthly update",
     "Hello {name}, here are this month's new articles, events and success stories from Sakinah.", "doc", "#e0a21a"),
    ("Account Update", "Notify about account changes.", "Important update about your account",
     "Hello {name}, we have updated our terms and privacy policy. Please take a moment to review them.", "gear", "#d4213d"),
]

# ----- member dashboard designs (seed_images/v4) -----
MORE_MEMBERS = [  # name, age, gender, city, occupation, education, image, bio
    ("Fatma", 29, "F", "Arusha", "Nurse", "Diploma in Nursing", "w_fatma",
     "Ninapenda kuhudumia watu na ninathamini familia. Natafuta mume mcha Mungu, mwenye heshima na malengo ya kujenga familia."),
    ("Zuhura", 31, "F", "Dodoma", "Business Lady", "Bachelor Degree", "w_zuhura",
     "Mfanyabiashara mwenye bidii. Ninapenda dini yangu na familia; natafuta mwenza wa maisha kwa ndoa yenye utulivu."),
    ("Hawa", 26, "F", "Zanzibar", "Accountant", "Bachelor of Accounting", "w_hawa",
     "Ninaishi Zanzibar. Ninathamini uaminifu na mawasiliano mazuri. Natafuta mume anayemcha Mungu."),
    ("Rehema", 28, "F", "Tanga", "Pharmacist", "Bachelor of Pharmacy", "w_rehema",
     "Mfamasia mpenda watu na amani. Natafuta mwenza mwenye maadili, dini na malengo ya familia."),
    ("Sadia", 32, "F", "Kilimanjaro", "Lecturer", "Master's Degree", "w_sadia",
     "Mhadhiri ninayependa kujifunza na kufundisha. Natafuta ndoa yenye upendo, heshima na misingi ya Kiislamu."),
    ("Aisha", 25, "F", "Morogoro", "Software Developer", "Bachelor of Computer Science", "w_aisha",
     "Ninapenda teknolojia, kusoma na familia. Natafuta mume mwenye imani, mcheshi na mwenye malengo."),
]
MOHAMMED = dict(name="Mohammed Kapera", age=38, gender="M", city="Dar es Salaam", occupation="Business Owner", education="Bachelor Degree",
    verified=True, height_cm=175, body_type="Average", origin="African (Tanzanian)", languages="Swahili, English",
    income_range="TSh 2,000,000 - 5,000,000 per month", willing_to_relocate="Yes", workplace="Own business",
    interests="Qur'an, Islamic Lectures, Coaching, Travel, Community Service, Family Life, Halal Business, Sports, Reading",
    lifestyle="Healthy lifestyle, Prefer simple lifestyle, Open-minded", pref_age_min=25, pref_age_max=35, pref_marital="Never Married",
    pref_location="Tanzania (Preferably Dar es Salaam)", pref_education="Any", pref_prayer="Practising Muslim", prayer="Regularly",
    headline="Seeking a righteous life partner",
    bio="Assalamu Alaikum. Mimi ni mtu mcha Mungu, ninayetaka kujenga familia ya kiislamu iliyojaa upendo, heshima na utulivu. "
        "Ninapenda kusoma Qur'an, kushiriki katika shughuli za kijamii na kuendelea kujifunza. Ninataka mpenzi mwema, muaminifu na anayemcha Allah.")

MEMBER_EVENT_CATEGORIES = [("Islamic Lectures", "islamic-lectures"), ("Marriage Seminars", "marriage-seminars"),
    ("Counselling Sessions", "counselling-sessions"), ("Men's Programs", "mens-programs"), ("Women's Programs", "womens-programs")]
MEMBER_EVENTS = [  # title, date, start, end, city, category slug, capacity, tags, description, image
    ("Islamic Marriage Seminar", date(2026, 10, 15), time(14), time(17), "Dar es Salaam", "marriage-seminars", 80, "Seminar, Education",
     "Learn the fundamentals of a blessed Islamic marriage and family life.", "event1"),
    ("Qur'an and Family Life", date(2026, 10, 28), time(15), time(18), "Arusha", "islamic-lectures", 100, "Islamic Lecture, Spiritual",
     "Guidance from the Qur'an and Sunnah for building a strong family.", "event2"),
    ("Marriage Counselling Session", date(2026, 11, 12), time(10), time(13), "Dodoma", "counselling-sessions", 50, "Counselling, Community",
     "Interactive session with qualified Islamic counsellors.", "event3"),
    ("Sisters Forum: Building a Sakinah Home", date(2026, 11, 25), time(14), time(17), "Zanzibar", "womens-programs", 60, "Women, Discussion",
     "A special forum for sisters on marriage, family life and personal growth.", "event4"),
    ("Brothers Forum: Becoming a Better Husband", date(2026, 12, 5), time(14), time(17), "Mwanza", "mens-programs", 60, "Men, Development",
     "Guidance, experience sharing and practical tips for responsible husbandhood.", "event5"),
    ("Sakinah Community Iftar & Networking", date(2026, 12, 20), time(18), time(21), "Dar es Salaam", "community-events", 120, "Community, Networking",
     "Meet and connect with like-minded Muslims in a peaceful environment.", "event6"),
]
