import { ROUTES } from '../utils/constants.js';

/**
 * Simple client-side router using History API and dynamic imports.
 */
const routes = {
  [ROUTES.HOME]: () => import('../pages/home/home.page.js'),
  // Other routes removed for single-page component replacement architecture
};

/**
 * Resolve current path (no query/hash).
 */
function getCurrentPath() {
  const { pathname } = window.location;
  return pathname || ROUTES.HOME;
}

/**
 * Initialize router.
 * @param {HTMLElement} rootEl
 */
export function initRouter(rootEl) {
  const render = async () => {
    const path = getCurrentPath();
    const loader = routes[path] || routes[ROUTES.HOME];

    rootEl.innerHTML = '';
    const pageContainer = document.createElement('div');
    pageContainer.className = 'app-shell__main page-enter';
    rootEl.appendChild(pageContainer);

    try {
      const module = await loader();
      if (typeof module.render !== 'function') {
        // eslint-disable-next-line no-console
        console.error(`Route module for ${path} does not export render()`);
        pageContainer.textContent = 'Page failed to load.';
        return;
      }
      await module.render(pageContainer);
    } finally {
      // trigger enter transition
      requestAnimationFrame(() => {
        pageContainer.classList.add('page-enter-active');
      });
    }
  };

  window.addEventListener('popstate', render);

  // Link delegation for <a data-link>
  document.body.addEventListener('click', (event) => {
    const target = /** @type {HTMLElement} */ (event.target);
    if (target instanceof HTMLAnchorElement && target.dataset.link === 'router') {
      event.preventDefault();
      const href = target.getAttribute('href') || ROUTES.HOME;
      window.history.pushState({}, '', href);
      render();
    }
  });

  render();
}

