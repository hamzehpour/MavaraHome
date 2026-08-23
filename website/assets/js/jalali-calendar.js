/* Mavara Home — Jalali/Gregorian conversion + a minimal dependency-free
   calendar picker, used by the admin panel so dates are chosen by clicking
   a day instead of hand-typing "۱۴۰۵/۰۵/۱۵" (requested: reduce admin date-
   entry errors, and allow either calendar system). */
const MavaraCal = (() => {
  const g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29];

  function isLeapGregorian(y) { return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0; }

  // Correct, well-tested Jalali<->Julian-day-number<->Gregorian conversion
  // (ported from the jalaali-js algorithm — needed because the backend
  // stores sessions.session_date as ISO Gregorian, not Jalali, so a date
  // picked from the Jalali tab still needs to convert before being sent).
  const div = (a, b) => Math.trunc(a / b);
  const mod = (a, b) => a - Math.trunc(a / b) * b;

  function jalCal(jy) {
    const breaks = [-61, 9, 38, 199, 426, 686, 756, 818, 1111, 1181, 1210, 1635, 2060, 2097, 2192, 2262, 2324, 2394, 2456, 3178];
    const gy = jy + 621;
    let leapJ = -14, jp = breaks[0], jm, jump, n;
    for (let i = 1; i < breaks.length; i++) {
      jm = breaks[i]; jump = jm - jp;
      if (jy < jm) break;
      leapJ = leapJ + div(jump, 33) * 8 + div(mod(jump, 33), 4);
      jp = jm;
    }
    n = jy - jp;
    leapJ = leapJ + div(n, 33) * 8 + div(mod(n, 33) + 3, 4);
    if (mod(jump, 33) === 4 && jump - n === 4) leapJ += 1;
    const leapG = div(gy, 4) - div((div(gy, 100) + 1) * 3, 4) - 150;
    const march = 20 + leapJ - leapG;
    return { gy, march };
  }
  function g2d(gy, gm, gd) {
    let d = div((gy + div(gm - 8, 6) + 100100) * 1461, 4) + div(153 * mod(gm + 9, 12) + 2, 5) + gd - 34840408;
    d = d - div(div(gy + 100100 + div(gm - 8, 6), 100) * 3, 4) + 752;
    return d;
  }
  function j2d(jy, jm, jd) {
    const r = jalCal(jy);
    return g2d(r.gy, 3, r.march) + (jm - 1) * 31 - div(jm, 7) * (jm - 7) + jd - 1;
  }
  function d2g(jdn) {
    let j = 4 * jdn + 139361631;
    j = j + div(div(4 * jdn + 183187720, 146097) * 3, 4) * 4 - 3908;
    const i = div(mod(j, 1461), 4) * 5 + 308;
    const gd = div(mod(i, 153), 5) + 1;
    const gm = mod(div(i, 153), 12) + 1;
    const gy = div(j, 1461) - 100100 + div(8 - gm, 6);
    return { gy, gm, gd };
  }
  /** Jalali (jy, jm, jd) -> ISO Gregorian "YYYY-MM-DD" string — the exact
      format the backend's sessions.session_date column stores. */
  function toIsoGregorian(jy, jm, jd) {
    const { gy, gm, gd } = d2g(j2d(jy, jm, jd));
    return `${gy}-${String(gm).padStart(2, '0')}-${String(gd).padStart(2, '0')}`;
  }

  function gregorianToJalali(gy, gm, gd) {
    const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
    let jy = gy <= 1600 ? 0 : 979;
    const gy2 = gy <= 1600 ? gy - 621 : gy - 1600;
    const gy3 = gm > 2 ? gy2 + 1 : gy2;
    let days = 365 * gy2 + Math.floor((gy3 + 3) / 4) - Math.floor((gy3 + 99) / 100) +
      Math.floor((gy3 + 399) / 400) - 80 + gd + g_d_m[gm - 1];
    jy += 33 * Math.floor(days / 12053); days %= 12053;
    jy += 4 * Math.floor(days / 1461); days %= 1461;
    if (days > 365) { jy += Math.floor((days - 1) / 365); days = (days - 1) % 365; }
    const jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
    const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
    return { jy, jm, jd };
  }

  const faDigits = s => String(s).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
  const jMonthNames = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
  const gMonthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];

  function formatJalali(jy, jm, jd) { return faDigits(`${jy}/${String(jm).padStart(2,'0')}/${String(jd).padStart(2,'0')}`); }

  /** Renders a small popup calendar into `container`, calling onPick(formattedJalaliString) when a day is clicked. */
  function attachPicker(inputEl, buttonEl) {
    let mode = 'jalali'; // 'jalali' | 'gregorian'
    const today = new Date();
    let view = gregorianToJalali(today.getFullYear(), today.getMonth() + 1, today.getDate());
    let viewG = { gy: today.getFullYear(), gm: today.getMonth() + 1 };

    const pop = document.createElement('div');
    pop.style.cssText = 'position:absolute;z-index:50;background:#fff;border:1px solid var(--border,#ddd);border-radius:12px;padding:12px;box-shadow:0 8px 24px rgba(0,0,0,.15);display:none;min-width:260px';
    document.body.appendChild(pop);

    function render() {
      const tabs = `<div style="display:flex;gap:6px;margin-bottom:10px">
        <button type="button" data-tab="jalali" style="flex:1;padding:6px;border-radius:8px;border:1px solid #ddd;background:${mode==='jalali'?'var(--gold,#c9a15a)':'#fff'};color:${mode==='jalali'?'#fff':'#333'}">شمسی</button>
        <button type="button" data-tab="gregorian" style="flex:1;padding:6px;border-radius:8px;border:1px solid #ddd;background:${mode==='gregorian'?'var(--gold,#c9a15a)':'#fff'};color:${mode==='gregorian'?'#fff':'#333'}">میلادی</button>
      </div>`;
      let grid;
      if (mode === 'jalali') {
        const dim = j_days_in_month[view.jm - 1] + (view.jm === 12 ? 0 : 0);
        const monthLabel = `${jMonthNames[view.jm - 1]} ${faDigits(view.jy)}`;
        let cells = '';
        for (let d = 1; d <= dim; d++) cells += `<button type="button" data-jd="${d}" style="padding:6px;border:none;background:#f5f0e6;border-radius:6px;cursor:pointer">${faDigits(d)}</button>`;
        grid = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <button type="button" data-nav="-1">‹</button><strong>${monthLabel}</strong><button type="button" data-nav="1">›</button>
        </div><div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px;font-size:12px">${cells}</div>`;
      } else {
        const dim = new Date(viewG.gy, viewG.gm, 0).getDate();
        const monthLabel = `${gMonthNames[viewG.gm - 1]} ${viewG.gy}`;
        let cells = '';
        for (let d = 1; d <= dim; d++) cells += `<button type="button" data-gd="${d}" style="padding:6px;border:none;background:#eef2f6;border-radius:6px;cursor:pointer">${d}</button>`;
        grid = `<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
          <button type="button" data-nav="-1">‹</button><strong>${monthLabel}</strong><button type="button" data-nav="1">›</button>
        </div><div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px;font-size:12px">${cells}</div>`;
      }
      pop.innerHTML = tabs + grid;
      pop.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => { mode = b.dataset.tab; render(); });
      pop.querySelectorAll('[data-nav]').forEach(b => b.onclick = () => {
        const dir = Number(b.dataset.nav);
        if (mode === 'jalali') { view.jm += dir; if (view.jm > 12) { view.jm = 1; view.jy++; } if (view.jm < 1) { view.jm = 12; view.jy--; } }
        else { viewG.gm += dir; if (viewG.gm > 12) { viewG.gm = 1; viewG.gy++; } if (viewG.gm < 1) { viewG.gm = 12; viewG.gy--; } }
        render();
      });
      pop.querySelectorAll('[data-jd]').forEach(b => b.onclick = () => {
        const jd = Number(b.dataset.jd);
        inputEl.value = formatJalali(view.jy, view.jm, jd);
        inputEl.dataset.iso = toIsoGregorian(view.jy, view.jm, jd);
        inputEl.dispatchEvent(new Event('change'));
        pop.style.display = 'none';
      });
      pop.querySelectorAll('[data-gd]').forEach(b => b.onclick = () => {
        const gd = Number(b.dataset.gd);
        const { jy, jm, jd } = gregorianToJalali(viewG.gy, viewG.gm, gd);
        inputEl.value = formatJalali(jy, jm, jd); // display is always Jalali, regardless of which calendar tab was used to pick
        inputEl.dataset.iso = `${viewG.gy}-${String(viewG.gm).padStart(2, '0')}-${String(gd).padStart(2, '0')}`;
        inputEl.dispatchEvent(new Event('change'));
        pop.style.display = 'none';
      });
    }

    buttonEl.addEventListener('click', (e) => {
      e.preventDefault();
      const rect = buttonEl.getBoundingClientRect();
      pop.style.top = (window.scrollY + rect.bottom + 4) + 'px';
      pop.style.left = (window.scrollX + rect.left) + 'px';
      pop.style.display = pop.style.display === 'none' ? 'block' : 'none';
      render();
    });
    document.addEventListener('click', (e) => { if (!pop.contains(e.target) && e.target !== buttonEl) pop.style.display = 'none'; });
  }

  return { gregorianToJalali, toIsoGregorian, formatJalali, attachPicker };
})();
