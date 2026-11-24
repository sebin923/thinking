// Hash addresses also work on static hosting without server rewrite rules.
const PAGES = new Set([
  "home", "about", "learn", "write", "writing-settings", "quiz", "ranking",
  "challenge", "mypage", "mypage-edit", "admin", "login", "signup", "find-account", "notice",
  "terms", "privacy", "payment", "payment-result",
]);
const HISTORY_KEY = "saenggak-hanjul-navigation";

export function readPage(location) {
  const page = location.hash.replace(/^#\/?/, "");
  return PAGES.has(page) ? page : "home";
}

function pageUrl(page, location) {
  const paymentReturn = /^\/payment\/(success|fail)$/.test(location.pathname);
  const base = paymentReturn ? "/" : location.pathname + location.search;
  return base + (page === "home" ? "" : `#/${page}`);
}

function readEntry(state) {
  const entry = state?.[HISTORY_KEY];
  return entry && Number.isInteger(entry.index) && PAGES.has(entry.page) ? entry : null;
}

export function createPageHistory(browser, {
  initialPage, onChange, shouldBlock = () => false, onBlocked = () => {},
  onTraverse = () => {},
}) {
  const { history, location } = browser;
  const saved = readEntry(history.state);
  let current = {
    index: saved?.index ?? 0,
    page: initialPage || readPage(location),
    data: saved?.page === (initialPage || readPage(location)) ? saved.data : null,
  };
  let restoring = null;
  let approvedIndex = null;
  let revision = 0;

  const write = (entry, replace) => {
    history[replace ? "replaceState" : "pushState"](
      { ...history.state, [HISTORY_KEY]: entry }, "", pageUrl(entry.page, location),
    );
  };
  const apply = (entry, traversed = false) => {
    if (traversed) onTraverse(entry, current);
    current = entry;
    onChange(entry);
  };

  // Register the first screen without adding a duplicate home entry.
  write(current, true);
  onChange(current);

  const handlePop = (event) => {
    // An address typed into the hash bar creates an entry without our state.
    let next = readEntry(event.state);
    if (!next || next.page !== readPage(location)) {
      next = { index: current.index + 1, page: readPage(location), data: null };
      write(next, true);
    }

    if (restoring) {
      if (next.index !== current.index) return;
      const blocked = restoring;
      restoring = null;
      const blockedRevision = revision;
      // Restore the address before showing the existing leave confirmation.
      onBlocked(() => {
        if (revision !== blockedRevision) return;
        approvedIndex = blocked.index;
        history.go(blocked.index - current.index);
      });
      return;
    }

    revision += 1;
    if (approvedIndex === next.index) {
      approvedIndex = null;
      apply(next, true);
      return;
    }
    approvedIndex = null;
    if (next.index !== current.index && shouldBlock(next, current)) {
      restoring = next;
      history.go(current.index - next.index);
      return;
    }
    apply(next, true);
  };
  browser.addEventListener("popstate", handlePop);

  return {
    navigate(page, { replace = false, data = null } = {}) {
      if (!PAGES.has(page) || restoring) return;
      revision += 1;
      // Repeated menu clicks must not make the Back button appear stuck.
      if (page === current.page && JSON.stringify(data) === JSON.stringify(current.data)) return;
      const next = { index: current.index + (replace ? 0 : 1), page, data };
      write(next, replace);
      apply(next);
    },
    back(fallback, data = null) {
      if (current.index > 0) history.back();
      else this.navigate(fallback, { replace: true, data });
    },
    destroy() {
      revision += 1;
      browser.removeEventListener("popstate", handlePop);
    },
  };
}
