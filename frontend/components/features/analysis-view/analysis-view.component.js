import { store } from '../../../state/store.js';
import { SummaryViewComponent } from '../llm-analysis/summary-view/summary-view.component.js';
import { RedFlagsViewComponent } from '../llm-analysis/red-flags-view/red-flags-view.component.js';

const templateUrl = new URL('./analysis.template.html', import.meta.url).href;
const cssUrl = new URL('./analysis.css', import.meta.url).href;

export class AnalysisViewComponent {
    constructor(container) {
        this.host = container;
        this.container = null;
        this.tabs = {
            summary: null,
            redFlags: null,
            hiddenClauses: null,
            financialTerms: null,
            chat: null
        };
    }

    async render() {
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
        this.container = this.host.querySelector('.analysis-container');

        // 3. Initialize Logic
        this.init();
    }

    init() {
        const state = store.getState();
        const pdfFrame = this.container.querySelector('#pdf-frame');
        const tabBtns = this.container.querySelectorAll('.tab-btn');
        const tabPanes = this.container.querySelectorAll('.tab-pane');

        // Load PDF if exists
        if (state.document && state.document.id) {
            if (state.document.fileBlob) {
                const url = URL.createObjectURL(state.document.fileBlob);
                // Try to hide native toolbar to keep the custom "clean" look
                pdfFrame.src = `${url}#toolbar=0&navpanes=0&scrollbar=0&view=FitH`;
            } else {
                pdfFrame.srcdoc = '<div style="display:flex;justify-content:center;align-items:center;height:100%;color:#666;flex-direction:column;gap:1rem;"><span style="font-size:2rem">📄</span><span>PDF Preview Unavailable (File not in memory)</span></div>';
            }
        } else {
            pdfFrame.srcdoc = '<div style="display:flex;justify-content:center;align-items:center;height:100%;color:#666;flex-direction:column;gap:1rem;"><span style="font-size:2rem">📄</span><span>No document selected</span></div>';
        }

        // Tab Switching Logic
        tabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                // Remove active class from all
                tabBtns.forEach(b => b.classList.remove('active'));
                tabPanes.forEach(p => p.classList.remove('active'));

                // Add active to clicked
                btn.classList.add('active');
                const tabId = btn.dataset.tab;
                const pane = this.container.querySelector(`#tab-${tabId}`);
                if (pane) pane.classList.add('active');

                // Lazy load tab content
                this.loadTabContent(tabId);
            });
        });

        // Initialize Summary View (default)
        if (state.document && state.document.id) {
            this.loadTabContent('summary');
        }
    }

    loadTabContent(tabId) {
        const state = store.getState();
        if (!state.document || !state.document.id) return;

        const docId = state.document.id;

        switch (tabId) {
            case 'summary':
                if (!this.tabs.summary) {
                    const el = this.container.querySelector('#summary-view-container');
                    if (el) {
                        this.tabs.summary = new SummaryViewComponent(el);
                        this.tabs.summary.render(docId);
                    }
                }
                break;
            case 'red-flags':
                if (!this.tabs.redFlags) {
                    // Create container if not exists (it should exist from template)
                    // The template has placeholders like <div id="tab-red-flags">...</div>
                    // We need to inject the component into that pane
                    const pane = this.container.querySelector('#tab-red-flags');
                    if (pane) {
                        // Clear placeholder text
                        pane.innerHTML = '<div id="red-flags-view-container"></div>';
                        const el = pane.querySelector('#red-flags-view-container');
                        this.tabs.redFlags = new RedFlagsViewComponent(el);
                        this.tabs.redFlags.render(docId);
                    }
                }
                break;
            case 'hidden-clauses':
                // Coming next
                break;
            case 'financial-terms':
                // Coming later
                break;
            case 'chat':
                // Coming later
                break;
        }
    }
}
