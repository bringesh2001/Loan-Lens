import { api } from '../../../../services/api.service.js';
import { store } from '../../../../state/store.js';

const templateUrl = new URL('./summary-view.template.html', import.meta.url).href;
const cssUrl = new URL('./summary-view.css', import.meta.url).href;

export class SummaryViewComponent {
    constructor(container) {
        this.host = container;
        this.container = null;
        this.documentId = null;
    }

    async render(docId) {
        this.documentId = docId;

        // Load CSS
        if (!document.querySelector(`link[href="${cssUrl}"]`)) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = cssUrl;
            document.head.appendChild(link);
        }

        // Load Template
        const response = await fetch(templateUrl);
        const html = await response.text();
        this.host.innerHTML = html;
        this.container = this.host.querySelector('.summary-view');

        this.checkStateAndFetch();
    }

    async checkStateAndFetch() {
        const state = store.getState();

        // 1. Check if we already have data in store
        if (state.analysis.summary && state.document.id === this.documentId) {
            this.renderData(state.analysis.summary);
            return;
        }

        // 2. Fetch from API
        await this.fetchSummary();
    }

    async fetchSummary() {
        this.setLoading(true);
        try {
            const response = await api.getSummary(this.documentId);

            if (response.status === 'processing') {
                // Poll again after delay
                setTimeout(() => this.fetchSummary(), 2000);
                return;
            }

            if (response.status === 'failed') {
                throw new Error(response.error || 'Analysis failed');
            }

            // Update Store
            store.setState({
                analysis: {
                    ...store.getState().analysis,
                    summary: response.data
                }
            });

            this.renderData(response.data);

        } catch (error) {
            console.error('Summary fetch error:', error);
            this.setError(error.message);
        } finally {
            // Only turn off loading if we are not polling (i.e. if we rendered or error)
            // The polling recursion handles its own state, so here we assume finally runs on completion/error of THIS call
            // If simply scheduling next poll, we stay loading.
            // logic: if success or error, loading off. If processing, keep on.
        }
    }

    renderData(data) {
        this.setLoading(false);
        this.container.querySelector('#summary-content').style.display = 'block';

        // Overview
        const overviewEl = this.container.querySelector('#overview-text');
        overviewEl.innerHTML = this.formatOverview(data.overview);

        // Key Numbers
        this.setText('#val-total-loan', data.key_numbers.total_loan);
        this.setText('#val-monthly-pay', data.key_numbers.monthly_payment);
        this.setText('#val-interest-rate', data.key_numbers.interest_rate);
        this.setText('#val-term', data.key_numbers.term_months ? `${data.key_numbers.term_months} Months` : '-');

        // Highlights
        const highlightsContainer = this.container.querySelector('#highlights-container');
        highlightsContainer.innerHTML = '';

        data.highlights.forEach(h => {
            const card = document.createElement('div');
            card.className = `highlight-card ${this.getSentimentClass(h.type)}`;

            const icon = document.createElement('span');
            icon.className = 'highlight-icon';
            icon.textContent = this.getSentimentIcon(h.type);

            const text = document.createElement('span');
            text.className = 'highlight-text';
            text.textContent = h.text;

            card.appendChild(icon);
            card.appendChild(text);
            highlightsContainer.appendChild(card);
        });
    }

    setLoading(isLoading) {
        const loadingEl = this.container.querySelector('#summary-loading');
        const contentEl = this.container.querySelector('#summary-content');
        const errorEl = this.container.querySelector('#summary-error');

        if (isLoading) {
            loadingEl.style.display = 'flex';
            contentEl.style.display = 'none';
            errorEl.style.display = 'none';
        } else {
            loadingEl.style.display = 'none';
        }
    }

    setError(msg) {
        this.setLoading(false);
        const errorEl = this.container.querySelector('#summary-error');
        const msgEl = this.container.querySelector('#summary-error-msg');

        errorEl.style.display = 'block';
        msgEl.textContent = msg;

        const retryBtn = this.container.querySelector('#retry-btn');
        retryBtn.onclick = () => this.fetchSummary();
    }

    setText(selector, value) {
        const el = this.container.querySelector(selector);
        if (el) el.textContent = value || '-';
    }

    formatOverview(text) {
        // Bold numbers for emphasis
        return text.replace(/(\$[\d,]+|\d+(\.\d+)?%|\d+ months)/g, '<strong>$1</strong>');
    }

    getSentimentClass(type) {
        switch (type) {
            case 'positive': return 'positive';
            case 'warning': return 'warning';
            case 'negative': return 'negative';
            default: return 'warning';
        }
    }

    getSentimentIcon(type) {
        switch (type) {
            case 'positive': return '✓';
            case 'warning': return '⚠️';
            case 'negative': return '⚠️'; // Or specific icon
            default: return 'ℹ️';
        }
    }
}
