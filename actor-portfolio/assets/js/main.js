document.addEventListener('DOMContentLoaded', () => {
  initNavToggle();
  initHomeEventsPreview();
  initEventsPage();
  initEventDetailPage();
});

function initNavToggle() {
  const toggle = document.getElementById('navToggle');
  const nav = document.getElementById('siteNav');
  if (!toggle || !nav) return;

  toggle.addEventListener('click', () => {
    const isOpen = nav.classList.toggle('is-open');
    toggle.setAttribute('aria-expanded', String(isOpen));
  });

  nav.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      nav.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
    });
  });
}

const STATUS_LABELS = {
  ongoing: 'در حال اجرا',
  upcoming: 'به‌زودی',
  archived: 'آرشیو'
};

const GROUP_LABELS = {
  cast: {
    actor: 'بازیگر',
    stage_design: 'طراحی صحنه',
    planner: 'برنامه‌ریز',
    special_thanks: 'تشکر ویژه',
    director: 'کارگردان'
  }
};

/* شش مسیر هنر — همون آیکون‌های صفحه اصلی، برای تگ روی کارت رویداد و فیلتر صفحه رویدادها */
const PATH_TAGS = {
  theater: {
    label: 'تئاتر',
    icon: '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.6"><ellipse cx="18" cy="22" rx="12" ry="10"/><circle cx="13" cy="20" r="1.4" fill="currentColor" stroke="none"/><circle cx="23" cy="20" r="1.4" fill="currentColor" stroke="none"/><path d="M12 27c2 2 8 2 10 0"/><ellipse cx="30" cy="26" rx="12" ry="10"/><circle cx="25" cy="24" r="1.4" fill="currentColor" stroke="none"/><circle cx="35" cy="24" r="1.4" fill="currentColor" stroke="none"/><path d="M25 32c2-2 8-2 10 0"/></svg>'
  },
  podcast: {
    label: 'پادکست',
    icon: '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="18" y="6" width="12" height="20" rx="6"/><path d="M12 22c0 7 5.4 12 12 12s12-5 12-12"/><line x1="24" y1="34" x2="24" y2="42"/><line x1="17" y1="42" x2="31" y2="42"/></svg>'
  },
  'self-knowledge': {
    label: 'خودشناسی',
    icon: '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="24" cy="12" r="5"/><path d="M24 19c-4 4-6 6-6 11 0 3 2 5 2 5h16s2-2 2-5c0-5-2-7-6-11"/><circle cx="24" cy="27" r="2" fill="currentColor" stroke="none"/><path d="M14 40c4-3 6-3 10-3s6 0 10 3"/></svg>'
  },
  poetry: {
    label: 'شعر',
    icon: '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M36 8C22 8 12 18 12 32c0 2 0 4 1 6"/><path d="M36 8c0 12-4 20-12 26-4 3-8 4-11 4"/><path d="M18 30c4 0 8-2 10-6"/><circle cx="13" cy="39" r="1.6" fill="currentColor" stroke="none"/></svg>'
  },
  dialogue: {
    label: 'گفتگو',
    icon: '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M6 12h24v16H16l-6 6v-6H6z"/><path d="M20 22h22v14l-5 5v-5H26l-6-6"/></svg>'
  },
  companionship: {
    label: 'همراهی',
    icon: '<svg viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="16" cy="14" r="5"/><circle cx="32" cy="14" r="5"/><path d="M6 38c0-7 4-12 10-12s10 5 10 12"/><path d="M22 38c0-7 4-12 10-12s10 5 10 12"/></svg>'
  }
};

function dataPath(file) {
  return location.pathname.includes('/pages/') ? `../data/${file}` : `data/${file}`;
}

function pagePath(file) {
  return location.pathname.includes('/pages/') ? file : `pages/${file}`;
}

function assetPath(path) {
  return location.pathname.includes('/pages/') ? `../${path}` : path;
}

