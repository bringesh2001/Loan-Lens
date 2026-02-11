import { initRouter } from './router/router.js';
import { store } from './state/store.js';

/**
 * Application bootstrap.
 */
function bootstrap() {
  const appRoot = document.getElementById('app');
  if (!appRoot) {
    // Fail fast in development – this should never happen
    // eslint-disable-next-line no-console
    console.error('Root element #app not found');
    return;
  }

  // Simple global error listener (can be extended later)
  window.addEventListener('error', (event) => {
    store.setState({
      ui: {
        ...store.getState().ui,
        globalError: event.message || 'Unexpected error occurred',
      },
    });
  });

  initRouter(appRoot);
}

bootstrap();

