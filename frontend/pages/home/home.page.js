import { NavbarComponent } from '../../components/layout/navbar/navbar.component.js';
import { SidebarComponent } from '../../components/layout/sidebar/sidebar.component.js';
import { AnalysisViewComponent } from '../../components/features/analysis-view/analysis-view.component.js';
import { store } from '../../state/store.js';

/**
 * Home page - Orchestrates the main view switching.
 * @param {HTMLElement} rootEl
 */
export async function render(rootEl) {
  // Shell wrapper
  const shell = document.createElement('div');
  shell.className = 'app-shell';

  const content = document.createElement('div');
  content.className = 'app-shell__main';

  // Wrapper for the dynamic content (Welcome vs Analysis)
  const viewContainer = document.createElement('div');
  viewContainer.id = 'main-view-container';

  // Navbar
  const navbarHost = document.createElement('div');
  const navbar = new NavbarComponent({ profileInitials: 'BH' });
  await navbar.render(navbarHost);

  content.appendChild(navbarHost);
  content.appendChild(viewContainer);
  shell.appendChild(content);
  rootEl.appendChild(shell);

  // Initialize Sidebar (Overlay)
  const sidebar = new SidebarComponent();
  await sidebar.render(rootEl);
  window.addEventListener('loanlens:open-upload-sidebar', () => sidebar.open());

  // Function to render the correct view based on state
  const renderView = async () => {
    const state = store.getState();
    viewContainer.innerHTML = ''; // Clear current view

    if (state.document && state.document.id) {
      // Show Analysis View
      const analysisView = new AnalysisViewComponent(viewContainer);
      await analysisView.render();
    } else {
      // Show Welcome View
      viewContainer.innerHTML = `
        <div style="margin-top: 1.25rem;">
          <div class="card" style="padding: 1.75rem; min-height: 200px; margin: 0.5rem;">
            <h1 style="margin: 0 0 0.5rem 0; font-size: 1.35rem;">Welcome to LoanLens</h1>
            <p class="text-muted" style="max-width: 520px; font-size: 0.9rem;">
              Use the <strong>Upload New Doc</strong> button in the top right to start analyzing your loan agreement.
            </p>
          </div>
        </div>
      `;
    }
  };

  // Initial Render
  await renderView();

  // Subscribe to store changes
  store.subscribe(() => {
    // Re-render when state changes (specifically document)
    // Optimization: Check if document ID actually changed to avoid re-rendering blindly
    // For now, simple re-render is fine for this MVP scale.
    renderView();
  });
}