function fetchEvents() {
  return fetch(dataPath('events.json')).then((res) => {
    if (!res.ok) throw new Error('events.json not found');
    return res.json();
  });
}

/* ============ پیش‌نمایش رویدادها در صفحه اصلی ============ */
function initHomeEventsPreview() {
  const list = document.getElementById('eventsPreviewList');
  if (!list) return;

  fetchEvents()
    .then((events) => {
      const featured = events
        .filter((event) => event.status === 'ongoing' || event.status === 'upcoming')
        .sort((a, b) => (a.status === 'ongoing' ? -1 : 1))
        .slice(0, 3);

      if (featured.length === 0) {
        list.innerHTML = '<p class="events-preview__empty">در حال حاضر رویداد جاری یا پیش‌رویی ثبت نشده است.</p>';
        return;
      }

      list.innerHTML = '';
      featured.forEach((event) => list.appendChild(buildEventCard(event)));
    })
    .catch(() => {
      list.innerHTML = '<p class="events-preview__empty">در حال حاضر امکان نمایش رویدادها نیست.</p>';
    });
}

function buildEventCard(event) {
  const card = document.createElement('article');
  card.className = 'event-card';

  card.appendChild(buildStatusBadge(event.status));

  const title = document.createElement('h3');
  title.className = 'event-card__title';
  title.textContent = event.title;
  card.appendChild(title);

  const tags = buildTagChips(event.tags);
  if (tags) card.appendChild(tags);

  if (event.location) {
    card.appendChild(buildMeta(event.location));
  }

  if (event.schedule && Array.isArray(event.schedule.days)) {
    card.appendChild(buildMeta(event.schedule.days.join('، ')));
  }

  const cta = buildBookingCta(event);
  if (cta) card.appendChild(cta);

  return card;
}

/* ============ صفحه رویدادها (تب وضعیت + فیلتر تگ + کارت کامل) ============ */
function initEventsPage() {
  const tabsEl = document.getElementById('eventsTabs');
  const tagsEl = document.getElementById('eventsTags');
  const grid = document.getElementById('eventsGrid');
  const filterBar = document.getElementById('activeFilterBar');
  const filterLabel = document.getElementById('activeFilterLabel');
  const clearBtn = document.getElementById('clearFilterBtn');
  if (!tabsEl || !grid) return;

  const requestedTag = new URLSearchParams(location.search).get('tag');
  const state = {
    tag: PATH_TAGS[requestedTag] ? requestedTag : null,
    status: 'ongoing'
  };

  fetchEvents()
    .then((events) => {
      renderTagChips(tagsEl, state.tag);
      render(events);

      tabsEl.querySelectorAll('.events-tabs__btn').forEach((btn) => {
        btn.addEventListener('click', () => {
          state.tag = null;
          state.status = btn.dataset.status;
          render(events);
        });
      });

      tagsEl.querySelectorAll('.events-tags__btn').forEach((btn) => {
        btn.addEventListener('click', () => {
          state.tag = state.tag === btn.dataset.tag ? null : btn.dataset.tag;
          if (!state.tag) state.status = 'ongoing';
          render(events);
        });
      });

      clearBtn.addEventListener('click', () => {
        state.tag = null;
        state.status = 'ongoing';
        render(events);
      });

      function render(allEvents) {
        tabsEl.querySelectorAll('.events-tabs__btn').forEach((b) => {
          b.setAttribute('aria-selected', String(!state.tag && b.dataset.status === state.status));
        });
        tagsEl.querySelectorAll('.events-tags__btn').forEach((b) => {
          b.setAttribute('aria-pressed', String(b.dataset.tag === state.tag));
        });

        if (state.tag) {
          filterBar.hidden = false;
          filterLabel.textContent = PATH_TAGS[state.tag].label;
        } else {
          filterBar.hidden = true;
        }

        const filtered = state.tag
          ? allEvents.filter((event) => Array.isArray(event.tags) && event.tags.includes(state.tag))
          : allEvents.filter((event) => event.status === state.status);

        if (filtered.length === 0) {
          grid.innerHTML = '<p class="events-grid__empty">رویدادی در این بخش ثبت نشده است.</p>';
          return;
        }

        grid.innerHTML = '';
        filtered.forEach((event) => grid.appendChild(buildFullEventCard(event)));
      }
    })
    .catch(() => {
      grid.innerHTML = '<p class="events-grid__empty">در حال حاضر امکان نمایش رویدادها نیست.</p>';
    });
}

