/* ════════════════════════════════════════════
   خانه ماورا — Site Logic v3 (public pages)
   + bilingual (FA/EN) + bio toggle + flip gallery
   ════════════════════════════════════════════ */

// ── Path helpers ──
function pp(p) {
  const inPages = location.pathname.includes('/pages/');
  if (p.startsWith('http')) return p;
  // Pre-existing gap (not introduced here): pp('index.html') was returned
  // unprefixed even when called from a page inside /pages/, so the site
  // logo / "home" link 404'd from every non-home page. One targeted line,
  // not a pp() rewrite — everything else below is unchanged.
  if (p === 'index.html') return inPages ? '../index.html' : p;
  if (inPages && p.startsWith('assets/')) return '../' + p;
  if (inPages && p.startsWith('pages/')) return p.replace('pages/', '');
  // Uploaded media (poster/gallery/video/team photos) comes back from the
  // API as a bare relative path — "media/poster/xxx.jpg" — with no case
  // above matching it, so it fell through to `return p` unchanged. From
  // site root that resolves fine; from any /pages/*.html (event detail,
  // team, portfolio — most image displays) the browser resolved it
  // against the wrong base and 404'd. onerror="coverFallback(...)" on
  // every image tag silently swapped in a fallback icon instead of
  // surfacing this, which is why it went unnoticed.
  if (inPages && p.startsWith('media/')) return '../' + p;
  return p;
}

