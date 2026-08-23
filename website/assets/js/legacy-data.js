/**
 * Legacy portfolio data — imported once into DB on first load
 * Updated with resume image data (festivals, fuller credits)
 */

const resumeTranslations = {
    directors: {
        "سعید روستایی": "Saeed Roustayi", "مهران مدیری": "Mehran Modiri", "سیاوش سرمدی": "Siavash Sarmadi", "کاوه سجادی حسینی": "Kaveh Sajjadi-Hosseini", "علی جعفرآبادی": "Ali Jafarabadi",
        "مجید اسماعیلی": "Majid Esmaeili", "آیدا پناهنده": "Aida Panahandeh", "جلیل سامان": "Jalil Saman", "علیرضا امینی": "Alireza Amini", "سروش محمدزاده": "Soroush Mohammadzadeh",
        "شادی کرم‌رودی": "Shadi Karamroudi", "مهرداد حسنی": "Mehrdad Hasani", "مریم زارعی": "Maryam Zarei", "یلدا زادون": "Yalda Zadoun", "ارمین اعتمادی": "Armin Etemadi", "افسانه بابایی": "Afsaneh Babaei", "سعید زمانیان": "Saeed Zamanian", "پیام رضایی": "Payam Rezaei",
        "منصور نصیری": "Mansour Nasiri", "پویا سعیدی و مسعود صرامی": "Pouya Saeedi & Masoud Sarrami", "پیام دهکردی": "Payam Dehkordi", "گلچهر دامغانی": "Golchehr Damghani", "سینا راستگو": "Sina Rastgoo", "گروهی": "Ensemble", "روناک قاسمی": "Ronak Ghasemi", "رامین اکبری": "Ramin Akbari"
    },
    roles: {
        "وکیل": "Lawyer", "پیمان": "Peyman", "مامور زندان": "Prison Officer", "محافظ تیمسار ستاری": "General Sattari's Guard", "پزشک داروخانه": "Pharmacy Doctor", "جمال": "Jamal", "سعید": "Saeed", "دکتر رحیمی": "Dr. Rahimi", "بازیگر": "Actor", "امجدی (فصل ۱ و ۴)": "Amjadi (Seasons 1 & 4)", "دکتر نریمانی": "Dr. Narimani", "اسد بندری": "Asad Bandari", "مرتضی": "Morteza", "معلم مدرسه": "School Teacher", "پدر": "Father", "دایی": "Uncle", "شلی لوین": "Shelly Levene", "دکتر استوکمان": "Dr. Stockmann", "بازیگر / دستیار کارگردان": "Actor / Assistant Director", "نویسنده، بازیگر و کارگردان": "Writer, Actor & Director", "کارگردان / بازیگر": "Director / Actor"
    },
    festivals: {
        "جایزه بزرگ بوسان ۲۰۲۳ و SXSW": "Busan Grand Prize 2023 & SXSW", "جایزه بزرگ جشنواره بوسان ۲۰۲۲": "Busan International Film Festival Grand Prize 2022", "جشنواره برلین ۲۰۱۹": "Berlin Film Festival 2019", "جایزه بزرگ جشنواره فرایبورگ ۲۰۲۶": "Fribourg Festival Grand Prize 2026", "Cannes 2025": "Cannes 2025"
    }
};