function renderTagChips(container, activeTag) {
  container.innerHTML = '';
  Object.entries(PATH_TAGS).forEach(([slug, meta]) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'events-tags__btn';
    btn.dataset.tag = slug;
    btn.setAttribute('aria-pressed', String(slug === activeTag));
    btn.innerHTML = `${meta.icon}<span>${meta.label}</span>`;
    container.appendChild(btn);
  });
}

function buildFullEventCard(event) {
  const card = document.createElement('article');
  card.className = 'event-card event-card--full';

  card.appendChild(buildStatusBadge(event.status));

  const title = document.createElement('h3');
  title.className = 'event-card__title';
  title.textContent = event.title;
  card.appendChild(title);

  const tags = buildTagChips(event.tags);
  if (tags) card.appendChild(tags);

  if (event.date) card.appendChild(buildMeta(event.date));
  if (event.location) card.appendChild(buildMeta(event.location));

  if (event.schedule) {
    const parts = [];
    if (Array.isArray(event.schedule.days)) parts.push(event.schedule.days.join('، '));
    if (Array.isArray(event.schedule.times)) parts.push(event.schedule.times.join(' / '));
    if (event.schedule.duration_minutes) parts.push(`${event.schedule.duration_minutes} دقیقه`);
    if (parts.length) card.appendChild(buildMeta(parts.join(' — ')));
  }

  if (event.cast) {
    card.appendChild(buildGroup('عوامل', event.cast, GROUP_LABELS.cast));
  }

  if (event.context) {
    const context = document.createElement('p');
    context.className = 'event-card__context';
    context.textContent = event.context;
    card.appendChild(context);
  }

  const cta = buildBookingCta(event);
  if (cta) card.appendChild(cta);

  return card;
}

/* ============ صفحه جزییات رویداد ============ */
function initEventDetailPage() {
  const root = document.getElementById('eventDetailRoot');
  if (!root) return;

  const id = new URLSearchParams(location.search).get('id');

  fetchEvents()
    .then((events) => {
      const event = events.find((item) => item.id === id);
      if (!event) {
        root.innerHTML = `
          <p class="events-grid__empty">این رویداد پیدا نشد. شاید لینک قدیمی شده باشد.</p>
        `;
        return;
      }

      document.title = `${event.title} | خانه‌ی ماورا`;
      root.innerHTML = '';
      root.appendChild(buildEventDetail(event));
    })
    .catch(() => {
      root.innerHTML = '<p class="events-grid__empty">در حال حاضر امکان نمایش این رویداد نیست.</p>';
    });
}