// ── Escape (XSS-safe output) ──
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function reducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/* ═══════════ I18N ═══════════ */
const I18N = {
  fa: {
    logo: 'خانه ماورا',
    q1: '«آنچه می‌جویید، شما را می‌جوید.»', q2: '«راه، با نخستین گام آغاز می‌شود.»', q3: '«آرامش از درون می‌آید؛ آن را بیرون نجویید.»', q4: '«بگذار هر چه هست، همان‌گونه که هست بماند.»', q5: '«هر روز، آغازی دوباره است.»', q6: '«شناختن خویش، آغاز همه‌ی شناخت‌هاست.»',
    nav_about: 'درباره ماورا', nav_mansour: 'منصور نصیری', nav_team: 'اعضای خانه ماورا', nav_events: 'رویدادها', nav_podcast: 'پادکست', nav_companion: 'همراهی', nav_contact: 'تماس', nav_account: 'حساب من',
    hero_eyebrow: 'هنر · آگاهی · زندگی', hero_t1: 'خانه‌ی', hero_t2: 'ماورا',
    hero_tag: 'سفری به سوی خویشتن، از مسیر آگاهی، به یاری هنر',
    cta_events: 'رویدادها', cta_about: 'درباره ماورا',
    w_art: 'هنر', w_aware: 'آگاهی', w_life: 'زندگی', w_dialogue: 'گفتگو', w_poetry: 'شعر', w_music: 'موسیقی', w_self: 'خودشناسی', w_theater: 'تئاتر', w_companion: 'همراهی',
    paths_eyebrow: 'راه‌ها', paths_title: 'از کدام راه می‌آیی؟',
    p_theater: 'تئاتر', p_podcast: 'پادکست', p_music: 'موسیقی', p_self: 'خودشناسی', p_poetry: 'شعر', p_dialogue: 'گفتگو', p_companion: 'همراهی',
    bio_eyebrow: 'بنیان‌گذار خانه ماورا', bio_name: 'منصور نصیری', bio_role: 'بازیگر، کارگردان و نویسنده',
    bio_short: 'منصور نصیری، بازیگر و کارگردان سینما و تئاتر، خانه ماورا را برای پیوند هنر و آگاهی پایه گذاشته است؛ جایی که هنر دست‌مایه‌ی نگاهی دوباره به خویشتن می‌شود.',
    bio_full: ' او با بیش از دو دهه تجربه در تئاتر، سینما و تلویزیون، مسیرش را از صحنه آغاز کرد و در آثارش، بازیگری را راهی برای شناخت عمیق‌تر انسان می‌داند. پادکست «ما ورای بازیگری»، کارگاه‌ها و جلسات همراهی، ادامه‌ی همین راه‌اند.',
    bio_more: 'بیشتر', bio_less: 'کمتر',
    live_eyebrow: 'زنده', live_title: 'همین حالا در خانه ماورا',
    up_eyebrow: 'در راه', up_title: 'رویدادهای پیش‌رو',
    all_events: 'همه رویدادها',
    b_live: 'در حال اجرا', b_soon: 'به‌زودی', b_ended: 'آرشیو',
    b_details: 'جزئیات', b_book: 'جزئیات و رزرو',
    empty_up: 'رویداد پیش‌رویی ثبت نشده — به‌زودی اینجا می‌بینمت.',
    empty_cat: 'رویدادی در این دسته ثبت نشده.', empty_event: 'رویداد پیدا نشد.',
    gal_eyebrow: 'گالری', gal_title: 'از نگاه من', gal_link: 'فایل رزومه',
    events_eyebrow: 'تقویم', events_title: 'رویدادهای خانه ماورا', events_sub: 'همین حالا، به‌زودی، و آنچه گذشت', tag_all: 'همه',
    info_label: 'اطلاعات', loc_label: 'مکان', date_label: 'تاریخ', book_tg: 'رزرو از تلگرام',
    reserve_title: 'رزرو این رویداد', reserve_name: 'نام و نام خانوادگی', reserve_phone: 'شماره موبایل', reserve_email: 'ایمیل (برای پیگیری رزرو و دریافت بلیت)',
    bk_date: 'تاریخ اجرا', bk_session: 'انتخاب سانس', bk_remaining: (n) => n + ' نفر باقی مانده', bk_full: 'تکمیل ظرفیت', bk_waitlist: 'افزودن به لیست انتظار',
    bk_qty: 'تعداد بلیت', bk_each: 'قیمت هر بلیت', bk_total: 'مبلغ کل', bk_buyer: 'اطلاعات خریدار', bk_confirm: 'ثبت رزرو',
    bk_done: 'رزرو شما ثبت شد — کد پیگیری شما:', bk_sel_date: 'ابتدا یک روز اجرا انتخاب کن', bk_tracking_id: 'شماره پیگیری',
    bk_waitlist_done: 'درخواست شما در لیست انتظار ثبت شد؛ در صورت آزاد شدن ظرفیت با شما تماس می‌گیریم.',
    pay_title: 'پرداخت (کارت به کارت)', pay_upload: 'آپلود رسید پرداخت', pay_ok: 'رسید شما دریافت شد. پس از بررسی ادمین، تایید نهایی به ایمیل‌تان ارسال می‌شود.',
    pay_fallback: 'اطلاعات کارت از پنل ادمین تنظیم می‌شود — برای دریافت شماره کارت به تلگرام پیام بدهید.',
    fb_title: 'بازخورد و نظرات', fb_name_ph: 'نام شما (اختیاری)', fb_text_ph: 'نظر خود را بنویسید...', fb_submit: 'ثبت', empty_comment: 'هنوز نظری ثبت نشده.',
    f_tag: 'سفری به سوی خویشتن<br>از مسیر آگاهی، به یاری هنر',
    f_social: 'شبکه‌های اجتماعی', f_contact: 'تماس',
    f_social_ig: 'اینستاگرام', f_social_tg: 'تلگرام', f_castbox: 'Castbox',
    f_contact_tg: 'تلگرام: mavara_home', f_contact_page: 'صفحه تماس', f_city: 'تهران، ایران',
    f_copy: '© ۱۴۰۴ خانه ماورا — Maavara Home',
    about_m_eyebrow: 'ما که هستیم', about_m_title: 'درباره خانه ماورا', about_m_sub: 'سفری به سوی خویشتن، از مسیر آگاهی، به یاری هنر',
    about_m_p1: 'خانه ماورا فضایی است برای پیوند هنر، آگاهی و زندگی. این مجموعه به همت منصور نصیری پایه‌گذاری شده و در مسیرهای گوناگون — تئاتر، پادکست، خودشناسی، شعر، گفتگو، موسیقی و همراهی — میزبان مخاطبان است.',
    about_m_p2: 'آنچه در خانه ماورا می‌گذرد، تلاشی است برای نگاهی دوباره به خویشتن؛ جایی که هنر نه فقط برای دیده شدن، که برای دیدن خود به کار می‌آید.',
    contact_eyebrow: 'در ارتباط باشیم', contact_title: 'تماس با خانه ماورا', contact_sub: 'برای رویدادها، گفتگوها و همراهی',
    c_tg: 'تلگرام', c_tg_d: 't.me/mavara_home', c_ig: 'اینستاگرام', c_ig_d: '@mansournasirii', c_loc: 'موقعیت', c_loc_d: 'تهران، ایران',
    companion_eyebrow: 'همراهی', companion_title: 'گاهی برای دیدن راه، داشتن یک همراه کافی است', companion_sub: 'جلسات گفت‌وگوی عمیق و بدون قضاوت — به میزبانی منصور نصیری',
    companion_p1: 'همه‌ی ما در مقاطعی با پرسش‌ها، تردیدها یا تصمیم‌هایی روبه‌رو می‌شویم که گفت‌وگو می‌تواند نگاه تازه‌ای ایجاد کند. در جلسات همراهی، در فضایی امن و بدون قضاوت، موضوعاتی را بررسی می‌کنیم که برایت اهمیت دارند — از مسائل شخصی و روابط تا مسیر شغلی، بازیگری و خلاقیت.',
    companion_p2: 'این جلسات درمان یا روان‌درمانی نیستند؛ بلکه فرصتی برای گفت‌وگو، اندیشیدن و نگاه کردن به مسائل از زاویه‌ای تازه‌اند.',
    companion_h3: 'این جلسات مناسب کسانی است که:', companion_li1: 'به دنبال گفت‌وگویی عمیق و صادقانه هستند', companion_li2: 'به جای فرار از مسائل، به دنبال کشف راه‌حل هستند', companion_li3: 'می‌خواهند مسیر شخصی یا هنری خود را شفاف‌تر ببینند', companion_li4: 'به خودشناسی و زندگی با آگاهی علاقه‌مندند',
    companion_note: 'نحوه برگزاری: <strong style="color:var(--navy)">آنلاین و تلفنی</strong> — با تعیین وقت قبلی — مدت هر جلسه: <strong style="color:var(--navy)">یک ساعت</strong>',
    companion_cta: 'هماهنگی از تلگرام: t.me/mavara_home',
    podcast_eyebrow: 'پادکست', podcast_title: 'ما ورای بازیگری', podcast_sub: 'به میزبانی منصور نصیری',
    podcast_p: 'پادکست «ما ورای بازیگری» در اپل پادکست و کست‌باکس منتشر می‌شود و بر <strong>آگاهی‌بخشی</strong> به علاقه‌مندان، دانشجویان و بازیگران تمرکز دارد؛ از خودشناسی و کشف و شهود تا تحلیل ایگو و پیوند هنر با زندگی.',
    podcast_castbox: 'کست‌باکس', podcast_castbox_d: 'castbox.fm', podcast_apple: 'اپل پادکست', podcast_apple_d: 'Apple Podcasts', podcast_ig: 'اینستاگرام', podcast_ig_d: '@beyond_the_acting',
    podcast_support: 'حمایت از پادکست', podcast_support_eyebrow: 'حمایت', podcast_host: 'میزبان و سازنده: منصور نصیری', podcast_card: 'شماره کارت (رفاه):',
    mansour_eyebrow: 'بازیگر · کارگردان · نویسنده', mansour_title: 'منصور نصیری', mansour_sub: 'بازیگر، کارگردان و نویسنده — مؤسس خانه ماورا',
    live_pill: 'در حال اکران',
    mansour_bio: 'متولد ۱۳۶۶ در تهران. فعالیت هنری را از تئاتر آغاز کرد و پس از تحصیل در آکادمی سمندریان، مسیرش را در سینما و سریال ادامه داد. برای او بازیگری راهی برای شناخت عمیق‌تر انسان است.',
    mansour_bio_full: ' او در کنار بازیگری، به آموزش، پادکست و ساختن فضاهایی برای گفت‌وگوی صادقانه و خودشناسی می‌پردازد. خانه ماورا ادامه‌ی همین مسیر است: پیوند هنر با دیدن دقیق‌تر زندگی.',
    samples_title: 'نمونه کارها', tab_all: 'همه', tab_photo: 'عکس', tab_video: 'ویدیو', resume_footer: 'با افتخار، برای دوستداران هنر',
    empty_sample: 'نمونه‌ای برای نمایش موجود نیست.',
    m_en_title: 'عنوان انگلیسی', m_year: 'سال', m_director: 'کارگردان', m_role: 'نقش', m_festival: 'جشنواره', m_desc: 'توضیحات'
  },
  en: {
    logo: 'Mavara House',
    q1: '“What you seek is seeking you.”', q2: '“The journey begins with a single step.”', q3: '“Peace comes from within — do not seek it without.”', q4: '“Let things be as they are, just this once.”', q5: '“Every day is a new beginning.”', q6: '“Knowing the self is the beginning of all knowing.”',
    nav_about: 'About Mavara', nav_mansour: 'Mansour Nasiri', nav_team: 'Our Team', nav_events: 'Events', nav_podcast: 'Podcast', nav_companion: 'Companionship', nav_contact: 'Contact', nav_account: 'My Account',
    hero_eyebrow: 'Art · Awareness · Life', hero_t1: 'Mavara', hero_t2: 'House',
    hero_tag: 'A journey toward the self — through awareness, by the hand of art.',
    cta_events: 'Events', cta_about: 'About Mavara',
    w_art: 'Art', w_aware: 'Awareness', w_life: 'Life', w_dialogue: 'Dialogue', w_poetry: 'Poetry', w_music: 'Music', w_self: 'Self-knowledge', w_theater: 'Theater', w_companion: 'Companionship',
    paths_eyebrow: 'Paths', paths_title: 'Which path calls to you?',
    p_theater: 'Theater', p_podcast: 'Podcast', p_music: 'Music', p_self: 'Self-knowledge', p_poetry: 'Poetry', p_dialogue: 'Dialogue', p_companion: 'Companionship',
    bio_eyebrow: 'Founder of Mavara House', bio_name: 'Mansour Nasiri', bio_role: 'Actor, Director & Writer',
    bio_short: 'Mansour Nasiri, actor and director of cinema and theater, founded Mavara House to unite art and awareness — a place where art becomes the handmaid of a renewed look at the self.',
    bio_full: ' With more than two decades on stage, screen and television, he began his path in theater and believes acting is a way to understand the human being more deeply. The podcast "Beyond Acting", workshops and companionship sessions continue that path.',
    bio_more: 'Read more', bio_less: 'Show less',
    live_eyebrow: 'Live', live_title: "What's on at Mavara now",
    up_eyebrow: 'Coming up', up_title: 'Upcoming events',
    all_events: 'All events',
    b_live: 'Now showing', b_soon: 'Coming soon', b_ended: 'Archive',
    b_details: 'Details', b_book: 'Details & booking',
    empty_up: 'No upcoming events yet — see you here soon.',
    empty_cat: 'No events in this category yet.', empty_event: 'Event not found.',
    gal_eyebrow: 'Gallery', gal_title: 'Through my lens', gal_link: 'Résumé',
    events_eyebrow: 'Calendar', events_title: 'Mavara events', events_sub: 'Now, soon, and what has passed', tag_all: 'All',
    info_label: 'Details', loc_label: 'Location', date_label: 'Date', book_tg: 'Book on Telegram',
    reserve_title: 'Reserve this event', reserve_name: 'Full name', reserve_phone: 'Mobile number', reserve_email: 'Email (to track your reservation and get your ticket)',
    bk_date: 'Show date', bk_session: 'Choose a session', bk_remaining: (n) => n + ' left', bk_full: 'Sold out', bk_waitlist: 'Join waiting list',
    bk_qty: 'Number of tickets', bk_each: 'Price per ticket', bk_total: 'Total', bk_buyer: 'Your details', bk_confirm: 'Confirm reservation',
    bk_done: 'Your reservation is in — tracking code:', bk_sel_date: 'Pick a show date first', bk_tracking_id: 'Tracking number',
    bk_waitlist_done: "You're on the waiting list — we'll reach out if a seat opens up.",
    pay_title: 'Payment (bank transfer)', pay_upload: 'Upload payment receipt', pay_ok: "Receipt received. You'll get a confirmation email once it's reviewed.",
    pay_fallback: 'Payment details are set from the admin panel — message us on Telegram for the card number.',
    fb_title: 'Feedback & comments', fb_name_ph: 'Your name (optional)', fb_text_ph: 'Write your comment...', fb_submit: 'Submit', empty_comment: 'No comments yet.',
    f_tag: 'A journey toward the self<br>through awareness, by the hand of art',
    f_social: 'Social media', f_contact: 'Contact',
    f_social_ig: 'Instagram', f_social_tg: 'Telegram', f_castbox: 'Castbox',
    f_contact_tg: 'Telegram: mavara_home', f_contact_page: 'Contact page', f_city: 'Tehran, Iran',
    f_copy: '© 2025 Mavara House — Maavara Home',
    about_m_eyebrow: 'Who we are', about_m_title: 'About Mavara House', about_m_sub: 'A journey toward the self, through awareness, by the hand of art',
    about_m_p1: 'Mavara House is a space where art, awareness and life meet. Founded by Mansour Nasiri, it welcomes audiences along many paths — theater, podcast, self-knowledge, poetry, dialogue, music and companionship.',
    about_m_p2: 'What happens at Mavara House is an attempt to look at the self anew; a place where art serves not only to be seen, but to see.',
    contact_eyebrow: "Let's stay in touch", contact_title: 'Contact Mavara House', contact_sub: 'For events, conversations & companionship',
    c_tg: 'Telegram', c_tg_d: 't.me/mavara_home', c_ig: 'Instagram', c_ig_d: '@mansournasirii', c_loc: 'Location', c_loc_d: 'Tehran, Iran',
    companion_eyebrow: 'Companionship', companion_title: 'Sometimes, to see the way, a companion is enough', companion_sub: 'Deep, judgment-free conversations — hosted by Mansour Nasiri',
    companion_p1: 'At some point, we all face questions, doubts or decisions where a conversation can open a fresh perspective. In companionship sessions, in a safe and judgment-free space, we explore what matters to you — from personal matters and relationships to your career, acting and creativity.',
    companion_p2: 'These sessions are not therapy or psychotherapy; they are an opportunity to talk, to think, and to look at things from a new angle.',
    companion_h3: 'These sessions suit those who:', companion_li1: 'seek a deep and honest conversation', companion_li2: 'look for solutions instead of running from them', companion_li3: 'want to see their personal or artistic path more clearly', companion_li4: 'are drawn to self-knowledge and living with awareness',
    companion_note: 'Format: <strong style="color:var(--navy)">online & by phone</strong> — by appointment — each session: <strong style="color:var(--navy)">one hour</strong>',
    companion_cta: 'Arrange via Telegram: t.me/mavara_home',
    podcast_eyebrow: 'Podcast', podcast_title: 'Beyond Acting', podcast_sub: 'Hosted by Mansour Nasiri',
    podcast_p: 'The podcast "Beyond Acting" is released on Apple Podcasts and Castbox, focused on <strong>raising awareness</strong> among enthusiasts, students and actors — from self-knowledge and intuition to ego analysis and the bond between art and life.',
    podcast_castbox: 'Castbox', podcast_castbox_d: 'castbox.fm', podcast_apple: 'Apple Podcasts', podcast_apple_d: 'Apple Podcasts', podcast_ig: 'Instagram', podcast_ig_d: '@beyond_the_acting',
    podcast_support: 'Support the podcast', podcast_support_eyebrow: 'Support', podcast_host: 'Host & producer: Mansour Nasiri', podcast_card: 'Card number (Refah):',
    mansour_eyebrow: 'Actor · Director · Writer', mansour_title: 'Mansour Nasiri', mansour_sub: 'Actor, director & writer — founder of Mavara House',
    live_pill: 'Now showing',
    mansour_bio: 'Born 1987 in Tehran. He began his artistic career in theater and, after studying at the Samandarian Academy, continued in cinema and television. For him, acting is a way to understand the human being more deeply.',
    mansour_bio_full: ' Alongside acting, he teaches, hosts a podcast and creates spaces for honest conversation and self-knowledge. Mavara House continues that path: connecting art with a more attentive way of seeing life.',
    samples_title: 'Selected works', tab_all: 'All', tab_photo: 'Photo', tab_video: 'Video', resume_footer: 'With pride, for lovers of art',
    empty_sample: 'Nothing to show yet.',
    m_en_title: 'English title', m_year: 'Year', m_director: 'Director', m_role: 'Role', m_festival: 'Festival', m_desc: 'Description'
  }
};

