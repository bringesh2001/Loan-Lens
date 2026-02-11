import { navigate } from '../../../utils/helpers.js';
import { ROUTES } from '../../../utils/constants.js';

const templateUrl = new URL('./navbar.template.html', import.meta.url);
const cssUrl = new URL('./navbar.component.css', import.meta.url);

let templateCache = null;
let cssInjected = false;

async function loadTemplate() {
  if (templateCache) return templateCache;
  const res = await fetch(templateUrl);
  templateCache = await res.text();
  return templateCache;
}

function ensureCssInjected() {
  if (cssInjected) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = cssUrl;
  document.head.appendChild(link);
  cssInjected = true;
}

/**
 * Navbar component – renders the top navigation bar.
 */
export class NavbarComponent {
  /**
   * @param {Object} [options]
   * @param {string} [options.profileInitials]
   */
  constructor(options = {}) {
    this.options = {
      profileInitials: options.profileInitials || 'BH',
    };
  }

  /**
   * Render navbar into container element.
   * @param {HTMLElement} container
   */
  async render(container) {
    ensureCssInjected();
    const html = await loadTemplate();
    container.innerHTML = html;

    const profileEl = container.querySelector(
      '[data-role="profile-button"] .navbar__profile-initials',
    );
    if (profileEl) {
      profileEl.textContent = this.options.profileInitials;
    }

    const uploadBtn = container.querySelector(
      '[data-role="upload-button"]',
    );
    if (uploadBtn instanceof HTMLElement) {
      uploadBtn.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('loanlens:open-upload-sidebar'));
      });
    }
  }
}