function buildEventDetail(event) {
  const wrap = document.createElement('div');

  const header = document.createElement('div');
  header.className = 'event-detail__header';
  header.appendChild(buildStatusBadge(event.status));

  const title = document.createElement('h1');
  title.className = 'event-detail__title';
  title.textContent = event.title;
  header.appendChild(title);

  const tags = buildTagChips(event.tags);
  if (tags) header.appendChild(tags);

  wrap.appendChild(header);
  wrap.appendChild(buildDetailGallery(event.images, event.title));

  const body = document.createElement('div');
  body.className = 'event-detail__body';

  const main = document.createElement('div');
  main.className = 'event-detail__main';

  if (event.context) {
    const section = document.createElement('div');
    section.className = 'event-detail__section';
    const p = document.createElement('p');
    p.className = 'event-detail__context';
    p.textContent = event.context;
    section.appendChild(p);
    main.appendChild(section);
  }

  const infoItems = buildDetailInfo(event);
  if (infoItems) main.appendChild(infoItems);

  if (event.cast) {
    const section = document.createElement('div');
    section.className = 'event-detail__section';
    const heading = document.createElement('h2');
    heading.className = 'event-detail__section-title';
    heading.textContent = 'عوامل';
    section.appendChild(heading);
    section.appendChild(buildGroup('', event.cast, GROUP_LABELS.cast));
    main.appendChild(section);
  }

  body.appendChild(main);
  body.appendChild(buildDetailBooking(event));
  wrap.appendChild(body);

  return wrap;
}

function buildDetailGallery(images, title) {
  const gallery = document.createElement('div');
  gallery.className = 'event-detail__gallery';

  if (!Array.isArray(images) || images.length === 0) {
    gallery.classList.add('event-detail__gallery--empty');
    gallery.innerHTML = `
      <img src="${assetPath('assets/images/logo/mavara-emblem-640.webp')}" alt="" class="event-detail__gallery-placeholder-icon">
      <p>پوستر این رویداد به‌زودی اضافه می‌شود</p>
    `;
    return gallery;
  }

  const resolved = images.map(assetPath);

  const main = document.createElement('img');
  main.className = 'event-detail__gallery-main';
  main.src = resolved[0];
  main.alt = title;
  gallery.appendChild(main);

  if (resolved.length > 1) {
    const thumbs = document.createElement('div');
    thumbs.className = 'event-detail__gallery-thumbs';
    resolved.forEach((src, index) => {
      const thumb = document.createElement('button');
      thumb.type = 'button';
      thumb.className = 'event-detail__gallery-thumb';
      thumb.setAttribute('aria-pressed', String(index === 0));
      thumb.innerHTML = `<img src="${src}" alt="">`;
      thumb.addEventListener('click', () => {
        main.src = src;
        thumbs.querySelectorAll('.event-detail__gallery-thumb').forEach((t) => t.setAttribute('aria-pressed', 'false'));
        thumb.setAttribute('aria-pressed', 'true');
      });
      thumbs.appendChild(thumb);
    });
    gallery.appendChild(thumbs);
  }

  return gallery;
}

function buildDetailInfo(event) {
  const rows = [];

  if (event.date) rows.push(['تاریخ', event.date]);
  if (event.location) rows.push(['مکان', event.location]);

  if (event.schedule) {
    if (Array.isArray(event.schedule.days)) rows.push(['روزهای اجرا', event.schedule.days.join('، ')]);
    if (Array.isArray(event.schedule.times)) rows.push(['ساعت‌های اجرا', event.schedule.times.join(' — ')]);
    if (event.schedule.duration_minutes) rows.push(['مدت اجرا', `${event.schedule.duration_minutes} دقیقه`]);
  }

  if (rows.length === 0) return null;

  const section = document.createElement('div');
  section.className = 'event-detail__section';

  const heading = document.createElement('h2');
  heading.className = 'event-detail__section-title';
  heading.textContent = 'زمان و مکان';
  section.appendChild(heading);

  const grid = document.createElement('dl');
  grid.className = 'event-detail__info-grid';
  rows.forEach(([label, value]) => {
    const dt = document.createElement('dt');
    dt.textContent = label;
    const dd = document.createElement('dd');
    dd.textContent = value;
    grid.appendChild(dt);
    grid.appendChild(dd);
  });
  section.appendChild(grid);

  return section;
}