function lang() {
  try { return (localStorage.getItem('mh_lang') || 'fa') === 'en' ? 'en' : 'fa'; } catch { return 'fa'; }
}
const T = (k) => (I18N[lang()][k] ?? I18N.fa[k] ?? k);

function applyLang() {
  const l = lang();
  document.documentElement.lang = l === 'en' ? 'en' : 'fa';
  document.documentElement.dir = l === 'en' ? 'ltr' : 'rtl';
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = T(el.dataset.i18n); });
  document.querySelectorAll('[data-i18n-html]').forEach(el => { el.innerHTML = T(el.dataset.i18nHtml); });
}
function setLang(l) {
  try { localStorage.setItem('mh_lang', l); } catch {}
  applyLang();
  loadHeader();
  loadFooter();
  dispatchPage();
  window.dispatchEvent(new Event('mv-lang'));
}

// ── Shared SVG icons ──
const LOGO_SVG = '<svg class="site-logo" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 140" role="img" aria-label="Mavara Home"><g fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><circle cx="120" cy="56" r="42"/><circle cx="120" cy="56" r="32" opacity=".45" stroke-width="1.2"/><path d="M120 26 L147 52 V88 H93 V52 Z"/><path d="M103 88 V70 a17 17 0 0 1 34 0 V88"/><path d="M120 26 C117 17 121 12 128 10 C126 15 128 19 133 20 C127 24 122 26 120 26 Z"/></g><text x="120" y="128" text-anchor="middle" font-family="Georgia,\'Times New Roman\',serif" font-size="19" letter-spacing="6" fill="currentColor">Mavara Home</text></svg>';
const ICON_STAR = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 6.9L21 9.3l-5.4 4.5L17.4 21 12 17.2 6.6 21l1.8-7.2L3 9.3l6.6-.4z"/></svg>';
const ICON_PIN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s-7-5.5-7-11a7 7 0 0 1 14 0c0 5.5-7 11-7 11z"/><circle cx="12" cy="10" r="2.6"/></svg>';

