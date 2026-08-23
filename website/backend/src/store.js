// Mavara Home · storage adapter (JSON file for dev/demo; replace with Postgres in production)
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DB_FILE = process.env.MAVARA_DB_FILE || join(__dirname, 'data', 'db.json');
mkdirSync(dirname(DB_FILE), { recursive: true });

let cache = null;
function load() {
  if (cache) return cache;
  if (!existsSync(DB_FILE)) { cache = seed(); persist(); return cache; }
  try { cache = JSON.parse(readFileSync(DB_FILE, 'utf8')); } catch { cache = seed(); persist(); }
  return cache;
}
function persist() { writeFileSync(DB_FILE, JSON.stringify(cache, null, 2)); }
function seed() {
  return {
    events: [
      { id: 'hubab-theater', title: 'حُباب', title_en: 'Hubab', status: 'ongoing', price: 150000, capacity: 20, images: ['assets/images/hubab/1.jpg'] },
      { id: 'khodshenasi-koodaki', title: 'خودشناسی (با بازیابی خاطرات کودکی)', title_en: 'Self-knowledge', status: 'upcoming', price: 0, capacity: 20, date: 'پاییز ۱۴۰۵' },
      { id: 'shab-goftogoo-sher', title: 'شب گفتگو و شعر: آرامش در دل آشوب', title_en: 'Night of Dialogue & Poetry', status: 'upcoming', price: 0, capacity: 20, date: 'به‌زودی' }
    ],
    sessions: [
      { id: 's1', event_id: 'hubab-theater', date: '1405-05-15', time: '15:30', capacity: 20, status: 'ACTIVE' },
      { id: 's2', event_id: 'hubab-theater', date: '1405-05-15', time: '18:30', capacity: 20, status: 'ACTIVE' },
      { id: 's3', event_id: 'hubab-theater', date: '1405-05-16', time: '20:00', capacity: 15, status: 'ACTIVE' }
    ],
    // Full resume/portfolio — restored from the 31-item dataset that used
    // to live only in the frontend (assets/js/legacy-data.js) and was never
    // fully admin-editable. Every one of these is now a real backend row,
    // so the admin portfolio page can add/edit/remove any of them.
    portfolio: [
        { id: 1, title_fa: "زن و بچه", title_en: "Woman and Child", year: "2025", category: "CINEMA", director: "سعید روستایی", role: "وکیل", poster: "assets/images/portfolio/zanobacheh.jpg", status: "active" },
        { id: 2, title_fa: "ساعت ۶ صبح", title_en: "6 AM", year: "2024", category: "CINEMA", director: "مهران مدیری", role: "پیمان", poster: null, status: "active" },
        { id: 3, title_fa: "متری شیش و نیم", title_en: "6.5 Per Meter", year: "2019", category: "CINEMA", director: "سعید روستایی", role: "مامور زندان", poster: "assets/images/portfolio/metrishishonim.jpg", status: "active" },
        { id: 4, title_fa: "منصور", title_en: "Mansour", year: "2020", category: "CINEMA", director: "سیاوش سرمدی", role: "محافظ تیمسار ستاری", poster: null, status: "active" },
        { id: 5, title_fa: "بی‌سر", title_en: "Be-Sar", year: "2019", category: "CINEMA", director: "کاوه سجادی حسینی", role: "پزشک داروخانه", poster: null, status: "active" },
        { id: 6, title_fa: "مسیح پسر مریم", title_en: "Masih Pesar-e Maryam", year: "2021", category: "CINEMA", director: "علی جعفرآبادی", role: "جمال", poster: null, status: "active" },
        { id: 10, title_fa: "استخوان‌سوز", title_en: "Bone Burner", year: "2024", category: "SERIES", director: "مجید اسماعیلی", role: "سعید", poster: null, status: "active" },
        { id: 11, title_fa: "در انتهای شب", title_en: "At the End of the Night", year: "2024", category: "SERIES", director: "آیدا پناهنده", role: "دکتر رحیمی", poster: "assets/images/portfolio/darentehayeshab.jpg", status: "active" },
        { id: 12, title_fa: "جادوی سفید", title_en: "White Magic", year: "2024", category: "SERIES", director: "آیدا پناهنده", role: "بازیگر", poster: null, status: "active" },
        { id: 13, title_fa: "زیرخاکی", title_en: "Zirkhaki", year: "2023", category: "SERIES", director: "جلیل سامان", role: "امجدی (فصل ۱ و ۴)", poster: null, status: "active" },
        { id: 14, title_fa: "قهوه ترک", title_en: "Turkish Coffee", year: "2023", category: "SERIES", director: "علیرضا امینی", role: "دکتر نریمانی", poster: null, status: "active" },
        { id: 15, title_fa: "سیاوش", title_en: "Siavash", year: "2021", category: "SERIES", director: "سروش محمدزاده", role: "اسد بندری", poster: null, status: "active" },
        { id: 20, title_fa: "آبی می‌شود", title_en: "It Turns Blue", year: "2022", category: "SHORT", director: "شادی کرم‌رودی", role: "مرتضی", poster: "assets/images/portfolio/abimishavad.jpg", status: "active" },
        { id: 21, title_fa: "تطبیق", title_en: "Adjustment", year: "2021", category: "SHORT", director: "مهرداد حسنی", role: "معلم مدرسه", poster: "assets/images/portfolio/tatbigh.jpg", status: "active" },
        { id: 22, title_fa: "مگرالن", title_en: "Magralen", year: "2019", category: "SHORT", director: "مریم زارعی", role: "پدر", poster: "assets/images/portfolio/magralen.jpg", status: "active" },
        { id: 23, title_fa: "ماتروشکا", title_en: "Matryoshka", year: "2016", category: "SHORT", director: "یلدا زادون", role: "بازیگر", poster: "assets/images/portfolio/matryoshka.jpg", status: "active" },
        { id: 24, title_fa: "ماقبل تاریخ", title_en: "Prehistoric", year: "2025", category: "SHORT", director: "ارمین اعتمادی", role: "بازیگر", poster: "assets/images/portfolio/maghabletrikh.jpg", status: "active" },
        { id: 25, title_fa: "تقلا", title_en: "Struggle", year: "2025", category: "SHORT", director: "افسانه بابایی", role: "بازیگر", poster: null, status: "active" },
        { id: 26, title_fa: "مثل یک راز", title_en: "Like a Secret", year: "2018", category: "SHORT", director: "سعید زمانیان", role: "دایی", poster: null, status: "active" },
        { id: 27, title_fa: "استخوان", title_en: "Bone", year: "2018", category: "SHORT", director: "مریم زارعی", role: "بازیگر", poster: null, status: "active" },
        { id: 28, title_fa: "به سبک زمین", title_en: "Style of Earth", year: "2017", category: "SHORT", director: "پیام رضایی", role: "بازیگر", poster: null, status: "active" },
        { id: 40, title_fa: "حُباب", title_en: "Bubble", year: "2024", category: "THEATER", director: "منصور نصیری", role: "نویسنده، بازیگر و کارگردان", poster: "assets/images/portfolio/Hobab Poster.jpg", status: "active" },
        { id: 41, title_fa: "لانچر ۵", title_en: "Launcher 5", year: "2019", category: "THEATER", director: "پویا سعیدی و مسعود صرامی", role: "بازیگر", poster: "assets/images/portfolio/launcher5.jpg", status: "active" },
        { id: 42, title_fa: "مرگ و پنگوئن", title_en: "Death and the Penguin", year: "2018", category: "THEATER", director: "پیام دهکردی", role: "بازیگر / دستیار کارگردان", poster: null, status: "active" },
        { id: 43, title_fa: "آرش", title_en: "Arash", year: "2019", category: "THEATER", director: "گلچهر دامغانی", role: "بازیگر", poster: null, status: "active" },
        { id: 44, title_fa: "دشمن مردم", title_en: "An Enemy of the People", year: "2017", category: "THEATER", director: "سینا راستگو", role: "دکتر استوکمان", poster: "assets/images/portfolio/doshmanemardom.jpg", status: "active" },
        { id: 45, title_fa: "مرگ و دوشیزه", title_en: "Death and the Maiden", year: "2017", category: "THEATER", director: "سینا راستگو", role: "بازیگر", poster: null, status: "active" },
        { id: 46, title_fa: "گلن‌گری گلن‌راس", title_en: "Glengarry Glen Ross", year: "2014", category: "THEATER", director: "گروهی", role: "شلی لوین", poster: null, status: "active" },
        { id: 47, title_fa: "درخت سیب گناهکار نیست", title_en: "Apple Tree is not Guilty", year: "2016", category: "THEATER", director: "روناک قاسمی", role: "بازیگر", poster: null, status: "active" },
        { id: 48, title_fa: "تشریفات", title_en: "Ceremonies", year: "2016", category: "THEATER", director: "رامین اکبری", role: "بازیگر", poster: null, status: "active" },
        { id: 49, title_fa: "کوچ جهان", title_en: "Kooch-e Jahan", year: "2016", category: "THEATER", director: "منصور نصیری", role: "کارگردان / بازیگر", poster: null, status: "active" }
    ],
    reservations: [],
    users: [],
    audit: [],
    payments: [],
    reservation_events: []
  };
}

export const store = {
  load,
  persist,
  get(collection) { return load()[collection] || []; },
  set(collection, rows) { load()[collection] = rows; persist(); },
  uid() { return 'mv_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 8); }
};
