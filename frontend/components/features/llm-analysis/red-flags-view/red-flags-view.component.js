import { api } from '../../../../../services/api.service.js';
import { store } from '../../../../../state/store.js';

const templateUrl = new URL('./red-flags-view.template.html', import.meta.url).href;
const cssUrl = new URL('./red-flags-view.css', import.meta.url).href;

export class RedFlagsViewComponent {
    constructor(container) {
        this.host = container;
        this.container = null;
        this.documentId = null;
        this.data = null;
        this.isLoading = false;
    }

    async render(docId) {
        this.documentId = docId;

        // 1. Load CSS
        if (!document.querySelector(`link[href="${cssUrl}"]`)) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = cssUrl;
            document.head.appendChild(link);
        }

        // 2. Load Template
        const response = await fetch(templateUrl);
        const html = await response.text();
        this.host.innerHTML = html;
        this.container = this.host.querySelector('.red-flags-container');

        // 3. Attach Event Listeners
        this.container.querySelector('#rf-retry-btn').addEventListener('click', () => {
            this.fetchData();
        });

        // 4. Check store or fetch data
        const state = store.getState();
        if (state.analysis && state.analysis.redFlags && state.analysis.redFlags.documentId === docId) {
            this.data = state.analysis.redFlags.data;
            this.displayContent();
        } else {
            this.fetchData();
        }
    }

    async fetchData() {
        this.setLoading(true);
        try {
            const result = await api.getRedFlags(this.documentId);

            // Update Store
            store.setState({
                analysis: {
                    ...store.getState().analysis,
                    redFlags: {
                        documentId: this.documentId,
                        data: result
                    }
                }
            });

            this.data = result;
            this.displayContent();
        } catch (error) {
            console.error('Red Flags fetch error:', error);
            this.setError(error.message || 'Failed to load analysis.');
        } finally {
            this.setLoading(false);
        }
    }

    displayContent() {
        if (!this.container) return;

        // Hide loading/error
        this.container.querySelector('#rf-loading').style.display = 'none';
        this.container.querySelector('#rf-error').style.display = 'none';
        const contentEl = this.container.querySelector('#rf-content');
        contentEl.style.display = 'block';

        const data = this.data;
        const listContainer = this.container.querySelector('#rf-list');
        const emptyState = this.container.querySelector('#rf-empty');
        const countBadge = this.container.querySelector('#rf-count');

        // Update count
        countBadge.textContent = data.count || 0;

        if (!data.data || data.data.length === 0) {
            listContainer.innerHTML = '';
            emptyState.style.display = 'block';
            return;
        }

        emptyState.style.display = 'none';

        // Render List
        listContainer.innerHTML = data.data.map(item => `
            <div class="risk-card severity-${item.severity}">
                <div class="risk-header">
                    <span class="risk-title">${item.title}</span>
                    <span class="risk-severity">${item.severity} Risk</span>
                </div>
                <div class="risk-description">${item.description}</div>
                <div class="risk-recommendation">
                    <span class="rec-title">Recommendation</span>
                    ${item.recommendation}
                </div>
            </div>
        `).join('');
    }

    setLoading(isLoading) {
        this.isLoading = isLoading;
        if (!this.container) return;

        const loadingEl = this.container.querySelector('#rf-loading');
        const contentEl = this.container.querySelector('#rf-content');
        const errorEl = this.container.querySelector('#rf-error');

        if (isLoading) {
            loadingEl.style.display = 'block';
            contentEl.style.display = 'none';
            errorEl.style.display = 'none';
        } else {
            loadingEl.style.display = 'none';
        }
    }

    setError(msg) {
        if (!this.container) return;

        this.container.querySelector('#rf-loading').style.display = 'none';
        this.container.querySelector('#rf-content').style.display = 'none';
        const errorEl = this.container.querySelector('#rf-error');
        errorEl.style.display = 'block';
        this.container.querySelector('#rf-error-msg').textContent = msg;
    }
}