function coverFallback(el) {
  el.classList.add('is-fallback');
  el.innerHTML = ICON_STAR + '<span>خانه ماورا</span>';
}
function coverHTML(e) {
  const img = e.poster || (Array.isArray(e.gallery) && e.gallery[0]) || null;
  if (!img) return '<div class="event-cover is-fallback">' + ICON_STAR + '<span>خانه ماورا</span></div>';
  return '<div class="event-cover"><img src="' + pp(img) + '" alt="' + esc(evTitle(e)) + '" loading="lazy" onerror="coverFallback(this.parentNode)"></div>';
}
function evTitle(e) { return (lang() === 'en' && e.title_en) ? e.title_en : e.title; }
function evLoc(e) { return (lang() === 'en' && e.location_en) ? e.location_en : (e.location || ''); }
function evCtx(e) { return (lang() === 'en' && e.context_en) ? e.context_en : (e.context || e.description || ''); }
function tagsHTML(e) {
  return (e.tags || []).length ? '<div class="event-tags">' + e.tags.map(t => '<span>' + esc(t) + '</span>').join('') + '</div>' : '';
}
function badgeHTML(status) {
  return status === 'ongoing' ? '<span class="event-badge event-badge--live">' + T('b_live') + '</span>'
       : status === 'upcoming' ? '<span class="event-badge event-badge--soon">' + T('b_soon') + '</span>'
       : '<span class="event-badge event-badge--ended">' + T('b_ended') + '</span>';
}

// ── Header ──
let __activeNav = null;
function loadHeader(active) {
  const el = document.getElementById('header');
  if (!el) return;
  if (active) __activeNav = active;
  const l = lang();
  const logo = pp('assets/images/logo/mavara-home-logo.png');
  const home = pp('index.html');
  const nav = [
    { h: 'pages/about-mavara.html', l: T('nav_about') },
    { h: 'pages/about-mansour.html', l: T('nav_mansour') },
    { h: 'pages/team.html', l: T('nav_team') },
    { h: 'pages/events.html', l: T('nav_events') },
    { h: 'pages/podcast.html', l: T('nav_podcast') },
    { h: 'pages/companionship.html', l: T('nav_companion') },
    { h: 'pages/contact.html', l: T('nav_contact') },
    { h: 'pages/account.html', l: T('nav_account') }
  ];
  el.innerHTML = `<header class="site-header" id="siteHeader"><div class="progress-bar" id="progressBar"></div><div class="header-inner">
    <a class="logo" href="${home}"><img src="${logo}" alt="${T('logo')}">${T('logo')}</a>
    <nav class="nav-links" id="navLinks">${nav.map((n, i) => `<a href="${pp(n.h)}"${('pages/' + (__activeNav||'')) === n.h ? ' class="active"' : ''} style="--i:${i}">${n.l}</a>`).join('')}</nav>
    <div style="display:flex;align-items:center">
      <div class="lang-toggle" role="group" aria-label="Language">
        <button type="button" data-lang="fa"${l === 'fa' ? ' class="active"' : ''}>فا</button>
        <button type="button" data-lang="en"${l === 'en' ? ' class="active"' : ''}>EN</button>
      </div>
      <button class="hamburger" id="hamburger" aria-label="منو"><span></span><span></span><span></span></button>
    </div>
  </div></header>`;
  el.querySelectorAll('.lang-toggle button').forEach(b => b.onclick = () => setLang(b.dataset.lang));
  const btn = document.getElementById('hamburger');
  const nl = document.getElementById('navLinks');
  const toggle = (open) => { nl.classList.toggle('open', open); btn.classList.toggle('open', open); };
  btn.onclick = () => toggle(!nl.classList.contains('open'));
  nl.querySelectorAll('a').forEach(a => a.onclick = () => toggle(false));
}

// ── Footer ──
function loadFooter() {
  const el = document.getElementById('footer');
  if (!el) return;
  const logo = pp('assets/images/logo/mavara-home-logo.png');
  const home = pp('index.html');
  el.innerHTML = `<footer class="site-footer"><div class="footer-grid">
    <div class="footer-col"><a class="logo logo--footer" href="${home}">${LOGO_SVG}<span>${T('logo')}</span></a>
      <p class="footer-tagline">${T('f_tag')}</p></div>
    <div class="footer-col"><h4>${T('logo')}</h4>
      <a href="${pp('pages/about-mavara.html')}">${T('nav_about')}</a>
      <a href="${pp('pages/about-mansour.html')}">${T('nav_mansour')}</a>
      <a href="${pp('pages/events.html')}">${T('nav_events')}</a>
      <a href="${pp('pages/companionship.html')}">${T('nav_companion')}</a></div>
    <div class="footer-col"><h4>${T('f_social')}</h4>
      <a href="https://instagram.com/mansournasirii" target="_blank" rel="noopener">${T('f_social_ig')}</a>
      <a href="https://t.me/mavara_home" target="_blank" rel="noopener">${T('f_social_tg')}</a>
      <a href="https://castbox.fm/channel/Maavara-Home" target="_blank" rel="noopener">${T('f_castbox')}</a></div>
    <div class="footer-col"><h4>${T('f_contact')}</h4>
      <a href="https://t.me/mavara_home" target="_blank" rel="noopener">${T('f_contact_tg')}</a>
      <a href="${pp('pages/contact.html')}">${T('f_contact_page')}</a>
      <p class="footer-tagline" style="margin-top:10px">${T('f_city')}</p></div>
  </div><p class="footer-copy">${T('f_copy')}</p></footer>`;
}