const projectsData = [
    // CINEMA
    { id: 1, titleFA: "زن و بچه", titleEN: "Woman and Child", year: "2025", category: "CINEMA", director: "سعید روستایی", role: "وکیل", poster: "../assets/images/portfolio/zanobacheh.jpg", gallery: ["../assets/images/portfolio/zanobacheh.jpg"], descFA: "حضور در بخش مسابقه اصلی جشنواره کن ۲۰۲۵.", descEN: "Official Selection - Cannes 2025.", festival: "Cannes 2025", status: "NOW_SHOWING" },
    { id: 2, titleFA: "ساعت ۶ صبح", titleEN: "6 AM", year: "2024", category: "CINEMA", director: "مهران مدیری", role: "پیمان", poster: null },
    { id: 3, titleFA: "متری شیش و نیم", titleEN: "6.5 Per Meter", year: "2019", category: "CINEMA", director: "سعید روستایی", role: "مامور زندان", poster: "../assets/images/portfolio/metrishishonim.jpg", gallery: ["../assets/images/portfolio/metrishishonim.jpg"] },
    { id: 4, titleFA: "منصور", titleEN: "Mansour", year: "2020", category: "CINEMA", director: "سیاوش سرمدی", role: "محافظ تیمسار ستاری", poster: null },
    { id: 5, titleFA: "بی‌سر", titleEN: "Be-Sar", year: "2019", category: "CINEMA", director: "کاوه سجادی حسینی", role: "پزشک داروخانه", poster: null },
    { id: 6, titleFA: "مسیح پسر مریم", titleEN: "Masih Pesar-e Maryam", year: "2021", category: "CINEMA", director: "علی جعفرآبادی", role: "جمال", poster: null },

    // SERIES
    { id: 10, titleFA: "استخوان‌سوز", titleEN: "Bone Burner", year: "2024", category: "SERIES", director: "مجید اسماعیلی", role: "سعید", poster: null, descFA: "پست پروداکشن" },
    { id: 11, titleFA: "در انتهای شب", titleEN: "At the End of the Night", year: "2024", category: "SERIES", director: "آیدا پناهنده", role: "دکتر رحیمی", poster: "../assets/images/portfolio/darentehayeshab.jpg" },
    { id: 12, titleFA: "جادوی سفید", titleEN: "White Magic", year: "2024", category: "SERIES", director: "آیدا پناهنده", role: "بازیگر", poster: null },
    { id: 13, titleFA: "زیرخاکی", titleEN: "Zirkhaki", year: "2023", category: "SERIES", director: "جلیل سامان", role: "امجدی (فصل ۱ و ۴)", poster: null },
    { id: 14, titleFA: "قهوه ترک", titleEN: "Turkish Coffee", year: "2023", category: "SERIES", director: "علیرضا امینی", role: "دکتر نریمانی", poster: null },
    { id: 15, titleFA: "سیاوش", titleEN: "Siavash", year: "2021", category: "SERIES", director: "سروش محمدزاده", role: "اسد بندری", poster: null },

    // SHORT FILMS
    { id: 20, titleFA: "آبی می‌شود", titleEN: "It Turns Blue", year: "2022", category: "SHORT", director: "شادی کرم‌رودی", role: "مرتضی", poster: "../assets/images/portfolio/abimishavad.jpg", gallery: ["../assets/images/portfolio/abimishavad.jpg"], festival: "جایزه بزرگ بوسان ۲۰۲۳ و SXSW" },
    { id: 21, titleFA: "تطبیق", titleEN: "Adjustment", year: "2021", category: "SHORT", director: "مهرداد حسنی", role: "معلم مدرسه", poster: "../assets/images/portfolio/tatbigh.jpg", festival: "جایزه بزرگ جشنواره بوسان ۲۰۲۲" },
    { id: 22, titleFA: "مگرالن", titleEN: "Magralen", year: "2019", category: "SHORT", director: "مریم زارعی", role: "پدر", poster: "../assets/images/portfolio/magralen.jpg", festival: "جشنواره برلین ۲۰۱۹" },
    { id: 23, titleFA: "ماتروشکا", titleEN: "Matryoshka", year: "2016", category: "SHORT", director: "یلدا زادون", role: "بازیگر", poster: "../assets/images/portfolio/matryoshka.jpg" },
    { id: 24, titleFA: "ماقبل تاریخ", titleEN: "Prehistoric", year: "2025", category: "SHORT", director: "ارمین اعتمادی", role: "بازیگر", poster: "../assets/images/portfolio/maghabletrikh.jpg", festival: "جایزه بزرگ جشنواره فرایبورگ ۲۰۲۶" },
    { id: 25, titleFA: "تقلا", titleEN: "Struggle", year: "2025", category: "SHORT", director: "افسانه بابایی", role: "بازیگر", poster: null },
    { id: 26, titleFA: "مثل یک راز", titleEN: "Like a Secret", year: "2018", category: "SHORT", director: "سعید زمانیان", role: "دایی", poster: null },
    { id: 27, titleFA: "استخوان", titleEN: "Bone", year: "2018", category: "SHORT", director: "مریم زارعی", role: "بازیگر", poster: null },
    { id: 28, titleFA: "به سبک زمین", titleEN: "Style of Earth", year: "2017", category: "SHORT", director: "پیام رضایی", role: "بازیگر", poster: null },

    // THEATER
    { id: 40, titleFA: "حُباب", titleEN: "Bubble", year: "2024", category: "THEATER", director: "منصور نصیری", role: "نویسنده، بازیگر و کارگردان", poster: "../assets/images/portfolio/Hobab Poster.jpg", status: "NOW_SHOWING" },
    { id: 41, titleFA: "لانچر ۵", titleEN: "Launcher 5", year: "2019", category: "THEATER", director: "پویا سعیدی و مسعود صرامی", role: "بازیگر", poster: "../assets/images/portfolio/launcher5.jpg" },
    { id: 42, titleFA: "مرگ و پنگوئن", titleEN: "Death and the Penguin", year: "2018", category: "THEATER", director: "پیام دهکردی", role: "بازیگر / دستیار کارگردان", poster: null },
    { id: 43, titleFA: "آرش", titleEN: "Arash", year: "2019", category: "THEATER", director: "گلچهر دامغانی", role: "بازیگر", poster: null },
    { id: 44, titleFA: "دشمن مردم", titleEN: "An Enemy of the People", year: "2017", category: "THEATER", director: "سینا راستگو", role: "دکتر استوکمان", poster: "../assets/images/portfolio/doshmanemardom.jpg" },
    { id: 45, titleFA: "مرگ و دوشیزه", titleEN: "Death and the Maiden", year: "2017", category: "THEATER", director: "سینا راستگو", role: "بازیگر", poster: null },
    { id: 46, titleFA: "گلن‌گری گلن‌راس", titleEN: "Glengarry Glen Ross", year: "2014", category: "THEATER", director: "گروهی", role: "شلی لوین", poster: null },
    { id: 47, titleFA: "درخت سیب گناهکار نیست", titleEN: "Apple Tree is not Guilty", year: "2016", category: "THEATER", director: "روناک قاسمی", role: "بازیگر", poster: null },
    { id: 48, titleFA: "تشریفات", titleEN: "Ceremonies", year: "2016", category: "THEATER", director: "رامین اکبری", role: "بازیگر", poster: null },
    { id: 49, titleFA: "کوچ جهان", titleEN: "Kooch-e Jahan", year: "2016", category: "THEATER", director: "منصور نصیری", role: "کارگردان / بازیگر", poster: null },
];

const galleryData = [];
