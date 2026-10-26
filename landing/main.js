// Scroll-reveal
const io = new IntersectionObserver(
  (entries) =>
    entries.forEach((e) => {
      if (e.isIntersecting) {
        e.target.classList.add('in')
        io.unobserve(e.target)
      }
    }),
  { threshold: 0.12 },
)
document.querySelectorAll('.reveal').forEach((el, i) => {
  el.style.transitionDelay = `${(i % 3) * 90}ms`
  io.observe(el)
})

// Autopilot log (generated from git history by scripts/autopilot_log.py)
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
const day = (iso) => new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })

function countUp(el, to) {
  const start = performance.now()
  const step = (t) => {
    const p = Math.min(1, (t - start) / 1200)
    el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3)))
    if (p < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

// The release's changelog, grouped (Security, Fixed, Added, ...). The newest one starts open.
function releaseNotes(release, open) {
  const groups = Object.entries(release.groups || {})
  if (!groups.length) return ''
  const count = groups.reduce((n, [, items]) => n + items.length, 0)
  const body = groups
    .map(([name, items]) => `<h5>${esc(name)}</h5><ul>${items.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`)
    .join('')
  return `<details class="notes"${open ? ' open' : ''}><summary>Changelog · ${count} changes</summary>${body}</details>`
}

async function loadAutopilot() {
  const list = document.getElementById('timeline')
  let data
  try {
    const res = await fetch('autopilot.json', { cache: 'no-cache' })
    data = await res.json()
  } catch {
    list.innerHTML = '<li class="muted">The autopilot log is not available right now.</li>'
    return
  }
  const fixes = data.merges.reduce((n, m) => n + m.review_fixes, 0)
  const stats = { commits: data.commits, merges: data.merges.length, fixes, releases: data.releases.length }
  const statsObserver = new IntersectionObserver(([e]) => {
    if (!e.isIntersecting) return
    document.querySelectorAll('[data-stat]').forEach((el) => countUp(el, stats[el.dataset.stat]))
    statsObserver.disconnect()
  })
  statsObserver.observe(document.querySelector('.stats'))

  const items = [
    ...data.merges.map((m) => ({ kind: 'merge', date: m.date, ...m })),
    ...data.releases.map((r) => ({ kind: 'release', ...r })),
  ].sort((a, b) => b.date.localeCompare(a.date))

  const latest = data.releases[0]?.name
  list.innerHTML = items
    .map((it) =>
      it.kind === 'release'
        ? `<li class="release"><div class="meta"><span class="pill rel">release</span>${day(it.date)}</div>
             <h4>${esc(it.name)}</h4><p>${esc(it.intro || 'Tagged and released by the agent.')}</p>
             ${releaseNotes(it, it.name === latest)}</li>`
        : `<li><div class="meta"><span class="pill merged">merged</span><span class="pill">${esc(it.branch)}</span>
             ${it.commits} commits · ${it.review_fixes} self-review fix${it.review_fixes === 1 ? '' : 'es'} · ${day(it.date)} · ${esc(it.sha)}</div>
             <p>${esc(it.summary)}</p></li>`,
    )
    .join('')
}

loadAutopilot()