// ── Slider (now showing) ──
async function initSlider() {
  const track = document.getElementById('sliderTrack');
  if (!track) return;
  await API.init();
  const events = API.events.active();
  const section = document.getElementById('sliderSection');
  if (!events.length) { if (section) section.style.display = 'none'; return; }
  if (section) section.style.display = '';
  track.innerHTML = events.map(e => {
    const loc = evLoc(e) ? `<p class="event-meta">${ICON_PIN}${esc(evLoc(e))}</p>` : '';
    return `<div class="slider-slide"><div class="event-card">${coverHTML(e)}<div class="event-card-body">
      ${badgeHTML(e.status)}<h3>${esc(evTitle(e))}</h3>${loc}${tagsHTML(e)}
      <a class="btn btn--outline" href="${pp('pages/event-detail.html')}?id=${encodeURIComponent(e.id)}">${T('b_book')}</a>
    </div></div></div>`;
  }).join('');
  const dots = document.getElementById('sliderDots');
  if (dots) {
    dots.innerHTML = events.map((_, i) => `<button class="slider-dot${i === 0 ? ' active' : ''}" aria-label="slide ${i + 1}"></button>`).join('');
    dots.querySelectorAll('button').forEach((d, i) => d.onclick = () => track.scrollTo({ left: track.children[i].offsetLeft - track.offsetLeft, behavior: 'smooth' }));
    track.onscroll = () => {
      const i = Math.round(track.scrollLeft / (track.children[0].offsetWidth + 16));
      dots.querySelectorAll('button').forEach((d, j) => d.classList.toggle('active', j === i));
    };
  }
}

// ── Events preview (upcoming) ──
async function initEventsPreview() {
  const el = document.getElementById('eventsPreview');
  if (!el) return;
  await API.init();
  const ev = API.events.all().filter(e => e.status === 'ongoing' || e.status === 'upcoming').slice(0, 3);
  el.innerHTML = ev.length ? ev.map(e => {
    const meta = [e.date, evLoc(e)].filter(Boolean).join(' · ');
    return `<div class="event-card">${coverHTML(e)}<div class="event-card-body">
      ${badgeHTML(e.status)}<h3>${esc(evTitle(e))}</h3>
      ${meta ? `<p class="event-meta">${ICON_PIN}${esc(meta)}</p>` : ''}
      <a class="btn btn--outline" href="${pp('pages/event-detail.html')}?id=${encodeURIComponent(e.id)}">${T('b_details')}</a>
    </div></div>`;
  }).join('') : `<div class="empty-state" style="grid-column:1/-1">${ICON_STAR}<p>${T('empty_up')}</p></div>`;
}

// ── Events page (+ tag filter) ──
async function initEventsPage() {
  const el = document.getElementById('eventsGrid');
  if (!el) return;
  await API.init();
  const all = API.events.all();
  let currentTag = new URLSearchParams(location.search).get('tag');
  const bar = document.getElementById('tagBar');
  if (bar) {
    const tags = ['all'].concat([...new Set(all.flatMap(e => e.tags || []))]);
    bar.innerHTML = tags.map(t => `<button class="tag-chip${t === (currentTag || 'all') ? ' active' : ''}" data-tag="${t}">${t === 'all' ? T('tag_all') : esc(t)}</button>`).join('');
    bar.querySelectorAll('button').forEach(b => b.onclick = () => {
      currentTag = b.dataset.tag === 'all' ? null : b.dataset.tag;
      const url = new URL(location.href);
      if (!currentTag) url.searchParams.delete('tag'); else url.searchParams.set('tag', currentTag);
      history.replaceState(null, '', url);
      render();
      bar.querySelectorAll('button').forEach(x => x.classList.toggle('active', x === b));
    });
  }
  function render() {
    const list = currentTag ? all.filter(e => (e.tags || []).includes(currentTag)) : all;
    el.innerHTML = list.length ? list.map(e => {
      const meta = [e.date, evLoc(e)].filter(Boolean).join(' · ');
      return `<div class="event-card">${coverHTML(e)}<div class="event-card-body">
        ${badgeHTML(e.status)}<h3>${esc(evTitle(e))}</h3>
        ${meta ? `<p class="event-meta">${ICON_PIN}${esc(meta)}</p>` : ''}
        ${tagsHTML(e)}
        <a class="btn btn--outline" href="event-detail.html?id=${encodeURIComponent(e.id)}">${T('b_book')}</a>
      </div></div>`;
    }).join('') : '<div class="empty-state" style="grid-column:1/-1">' + ICON_STAR + '<p>' + T('empty_cat') + '</p></div>';
  }
  render();
}

// ── Event detail ──
async function initEventDetail() {
  const el = document.getElementById('eventDetailRoot');
  if (!el) return;
  await API.init();
  const id = new URLSearchParams(location.search).get('id');
  const e = API.events.get(id);
  if (!e) { el.innerHTML = '<div class="empty-state">' + ICON_STAR + '<p>' + T('empty_event') + '</p></div>'; return; }
  document.title = esc(evTitle(e)) + ' | ' + T('logo');

  const galleryHTML = Array.isArray(e.gallery) && e.gallery.length
    ? `<div style="margin-top:22px"><h3 style="font-weight:700;margin-bottom:10px;color:var(--navy)">${T('gallery_label') || 'گالری تصاویر'}</h3>
       <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px">
         ${e.gallery.map(src => `<img src="${pp(esc(src))}" loading="lazy" style="width:100%;aspect-ratio:1;object-fit:cover;border-radius:10px;cursor:pointer" onclick="window.open('${pp(esc(src))}','_blank')">`).join('')}
       </div></div>`
    : '';
  const videoHTML = e.video
    ? `<div style="margin-top:22px"><h3 style="font-weight:700;margin-bottom:10px;color:var(--navy)">${T('video_label') || 'ویدیو'}</h3>
       <video controls style="width:100%;border-radius:14px;background:#000" src="${pp(esc(e.video))}"></video></div>`
    : '';

  // Reservation-migration phase 3: booking happens right here now (same
  // backend, same database the Telegram bot itself uses — see
  // buildBooking() below) instead of only handing off to Telegram/phone.
  // The direct-contact buttons stay as a fallback underneath — an event
  // with no sessions defined yet, or an admin who just prefers handling
  // it personally for one event, both still work exactly as before.
  const directContact = (e.contact_phone || e.contact_telegram)
    ? `<div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:14px">
        ${e.contact_telegram ? `<a class="btn btn--outline" href="https://t.me/${esc(e.contact_telegram)}" target="_blank">${T('book_tg')}</a>` : ''}
        ${e.contact_phone ? `<a class="btn btn--outline" href="tel:${esc(e.contact_phone)}" dir="ltr">${ICON_PIN.replace('stroke-width="1.8"', 'stroke-width="2"')} ${esc(e.contact_phone)}</a>` : ''}
      </div>`
    : '';
  const bookingCta = `<div>
      <h3 style="font-weight:700;margin-bottom:10px;color:var(--navy)">${T('reserve_title')}</h3>
      <div id="bookingWidget"></div>
      ${directContact}
    </div>`;

  el.innerHTML = `
    <h1 style="font-size:clamp(1.5rem,3vw,1.95rem);font-weight:700;margin-bottom:6px;color:var(--navy)">${esc(evTitle(e))}</h1>
    <p style="color:var(--text-muted);margin-bottom:24px;line-height:2">${esc(evCtx(e))}</p>
    <div class="event-detail-grid" style="display:grid;grid-template-columns:340px 1fr;gap:32px;align-items:start;max-width:960px;margin:0 auto">
      <div class="event-detail-poster" style="order:2">${coverHTML(e)}${galleryHTML}${videoHTML}</div>
      <div class="event-detail-info" style="order:1;display:grid;gap:18px">
        <div>
          <h3 style="font-weight:700;margin-bottom:10px;color:var(--navy)">${T('info_label')}</h3>
          <table class="admin-table"><tbody>
            ${evLoc(e) ? `<tr><td style="font-weight:600;color:var(--gold-deep);width:110px">${T('loc_label')}</td><td>${esc(evLoc(e))}</td></tr>` : ''}
            ${e.date ? `<tr><td style="font-weight:600;color:var(--gold-deep)">${T('date_label')}</td><td>${esc(e.date)}</td></tr>` : ''}
          </tbody></table>
        </div>
        ${bookingCta}
      </div>
    </div>
    <div class="feedback-box" id="feedbackBox" style="max-width:640px;margin:24px auto 0"><h4>${T('fb_title')}</h4>
      <div id="feedbackForm"><input id="fbName" placeholder="${T('fb_name_ph')}" maxlength="60"><textarea id="fbText" placeholder="${T('fb_text_ph')}" required maxlength="1000"></textarea><button class="btn btn--gold" onclick="submitFeedback('${esc(e.id)}')" style="font-size:13px">${T('fb_submit')}</button></div>
      <div id="feedbackList" style="margin-top:16px"></div>
    </div>
    <style>@media (max-width: 760px) { .event-detail-grid { grid-template-columns: 1fr !important; } .event-detail-poster { order: 1 !important; max-width: 380px; margin: 0 auto; } .event-detail-info { order: 2 !important; } }</style>`;
  loadFeedbacks(e.id);
  await buildBooking(e);
}

