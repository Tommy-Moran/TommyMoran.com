/* ============================================================
   T-Minus 400 — Script
   ============================================================
   Dynamic state is fetched from goals-data.json at page load.
   To update the page, edit goals-data.json:

   goal_states:     Set status, completed_date, notes, evidence per goal id
   timeline_events: Add milestones (race results, gigs, etc.)
   updates:         Add timestamped entries to the feed
   financial:       Set debt_total_start, debt_remaining, savings when ready
   ============================================================ */

/* ---- Static goal definitions (never edited by the agent) ---- */
const GOAL_DEFS = [
  {
    id:            'music-release',
    title:         'Music Release',
    category:      'creative',
    icon:          'fa-music',
    description:   '6-track original project — written, recorded, mixed & mastered',
    pass_criteria: 'Public release on Spotify / Apple Music by Day 0'
  },
  {
    id:            'live-performance',
    title:         'Live Performance',
    category:      'creative',
    icon:          'fa-microphone',
    description:   'Perform original music at a ticketed public event or festival',
    pass_criteria: 'Verified public performance'
  },
  {
    id:            'screenplay-sale',
    title:         'Screenplay Sale',
    category:      'creative',
    icon:          'fa-film',
    description:   'Complete full-length screenplay — sold or optioned',
    pass_criteria: 'Signed purchase / option agreement'
  },
  {
    id:            'half-marathon-pr',
    title:         'Half-Marathon PR',
    category:      'athletic',
    icon:          'fa-person-running',
    description:   'Albert Park Half Marathon, June 2026 — beat 5:11/km baseline',
    pass_criteria: 'Official finish time under 5:11 min/km'
  },
  {
    id:            'strength-targets',
    title:         'Strength Targets',
    category:      'athletic',
    icon:          'fa-dumbbell',
    description:   'Single session: Chest 85 kg×5 / Squat 130 kg×5 / Deadlift 110 kg×5',
    pass_criteria: 'All three lifts in one session — controlled reps, no assistance'
  },
  {
    id:            'hockey-premier',
    title:         'Hockey Premier League',
    category:      'athletic',
    icon:          'fa-hockey-puck',
    description:   'Melbourne Sharks — appear in >50% of regular-season games',
    pass_criteria: 'Verified game appearances exceeding 50% of season'
  },
  {
    id:            'ecfmg-certification',
    title:         'ECFMG Certification',
    category:      'professional',
    icon:          'fa-certificate',
    description:   'USMLE Step 1 + Step 2 CK + full ECFMG certification',
    pass_criteria: 'Full ECFMG certification before Day 0'
  },
  {
    id:            'manuscript-publication',
    title:         'Manuscript Publication',
    category:      'professional',
    icon:          'fa-book-medical',
    description:   'Author on peer-reviewed journal publication',
    pass_criteria: 'Accepted for publication before Day 0'
  },
  {
    id:            'conference-presentation',
    title:         'Conference Presentation',
    category:      'professional',
    icon:          'fa-chalkboard-user',
    description:   'Present original research at a national/international cardiology conference',
    pass_criteria: 'Oral or poster presentation delivered'
  },
  {
    id:            'fracp-completion',
    title:         'FRACP Completion',
    category:      'professional',
    icon:          'fa-graduation-cap',
    description:   'Obtain FRACP cardiology qualification',
    pass_criteria: 'FRACP qualification obtained before Day 0'
  },
  {
    id:            'net-zero',
    title:         'Net Zero',
    category:      'financial',
    icon:          'fa-chart-line',
    description:   'Student bank debt fully offset by savings',
    pass_criteria: '(Savings − Debt) ≥ $0 by Day 0'
  }
];

const SOCIAL = {
  instagram: 'https://www.instagram.com/t-minus-400',
  tiktok:    'https://www.tiktok.com/@t-minus-400'
};