function buildDetailBooking(event) {
  const box = document.createElement('aside');
  box.className = 'event-detail__booking';

  const heading = document.createElement('h2');
  heading.className = 'event-detail__booking-title';

  if (event.status === 'archived') {
    heading.textContent = 'این رویداد به پایان رسیده است';
    box.appendChild(heading);
    const p = document.createElement('p');
    p.className = 'event-detail__booking-text';
    p.textContent = 'برای اطلاع از رویدادهای مشابه، رویدادهای جاری و پیش‌رو را ببین.';
    box.appendChild(p);
    const link = document.createElement('a');
    link.className = 'btn btn--gold';
    link.href = 'events.html';
    link.textContent = 'رویدادهای جاری';
    box.appendChild(link);
    return box;
  }

  heading.textContent = 'رزرو و هماهنگی';
  box.appendChild(heading);

  const buttons = buildBookingButtons(event);
  if (buttons) {
    box.appendChild(buttons);
  } else {
    const p = document.createElement('p');
    p.className = 'event-detail__booking-text';
    p.textContent = 'اطلاعات رزرو این رویداد به‌زودی اضافه می‌شود.';
    box.appendChild(p);
  }

  return box;
}

function buildTagChips(tags) {
  if (!Array.isArray(tags) || tags.length === 0) return null;

  const wrap = document.createElement('div');
  wrap.className = 'event-card__tags';

  tags.forEach((slug) => {
    const meta = PATH_TAGS[slug];
    if (!meta) return;
    const chip = document.createElement('span');
    chip.className = 'event-card__tag';
    chip.innerHTML = `${meta.icon}<span>${meta.label}</span>`;
    wrap.appendChild(chip);
  });

  return wrap.children.length ? wrap : null;
}

function buildGroup(title, data, labels) {
  const wrap = document.createElement('div');
  wrap.className = 'event-card__group';

  if (title) {
    const heading = document.createElement('p');
    heading.className = 'event-card__group-title';
    heading.textContent = title;
    wrap.appendChild(heading);
  }

  const list = document.createElement('ul');
  list.className = 'event-card__group-list';
  Object.entries(data).forEach(([key, value]) => {
    if (!value) return;
    const li = document.createElement('li');
    li.textContent = `${labels[key] || key}: ${value}`;
    list.appendChild(li);
  });
  wrap.appendChild(list);

  return wrap;
}

function buildStatusBadge(status) {
  const badge = document.createElement('span');
  badge.className = 'event-card__status';
  if (status === 'ongoing' || status === 'archived') {
    badge.classList.add(`event-card__status--${status}`);
  }
  badge.textContent = STATUS_LABELS[status] || status;
  return badge;
}

function buildMeta(text) {
  const meta = document.createElement('p');
  meta.className = 'event-card__meta';
  meta.textContent = text;
  return meta;
}

function buildBookingCta(event) {
  if (event.status === 'archived') return null;

  const cta = document.createElement('a');
  cta.className = 'btn btn--outline event-card__cta';
  cta.href = `${pagePath('event-detail.html')}?id=${encodeURIComponent(event.id)}`;
  cta.textContent = 'جزییات و رزرو';
  return cta;
}

function buildBookingButtons(event) {
  const wrap = document.createElement('div');
  wrap.className = 'event-detail__booking-actions';

  if (event.booking && event.booking.instagram) {
    const ig = document.createElement('a');
    ig.className = 'btn btn--gold';
    ig.href = `https://instagram.com/${event.booking.instagram.replace('@', '')}`;
    ig.target = '_blank';
    ig.rel = 'noopener';
    ig.textContent = 'رزرو از اینستاگرام';
    wrap.appendChild(ig);
  }

  if (event.booking && event.booking.phone) {
    const tel = document.createElement('a');
    tel.className = 'btn btn--outline-light';
    tel.href = `tel:${event.booking.phone}`;
    tel.textContent = event.booking.phone_note ? `تماس با ${event.booking.phone_note}` : 'تماس تلفنی';
    wrap.appendChild(tel);
  }

  return wrap.children.length ? wrap : null;
}