/* ── Step-by-step booking (same backend the Telegram bot itself uses) ── */
const __bk = { eventId: null, dateId: null, sessionId: null, qty: 1 };
async function buildBooking(e) {
  const box = document.getElementById('bookingWidget');
  if (!box) return;
  __bk.eventId = e.id;
  await API.sessions.refresh(e.id);
  const dates = API.dates.forEvent(e.id);
  if (!dates.length) {
    box.insertAdjacentHTML('beforeend', `<p style="font-size:13px;color:var(--text-muted)">${T('bk_sel_date')}</p>`);
    return;
  }
  // UX fix: a date "chip" that looks identical to the plain info-table
  // pill above it (both just a rounded label with a date in it) gave no
  // hint it was clickable — nothing was pre-selected, so nothing ever
  // showed the CSS's own hover/.active affordance until acted on, and a
  // buyer had no reason to act on what read as a static label. Now: with
  // only one date (the common case), skip the picker entirely — it'd be
  // a second, redundant control for a choice that doesn't exist — and go
  // straight to that date's sessions. With more than one date, the first
  // is auto-selected (so its sessions are visible immediately, and the
  // chip itself visibly renders "active" — which is what actually
  // demonstrates "these are clickable" instead of asking the buyer to
  // infer it from a plain rounded label).
  const multipleDates = dates.length > 1;
  box.insertAdjacentHTML('beforeend', `
    <div style="display:grid;gap:18px" id="bkRoot">
      ${multipleDates ? `<div><div class="bk-label">${T('bk_date')}</div><div class="bk-chips" id="bkDates">${dates.map(d => `<button type="button" class="bk-chip" data-date="${esc(d.id)}">${esc(d.jalali_date)}</button>`).join('')}</div></div>` : `<div id="bkDates" style="display:none"></div>`}
      <div id="bkSessionBlock"><div class="bk-label">${T('bk_session')}</div><div class="bk-sessions" id="bkSessions"></div></div>
      <div id="bkQtyBlock" style="display:none"><div class="bk-label">${T('bk_qty')}</div>
        <div class="bk-stepper"><button type="button" id="bkMinus" aria-label="−">−</button><span id="bkQtyVal">1</span><button type="button" id="bkPlus" aria-label="+">+</button></div>
      </div>
      <div id="bkSummary" style="display:none;background:var(--bg-soft);border-radius:12px;padding:14px;font-size:13.5px;line-height:2"></div>
      <div id="bkUser" style="display:none"><div class="bk-label">${T('bk_buyer')}</div>
        <input id="bkName" placeholder="${T('reserve_name')}" required maxlength="120" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:10px;font-family:inherit;margin-bottom:8px">
        <input id="bkPhone" placeholder="${T('reserve_phone')}" required maxlength="20" dir="ltr" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:10px;font-family:inherit;margin-bottom:8px">
        <input id="bkEmail" type="email" placeholder="${T('reserve_email')}" required maxlength="180" dir="ltr" style="width:100%;padding:10px;border:1px solid var(--border);border-radius:10px;font-family:inherit">
      </div>
      <button class="btn btn--gold" id="bkSubmit" type="button" style="display:none">${T('bk_confirm')}</button>
      <p id="bkMsg" style="display:none;color:#2a7a2a;font-size:13.5px;line-height:2"></p>
    </div>`);
  box.querySelectorAll('.bk-chip').forEach(chip => chip.onclick = () => selectDate(chip.dataset.date, chip));
  document.getElementById('bkMinus').onclick = () => stepQty(-1);
  document.getElementById('bkPlus').onclick = () => stepQty(1);
  document.getElementById('bkSubmit').onclick = () => submitBooking();
  selectDate(dates[0].id, box.querySelector('.bk-chip') || null);
}
function selectDate(dateIso, chip) {
  __bk.dateId = dateIso; __bk.sessionId = null; __bk.qty = 1;
  document.querySelectorAll('#bkDates .bk-chip').forEach(c => c.classList.toggle('active', c === chip));
  const sessions = API.sessions.forDate(__bk.eventId, dateIso);
  const event = API.events.get(__bk.eventId);
  const wrap = document.getElementById('bkSessions');
  wrap.innerHTML = sessions.length ? sessions.map(s => {
    const full = API.sessions.isFull(s);
    return `<button type="button" class="bk-session ${full ? 'is-full' : ''}" data-sid="${esc(s.id)}" ${full ? 'disabled' : ''}>
      <span dir="ltr" class="bk-time">${esc(s.time)}</span>
      <span class="bk-cap">${full ? T('bk_full') : T('bk_remaining')(API.sessions.remaining(s))}</span>
      <span class="bk-price">${Number(event.price || 0).toLocaleString(lang() === 'en' ? 'en-US' : 'fa-IR')} ${lang() === 'en' ? 'T' : (event.currency || 'تومان')}</span>
      ${full ? `<small style="display:block;width:100%;margin-top:6px"><button type="button" class="bk-waitlist" data-sid="${esc(s.id)}">${T('bk_waitlist')}</button></small>` : ''}
    </button>`;
  }).join('') : `<p style="font-size:12.5px;color:var(--text-muted)">${T('bk_sel_date')}</p>`;
  document.getElementById('bkSessionBlock').style.display = 'block';
  hideAfterSession();
  wrap.querySelectorAll('.bk-session:not(.is-full)').forEach(b => b.onclick = () => selectSession(b.dataset.sid, b));
  wrap.querySelectorAll('.bk-waitlist').forEach(b => b.onclick = (ev) => { ev.stopPropagation(); joinWaitlist(b.dataset.sid); });
}
function selectSession(sessionId, btn) {
  __bk.sessionId = sessionId; __bk.qty = 1;
  document.querySelectorAll('#bkSessions .bk-session').forEach(b => b.classList.toggle('active', b === btn));
  document.getElementById('bkQtyVal').textContent = '1';
  document.getElementById('bkQtyBlock').style.display = 'block';
  document.getElementById('bkUser').style.display = 'block';
  document.getElementById('bkSubmit').style.display = 'inline-flex';
  renderSummary();
}
function hideAfterSession() {
  document.getElementById('bkQtyBlock').style.display = 'none';
  document.getElementById('bkUser').style.display = 'none';
  document.getElementById('bkSubmit').style.display = 'none';
  document.getElementById('bkSummary').style.display = 'none';
}
function stepQty(delta) {
  const s = API.sessions.get(__bk.eventId, __bk.sessionId); if (!s) return;
  const max = Math.max(1, API.sessions.remaining(s));
  __bk.qty = Math.min(max, Math.max(1, __bk.qty + delta));
  document.getElementById('bkQtyVal').textContent = __bk.qty;
  document.getElementById('bkPlus').disabled = __bk.qty >= max;
  document.getElementById('bkMinus').disabled = __bk.qty <= 1;
  renderSummary();
}
function renderSummary() {
  const s = API.sessions.get(__bk.eventId, __bk.sessionId); if (!s) return;
  const d = API.dates.forEvent(__bk.eventId).find(x => x.id === __bk.dateId);
  const event = API.events.get(__bk.eventId);
  const unitPrice = Number(event.price || 0);
  const total = __bk.qty * unitPrice;
  const currencyLabel = lang() === 'en' ? 'T' : (event.currency || 'تومان');
  const el = document.getElementById('bkSummary');
  el.style.display = 'block';
  el.innerHTML = `${esc(evTitle(event))} · ${esc(d ? d.jalali_date : '')} · <span dir="ltr">${esc(s.time)}</span><br>${T('bk_qty')}: ${__bk.qty} · ${T('bk_each')}: ${unitPrice.toLocaleString(lang() === 'en' ? 'en-US' : 'fa-IR')}<br><strong style="color:var(--gold-deep)">${T('bk_total')}: ${total.toLocaleString(lang() === 'en' ? 'en-US' : 'fa-IR')} ${currencyLabel}</strong>`;
}
async function submitBooking() {
  const name = document.getElementById('bkName').value.trim();
  const phone = document.getElementById('bkPhone').value.trim();
  const email = document.getElementById('bkEmail').value.trim();
  if (!name || !phone || !email) return alert(`${T('reserve_name')} / ${T('reserve_phone')} / ${T('reserve_email')}`);
  const s = API.sessions.get(__bk.eventId, __bk.sessionId);
  if (!s || API.sessions.isFull(s)) return alert(T('bk_full'));

  const submitBtn = document.getElementById('bkSubmit');
  submitBtn.disabled = true;
  let record;
  try {
    // This is the real call — lands in the SAME database the Telegram
    // bot and admin panel read from, not a local-only record. email is
    // what lets this same person log in later (pages/account.html) and
    // see this exact reservation — see reservation_service.
    // start_reservation_web()'s docstring for why it's required.
    record = await API.reservations.create({ session_id: s.id, phone, full_name: name, email, people: __bk.qty });
  } catch (err) {
    submitBtn.disabled = false;
    if (err.status === 409 && err.message === 'sold_out') return alert(T('bk_full'));
    return alert('خطا در ثبت رزرو — لطفاً دوباره تلاش کنید. ' + (err.details || ''));
  }
  if (record && record.waiting) {
    const msg = document.getElementById('bkMsg');
    msg.style.display = 'block';
    msg.innerHTML = T('bk_waitlist_done');
    document.getElementById('bkUser').style.display = 'none';
    submitBtn.style.display = 'none';
    return;
  }
  const msg = document.getElementById('bkMsg');
  msg.style.display = 'block';
  // reservation_code is only assigned once the admin approves payment
  // (same as the Telegram bot flow) — showing a fake code here before
  // that would be inventing data the backend hasn't actually issued yet.
  msg.innerHTML = `${T('bk_done')}<br>${T('bk_tracking_id')}: <strong dir="ltr" style="color:var(--gold-deep)">#${esc(record.id)}</strong>`;
  document.getElementById('bkUser').style.display = 'none';
  submitBtn.style.display = 'none';
  document.getElementById('bkQtyBlock').style.display = 'none';
  await showPayment(record, s);
  selectDate(__bk.dateId, document.querySelector('#bkDates .bk-chip.active'));
}
async function showPayment(record, session) {
  let info = T('pay_fallback');
  try {
    const p = await API.paymentInfo.get();
    if (p && p.card_number) {
      info = `${lang() === 'en' ? 'Card' : 'شماره کارت'}: <strong dir="ltr">${esc(p.card_number)}</strong>${p.card_holder ? ' · ' + esc(p.card_holder) : ''}`;
    }
  } catch { /* fall back to the generic message rather than block the success screen on a payment-info fetch error */ }
  const box = document.getElementById('bookingWidget');
  const prev = document.getElementById('bkPay');
  if (prev) prev.remove();
  const div = document.createElement('div');
  div.id = 'bkPay';
  div.innerHTML = `<div class="feedback-box" style="background:var(--bg-soft)">
    <h4>${T('pay_title')}</h4><p style="font-size:13px;line-height:2;margin-bottom:10px">${info}</p>
    <label style="font-size:12.5px;font-weight:600;display:block;margin-bottom:6px">${T('pay_upload')}</label>
    <input type="file" id="bkReceipt" accept="image/*" style="font-size:12.5px;margin-bottom:10px">
    <button class="btn btn--gold" type="button" style="font-size:12.5px" onclick="uploadReceiptUI(${Number(record.id)})">${T('pay_upload')}</button>
    <p id="bkPayMsg" style="display:none;color:#2a7a2a;font-size:13px;margin-top:10px;line-height:2"></p>
  </div>`;
  box.appendChild(div);
}
function uploadReceiptUI(reservationId) {
  const file = document.getElementById('bkReceipt').files[0];
  if (!file) return alert(T('pay_upload'));
  if (!file.type.startsWith('image/')) return alert(T('bk_sel_date'));
  if (file.size > 1_500_000) return alert(T('pay_upload') + ' ≤1.5MB');
  const reader = new FileReader();
  reader.onload = async () => {
    const msg = document.getElementById('bkPayMsg');
    try {
      // Same submit_receipt() the Telegram bot's photo handler calls —
      // triggers the exact same admin notification either way.
      await API.receipts.submit(reservationId, String(reader.result));
      msg.style.display = 'block'; msg.textContent = T('pay_ok');
      document.getElementById('bkReceipt').disabled = true;
    } catch (err) {
      msg.style.display = 'block';
      msg.style.color = '#c44';
      msg.textContent = 'خطا در ارسال رسید — ' + (err.details || err.message || 'دوباره تلاش کنید.');
    }
  };
  reader.readAsDataURL(file);
}
async function joinWaitlist(sid) {
  const name = prompt(T('reserve_name')) || '';
  const phone = prompt(T('reserve_phone')) || '';
  const email = prompt(T('reserve_email')) || '';
  if (!name || !phone || !email) return;
  let record;
  try {
    // The backend automatically routes to the waiting list when the
    // session is full — same atomic check as a normal booking, no
    // separate "waiting" status invented on the frontend.
    record = await API.reservations.create({ session_id: sid, phone, full_name: name, email, people: 1 });
  } catch (err) {
    return alert('خطا در ثبت درخواست — لطفاً دوباره تلاش کنید.');
  }
  const msg = document.getElementById('bkMsg');
  msg.style.display = 'block';
  msg.textContent = record.waiting
    ? T('bk_waitlist_done')
    : (T('bk_done') + ' #' + record.id);
}