/* ---- Default dynamic state (used if JSON fetch fails) ---- */
const DEFAULT_DYNAMIC = {
  last_updated:    null,
  financial:       { debt_total_start: null, debt_remaining: null, savings: null, note: '' },
  goal_states:     {},
  timeline_events: [{ date: '2026-06-01', label: 'Half Marathon', description: 'Albert Park, Melbourne', type: 'event' }],
  updates:         []
};

/* ---- Merged goals (static defs + dynamic states) ---- */
let GOALS = [];
let DYNAMIC = DEFAULT_DYNAMIC;

/* ============================================================
   INIT
   ============================================================ */
document.addEventListener('DOMContentLoaded', async () => {
  initParticles();
  initCountdown();

  DYNAMIC = await fetchDynamic();
  GOALS   = mergeGoals(GOAL_DEFS, DYNAMIC.goal_states);

  renderGoals();
  initCategoryTabs();
  initScrollAnimations();
  renderTimeline();
  initTimelineDrag();
  renderFinancial();
  renderUpdates();
  renderLastUpdated();
});

/* ============================================================
   FETCH goals-data.json
   ============================================================ */
async function fetchDynamic() {
  try {
    const res = await fetch('./goals-data.json?v=' + Date.now());
    if (!res.ok) throw new Error('fetch failed');
    return await res.json();
  } catch {
    return DEFAULT_DYNAMIC;
  }
}

function mergeGoals(defs, states) {
  return defs.map(def => {
    const state = states[def.id] || {};
    return {
      ...def,
      status:         state.status         || 'in-progress',
      completed_date: state.completed_date || null,
      notes:          state.notes          || null,
      evidence:       state.evidence       || []
    };
  });
}

/* ============================================================
   PARTICLES
   ============================================================ */
