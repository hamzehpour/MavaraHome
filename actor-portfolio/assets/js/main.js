document.addEventListener('DOMContentLoaded', () => {
  initNavToggle();
  initHomeEventsPreview();
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

function fetchEvents() {
  return fetch('data/events.json').then((res) => {
    if (!res.ok) throw new Error('events.json not found');
    return res.json();
  });
}

function buildEventCard(event) {
  const card = document.createElement('article');
  card.className = 'event-card';

  const status = document.createElement('span');
  status.className = 'event-card__status';
  status.textContent = STATUS_LABELS[event.status] || event.status;
  card.appendChild(status);

  const title = document.createElement('h3');
  title.className = 'event-card__title';
  title.textContent = event.title;
  card.appendChild(title);

  if (event.location) {
    const meta = document.createElement('p');
    meta.className = 'event-card__meta';
    meta.textContent = event.location;
    card.appendChild(meta);
  }

  if (event.schedule && Array.isArray(event.schedule.days)) {
    const days = document.createElement('p');
    days.className = 'event-card__meta';
    days.textContent = event.schedule.days.join('، ');
    card.appendChild(days);
  }

  const bookingLink = event.booking && (event.booking.instagram || event.booking.phone);
  if (bookingLink) {
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
    card.appendChild(cta);
  }

  return card;
}