function submitFeedback(eventId) {
  const name = document.getElementById('fbName').value.trim() || '—';
  const text = document.getElementById('fbText').value.trim();
  if (!text) return;
  API.feedback.add(eventId, { author: name, text });
  document.getElementById('fbText').value = '';
  loadFeedbacks(eventId);
}

function loadFeedbacks(eventId) {
  const el = document.getElementById('feedbackList');
  if (!el) return;
  const items = API.feedback.byEvent(eventId);
  el.innerHTML = items.length ? items.map(f => `<div class="feedback-item"><div class="author">${esc(f.author)}</div><div class="text">${esc(f.text)}</div></div>`).join('') : '<p style="font-size:13px;color:var(--text-muted)">' + T('empty_comment') + '</p>';
}

// ── Bio (read-more) ──
function initBio() {
  const btn = document.getElementById('bioMore');
  const box = document.getElementById('bioText');
  if (!btn || !box) return;
  const render = () => { btn.textContent = box.classList.contains('expanded') ? T('bio_less') : T('bio_more'); };
  btn.onclick = () => { box.classList.toggle('expanded'); render(); };
  window.addEventListener('mv-lang', render);
  render();
}

/* ── Gallery (flip cards) ──
   عکسهای جدید خودت را اینجا اضافه کن:
   { img: 'assets/images/mansour/photo.jpg',
     title: { fa: 'عنوان فارسی', en: 'English title' },
     desc:  { fa: 'این عکس کجاست / چیست', en: 'Where / what it is' },
     link:  'pages/about-mansour.html' } */