function initParticles() {
  const canvas = document.getElementById('particle-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  let W, H, particles;
  const COUNT     = 75;
  const LINK_DIST = 130;

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  class Particle {
    constructor() { this.reset(true); }
    reset(init) {
      this.x  = Math.random() * W;
      this.y  = init ? Math.random() * H : (Math.random() < 0.5 ? -5 : H + 5);
      this.vx = (Math.random() - 0.5) * 0.22;
      this.vy = (Math.random() - 0.5) * 0.22;
      this.r  = Math.random() * 1.1 + 0.4;
      this.o  = Math.random() * 0.35 + 0.08;
    }
    update() {
      this.x += this.vx;
      this.y += this.vy;
      if (this.x < -10 || this.x > W + 10 || this.y < -10 || this.y > H + 10) this.reset(false);
    }
    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(255,255,255,${this.o})`;
      ctx.fill();
    }
  }

  resize();
  window.addEventListener('resize', resize);
  particles = Array.from({ length: COUNT }, () => new Particle());

  function frame() {
    ctx.clearRect(0, 0, W, H);
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx   = particles[i].x - particles[j].x;
        const dy   = particles[i].y - particles[j].y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < LINK_DIST) {
          ctx.beginPath();
          ctx.strokeStyle = `rgba(255,255,255,${(1 - dist / LINK_DIST) * 0.07})`;
          ctx.lineWidth   = 0.5;
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.stroke();
        }
      }
    }
    particles.forEach(p => { p.update(); p.draw(); });
    requestAnimationFrame(frame);
  }
  frame();
}

/* ============================================================
   COUNTDOWN
   ============================================================ */
function initCountdown() {
  const startDate = new Date('2026-02-22T00:00:00');
  const endDate   = new Date('2027-03-29T00:00:00');
  const totalMs   = endDate - startDate;

  function update() {
    const now           = new Date();
    const daysRemaining = Math.max(0, Math.ceil((endDate - now) / 86400000));
    const daysElapsed   = Math.max(0, Math.floor((now - startDate) / 86400000));
    const progress      = Math.min(100, Math.max(0, ((now - startDate) / totalMs) * 100));

    const daysEl   = document.getElementById('days-remaining');
    const dayNumEl = document.getElementById('day-number');
    const pctEl    = document.getElementById('progress-pct');
    const barEl    = document.getElementById('progress-bar');

    if (daysEl)   animateNumber(daysEl, daysRemaining);
    if (dayNumEl) dayNumEl.textContent = daysElapsed;
    if (pctEl)    pctEl.textContent    = progress.toFixed(1) + '%';
    if (barEl)    setTimeout(() => { barEl.style.width = progress.toFixed(3) + '%'; }, 300);
  }

  update();
  setInterval(update, 60000);
}

function animateNumber(el, target) {
  const start    = parseInt(el.textContent, 10) || target + 10;
  const duration = 1100;
  const t0       = performance.now();
  function step(now) {
    const t     = Math.min((now - t0) / duration, 1);
    const eased = 1 - Math.pow(1 - t, 3);
    el.textContent = Math.round(start + (target - start) * eased);
    if (t < 1) requestAnimationFrame(step);
    else        el.textContent = target;
  }
  requestAnimationFrame(step);
}

/* ============================================================
   GOAL CARDS
   ============================================================ */
function renderGoals() {
  const grid = document.getElementById('goals-grid');
  if (!grid) return;
  grid.innerHTML = '';
  GOALS.forEach((goal, i) => grid.appendChild(buildGoalCard(goal, i)));
}

function buildGoalCard(goal, index) {
  const statusLabels = {
    'in-progress': 'In Progress',
    'complete':    'Complete',
    'not-started': 'Not Started',
    'failed':      'Failed'
  };

  const evidenceHTML = goal.evidence.length
    ? `<div class="card-evidence">
        ${goal.evidence.map(e =>
          `<a href="${e.url}" target="_blank" rel="noopener noreferrer" class="evidence-link">
            <i class="fas fa-external-link-alt"></i>${e.label}
          </a>`
        ).join('')}
      </div>`
    : '';

  const notesHTML    = goal.notes          ? `<p class="card-notes">${goal.notes}</p>` : '';
  const completedHTML = goal.completed_date ? `<div class="card-completed-date">✓ Completed ${formatDate(goal.completed_date)}</div>` : '';

  const card = document.createElement('div');
  card.className            = `goal-card status-${goal.status}`;
  card.dataset.category     = goal.category;
  card.dataset.id           = goal.id;
  card.style.transitionDelay = `${index * 55}ms`;

  card.innerHTML = `
    <div class="card-header">
      <div class="card-category-icon"><i class="fas ${goal.icon}"></i></div>
      <span class="status-badge ${goal.status}">${statusLabels[goal.status]}</span>
    </div>
    <div class="card-title">${goal.title}</div>
    <p class="card-description">${goal.description}</p>
    <div class="card-criteria">
      <span class="card-criteria-label">Pass criteria</span>
      ${goal.pass_criteria}
    </div>
    ${evidenceHTML}${notesHTML}${completedHTML}
  `;
  return card;
}

/* ============================================================
   CATEGORY FILTER
   ============================================================ */
function initCategoryTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const filter = tab.dataset.filter;
      document.querySelectorAll('.goal-card').forEach(card => {
        card.classList.toggle('hidden', filter !== 'all' && card.dataset.category !== filter);
      });
    });
  });
}

/* ============================================================
   SCROLL ANIMATIONS
   ============================================================ */
function initScrollAnimations() {
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); });
  }, { threshold: 0.08 });
  document.querySelectorAll('.goal-card, .update-item').forEach(el => obs.observe(el));
}

/* ============================================================
   TIMELINE
   ============================================================ */
function renderTimeline() {
  const track = document.getElementById('timeline-track');
  if (!track) return;
  track.innerHTML = '';

  const startDate = new Date('2026-02-22T00:00:00');
  const endDate   = new Date('2027-03-29T00:00:00');
  const now       = new Date();
  const totalMs   = endDate - startDate;

  const milestones = [
    { date: startDate, label: 'Day −400', sub: 'Project launch', type: 'start' },
    ...DYNAMIC.timeline_events.map(ev => ({
      date:  new Date(ev.date + 'T00:00:00'),
      label: ev.label,
      sub:   ev.description,
      type:  ev.type || 'event'
    })),
    ...GOALS.filter(g => g.status === 'complete' && g.completed_date).map(g => ({
      date:  new Date(g.completed_date + 'T00:00:00'),
      label: g.title,
      sub:   'Complete ✓',
      type:  'complete'
    })),
    { date: now,     label: 'Today',   sub: null,             type: 'today' },
    { date: endDate, label: 'Day 0',   sub: 'Final judgement', type: 'end'   }
  ];

  milestones.sort((a, b) => a.date - b.date);

  const progressLine = document.createElement('div');
  progressLine.className = 'timeline-progress-line';
  track.appendChild(progressLine);

  const PX_PER_DAY = 3;
  const LEAD_IN    = 60;

  milestones.forEach((m, i) => {
    const ms = document.createElement('div');
    ms.className    = 'timeline-milestone';
    ms.dataset.type = m.type;

    if (i === 0) {
      ms.style.marginLeft = LEAD_IN + 'px';
    } else {
      const days = Math.round((m.date - milestones[i - 1].date) / 86400000);
      ms.style.marginLeft = Math.max(80, days * PX_PER_DAY) + 'px';
    }

    const labelTop = (i % 2 === 0);

    if (m.type === 'today') {
      const daysLeft = Math.ceil((endDate - now) / 86400000);
      ms.innerHTML = `
        <div class="milestone-label-top">${labelTop ? 'Today' : ''}</div>
        <div class="milestone-dot type-today"></div>
        <div class="${labelTop ? 'milestone-today-sub' : 'milestone-label-top'}">${labelTop ? `Day −${daysLeft}` : 'Today'}</div>
        ${!labelTop ? `<div class="milestone-today-sub">Day −${daysLeft}</div>` : ''}
      `;
    } else if (m.type === 'complete') {
      ms.innerHTML = `
        <div class="${labelTop ? 'milestone-label-top' : 'milestone-label-bottom'}">${m.label}</div>
        <div class="milestone-dot type-complete"></div>
        <div class="${labelTop ? 'milestone-complete-check' : 'milestone-label-top'}">✓</div>
      `;
    } else {
      ms.innerHTML = `
        <div class="${labelTop ? 'milestone-label-top' : 'milestone-label-bottom'}">${m.label}</div>
        <div class="milestone-dot type-${m.type}"></div>
        <div class="${labelTop ? 'milestone-label-bottom' : 'milestone-label-top'}">${m.sub || ''}</div>
      `;
    }

    track.appendChild(ms);
  });

  // Animate progress line to TODAY
  setTimeout(() => {
    const todayDot = track.querySelector('.milestone-dot.type-today');
    if (!todayDot) return;
    let offsetLeft = 0;
    let el = todayDot;
    while (el && el !== track) { offsetLeft += el.offsetLeft; el = el.offsetParent; }
    progressLine.style.width = (offsetLeft + todayDot.offsetWidth / 2) + 'px';
  }, 400);
}

/* ============================================================
   TIMELINE DRAG
   ============================================================ */
function initTimelineDrag() {
  const outer = document.getElementById('timeline-outer');
  if (!outer) return;

  let isDown = false, startX, scrollLeft;

  outer.addEventListener('mousedown', e => {
    isDown = true; startX = e.pageX - outer.offsetLeft; scrollLeft = outer.scrollLeft;
    outer.classList.add('dragging');
  });
  outer.addEventListener('mouseleave', () => { isDown = false; outer.classList.remove('dragging'); });
  outer.addEventListener('mouseup',    () => { isDown = false; outer.classList.remove('dragging'); });
  outer.addEventListener('mousemove',  e => {
    if (!isDown) return;
    e.preventDefault();
    outer.scrollLeft = scrollLeft - (e.pageX - outer.offsetLeft - startX) * 1.4;
  });

  let touchStartX, touchScroll;
  outer.addEventListener('touchstart', e => {
    touchStartX = e.touches[0].pageX - outer.offsetLeft; touchScroll = outer.scrollLeft;
  }, { passive: true });
  outer.addEventListener('touchmove', e => {
    outer.scrollLeft = touchScroll - (e.touches[0].pageX - outer.offsetLeft - touchStartX) * 1.4;
  }, { passive: true });
}

/* ============================================================
   FINANCIAL BAROMETER
   ============================================================ */
function renderFinancial() {
  const fin     = DYNAMIC.financial;
  const noteEl  = document.getElementById('financial-note');
  const valueEl = document.getElementById('gauge-value');
  const arcEl   = document.getElementById('gauge-fill-arc');

  if (!fin.debt_total_start) {
    if (noteEl) noteEl.innerHTML = `${fin.note || ''}<br>
      Follow <a href="${SOCIAL.instagram}" target="_blank" rel="noopener noreferrer">@t-minus-400</a> for the first update.`;
    return;
  }

  const netPos   = fin.savings - fin.debt_remaining;
  const progress = Math.min(100, Math.max(0,
    ((fin.debt_total_start - fin.debt_remaining + fin.savings) / fin.debt_total_start) * 100
  ));

  setTimeout(() => {
    if (arcEl) arcEl.style.strokeDashoffset = 251.3 - (progress / 100) * 251.3;
  }, 500);

  if (valueEl) {
    const sign = netPos >= 0 ? '+' : '-';
    const col  = netPos >= 0 ? 'var(--complete)' : 'var(--financial)';
    valueEl.innerHTML = `
      <span style="font-size:1.4rem;color:${col}">${sign}$${Math.abs(netPos).toLocaleString()}</span>
      <small style="font-size:0.55rem;letter-spacing:0.12em;text-transform:uppercase;color:var(--text-3);display:block;margin-top:0.25rem">Net position</small>
    `;
  }

  if (noteEl) noteEl.textContent = `$${fin.debt_remaining.toLocaleString()} debt remaining · $${fin.savings.toLocaleString()} saved`;
}

/* ============================================================
   UPDATES FEED
   ============================================================ */
function renderUpdates() {
  const list = document.getElementById('updates-list');
  if (!list) return;

  const updates = DYNAMIC.updates || [];
  if (!updates.length) {
    list.innerHTML = '<p class="no-updates">No updates yet — check back soon</p>';
    return;
  }

  list.innerHTML = '';
  [...updates].sort((a, b) => new Date(b.date) - new Date(a.date)).forEach(u => {
    const goal = GOALS.find(g => g.id === u.goal_id);
    const cat  = goal ? goal.category : 'professional';
    const item = document.createElement('div');
    item.className = 'update-item';
    item.innerHTML = `
      <div class="update-date">${formatDate(u.date)}</div>
      <div class="update-content">
        <span class="update-goal-tag" style="color:var(--${cat})">${goal ? goal.title : u.goal_id}</span>
        <p class="update-text">${u.text}</p>
        ${u.evidence_url
          ? `<a href="${u.evidence_url}" target="_blank" rel="noopener noreferrer" class="update-evidence-link">
              <i class="fas fa-external-link-alt"></i> View post
            </a>`
          : ''}
      </div>
    `;
    list.appendChild(item);
  });
}

/* ============================================================
   LAST UPDATED BADGE
   ============================================================ */
function renderLastUpdated() {
  const el = document.getElementById('last-updated');
  if (!el || !DYNAMIC.last_updated) return;
  el.textContent = 'Last synced ' + formatDate(DYNAMIC.last_updated);
  el.style.display = 'block';
}

/* ============================================================
   HELPERS
   ============================================================ */
function formatDate(dateStr) {
  return new Date(dateStr + 'T00:00:00').toLocaleDateString('en-AU', {
    day: 'numeric', month: 'short', year: 'numeric'
  });
}
