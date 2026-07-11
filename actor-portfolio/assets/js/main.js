document.addEventListener('DOMContentLoaded', () => {
  initNavToggle();
  initHomeEventsPreview();
  initEventsPage();
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

function dataPath(file) {
  return location.pathname.includes('/pages/') ? `../data/${file}` : `data/${file}`;
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

/* ============ صفحه رویدادها (تب‌ها + کارت کامل) ============ */
function initEventsPage() {
  const tabs = document.getElementById('eventsTabs');
  const grid = document.getElementById('eventsGrid');
  if (!tabs || !grid) return;

  fetchEvents()
    .then((events) => {
      renderEventsTab(grid, events, 'ongoing');

      tabs.querySelectorAll('.events-tabs__btn').forEach((btn) => {
        btn.addEventListener('click', () => {
          tabs.querySelectorAll('.events-tabs__btn').forEach((b) => b.setAttribute('aria-selected', 'false'));
          btn.setAttribute('aria-selected', 'true');
          renderEventsTab(grid, events, btn.dataset.status);
        });
      });
    })
    .catch(() => {
      grid.innerHTML = '<p class="events-grid__empty">در حال حاضر امکان نمایش رویدادها نیست.</p>';
    });
}

function renderEventsTab(grid, events, status) {
  const filtered = events.filter((event) => event.status === status);

  if (filtered.length === 0) {
    grid.innerHTML = '<p class="events-grid__empty">رویدادی در این بخش ثبت نشده است.</p>';
    return;
  }

  grid.innerHTML = '';
  filtered.forEach((event) => grid.appendChild(buildFullEventCard(event)));
}

function buildFullEventCard(event) {
  const card = document.createElement('article');
  card.className = 'event-card event-card--full';

  card.appendChild(buildStatusBadge(event.status));

  const title = document.createElement('h3');
  title.className = 'event-card__title';
  title.textContent = event.title;
  card.appendChild(title);

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

function buildGroup(title, data, labels) {
  const wrap = document.createElement('div');
  wrap.className = 'event-card__group';

  const heading = document.createElement('p');
  heading.className = 'event-card__group-title';
  heading.textContent = title;
  wrap.appendChild(heading);

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
  if (!event.booking || !(event.booking.instagram || event.booking.phone)) return null;

  const cta = document.createElement('a');
  cta.className = 'btn btn--outline event-card__cta';
  if (event.booking.instagram) {
    cta.href = `https://instagram.com/${event.booking.instagram.replace('@', '')}`;
    cta.target = '_blank';
    cta.rel = 'noopener';
  } else {
    cta.href = `tel:${event.booking.phone}`;
  }
  cta.textContent = 'هماهنگی';
  return cta;
}