const GALLERY = [
  { img: 'assets/images/mansour/m1.jpg', title: { fa: 'در نور صحنه', en: 'In the stage light' }, desc: { fa: 'لحظه‌ای از تمرین و اجرا — تهران', en: 'A moment from rehearsal & performance — Tehran' }, link: 'pages/about-mansour.html' },
  { img: 'assets/images/mansour/m2.jpg', title: { fa: 'بین نقش‌ها', en: 'Between roles' }, desc: { fa: 'پشت صحنه و لحظه‌های شخصی', en: 'Behind the scenes & personal moments' }, link: 'pages/about-mansour.html' },
  { img: 'assets/images/mansour/m3.jpg', title: { fa: 'پرتره', en: 'Portrait' }, desc: { fa: 'پرتره‌ای از منصور نصیری', en: 'A portrait of Mansour Nasiri' }, link: 'pages/about-mansour.html' }
];

function initGallery() {
  const wrap = document.getElementById('galleryGrid');
  if (!wrap) return;
  const l = lang();
  wrap.innerHTML = GALLERY.map((g, i) => `
    <div class="g-card" id="gcard${i}" data-reveal style="--d:${i % 5}">
      <div class="g-inner">
        <div class="g-face g-front"><img src="${pp(g.img)}" alt="${esc(g.title[l])}" loading="lazy"></div>
        <div class="g-face g-back">
          <h4>${esc(g.title[l])}</h4>
          <p>${esc(g.desc[l])}</p>
          <a href="${pp(g.link)}">${T('gal_link')}</a>
          <button type="button" class="g-return">${l === 'en' ? 'Flip back' : 'بازگشت به عکس'}</button>
        </div>
      </div>
    </div>`).join('');
  wrap.querySelectorAll('.g-card').forEach(card => {
    card.onclick = (event) => {
      if (event.target.closest('a')) return;
      if (event.target.closest('.g-return')) { card.classList.remove('flipped'); return; }
      card.classList.toggle('flipped');
    };
  });
  // re-reveal
  if (window.__mvReveal) window.__mvReveal();
}

// ── Quote ribbon: one thought, fading every 10s ──
let __quoteIdx = 0;
function initQuotes() {
  const el = document.getElementById('quoteText');
  if (!el) return;
  const show = () => { el.textContent = T('q' + ((__quoteIdx % 6) + 1)); };
  show();
  setInterval(() => {
    el.classList.add('is-hiding');
    setTimeout(() => { __quoteIdx++; show(); el.classList.remove('is-hiding'); }, 800);
  }, 10000);
  window.addEventListener('mv-lang', show);
}

// ── Global chrome: reveal / progress / back-to-top / particles ──
function initGlobal() {
  if (window.__mvGlobalInit) return;
  window.__mvGlobalInit = true;

  const onScroll = () => {
    const y = window.scrollY;
    const h = document.documentElement.scrollHeight - window.innerHeight;
    const bar = document.getElementById('progressBar');
    const header = document.getElementById('siteHeader');
    const topBtn = document.getElementById('backToTop');
    if (bar) bar.style.width = (h > 0 ? (y / h) * 100 : 0) + '%';
    if (header) header.classList.toggle('scrolled', y > 10);
    if (topBtn) topBtn.classList.toggle('visible', y > 420);
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  const topBtn = document.getElementById('backToTop');
  if (topBtn) topBtn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

  // reveal on scroll
  window.__mvReveal = () => {
    const revealEls = document.querySelectorAll('[data-reveal]');
    if (revealEls.length && !reducedMotion() && 'IntersectionObserver' in window) {
      const io = new IntersectionObserver((entries) => {
        entries.forEach(en => {
          if (en.isIntersecting) { en.target.classList.add('revealed'); io.unobserve(en.target); }
        });
      }, { threshold: 0.1, rootMargin: '0px 0px -30px 0px' });
      revealEls.forEach(el => io.observe(el));
    } else {
      revealEls.forEach(el => el.classList.add('revealed'));
    }
  };
  window.__mvReveal();

  // hero gold particles
  const pwrap = document.getElementById('particles');
  if (pwrap && !reducedMotion()) {
    for (let i = 0; i < 14; i++) {
      const p = document.createElement('span');
      p.className = 'particle';
      const size = 3 + Math.random() * 4;
      p.style.cssText = `width:${size}px;height:${size}px;left:${4 + Math.random() * 92}%;animation-duration:${9 + Math.random() * 12}s;animation-delay:${Math.random() * 8}s;opacity:${0.3 + Math.random() * 0.5}`;
      pwrap.appendChild(p);
    }
  }
}

// ── Init dispatch ──
function dispatchPage() {
  const page = document.body.dataset.page;
  if (page === 'home') { initQuotes(); initSlider(); initEventsPreview(); initGallery(); initBio(); }
  if (page === 'events') initEventsPage();
  if (page === 'event-detail') initEventDetail();
}

document.addEventListener('DOMContentLoaded', () => {
  const q = new URLSearchParams(location.search).get('lang');
  if (q === 'en' || q === 'fa') {
    try { localStorage.setItem('mh_lang', q); } catch {}
    loadHeader(); loadFooter(); // rebuild chrome in the target language
  }
  applyLang();
  dispatchPage();
  initGlobal();
});
