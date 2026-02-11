import { api } from '../../../services/api.service.js';
import { store } from '../../../state/store.js';

const templateUrl = new URL('./sidebar.template.html', import.meta.url).href;
const cssUrl = new URL('./sidebar.css', import.meta.url).href;

export class SidebarComponent {
    constructor() {
        this.container = null;
        this.overlay = null;
        this.file = null;
        this.isUploading = false;
    }

    async render(parent) {
        // Load CSS
        if (!document.querySelector(`link[href="${cssUrl}"]`)) {
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = cssUrl;
            document.head.appendChild(link);
        }

        // Load Template
        if (!this.template) {
            const response = await fetch(templateUrl);
            this.template = await response.text();
        }

        const wrapper = document.createElement('div');
        wrapper.innerHTML = this.template;
        this.container = wrapper.firstElementChild;
        parent.appendChild(this.container);

        this.overlay = this.container; // The outer div is the overlay
        this.attachEvents();
    }

    attachEvents() {
        const closeBtn = this.container.querySelector('#close-sidebar');
        const uploadArea = this.container.querySelector('#upload-area');
        const fileInput = this.container.querySelector('#file-input');
        const uploadBtn = this.container.querySelector('#upload-btn');
        const overlay = this.container;

        // Close actions
        closeBtn.addEventListener('click', () => this.close());
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this.close();
        });

        // File selection
        uploadArea.addEventListener('click', (e) => {
            // Prevent double-trigger if clicking the label (which already triggers input)
            // or if the event bubbled up from the input itself
            if (e.target.closest('label') || e.target === fileInput) {
                return;
            }
            fileInput.click();
        });

        // Drag & Drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });
        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });
        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                this.handleFileSelect(e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) {
                this.handleFileSelect(e.target.files[0]);
            }
        });

        // Upload action
        uploadBtn.addEventListener('click', () => this.handleUpload());
    }

    handleFileSelect(file) {
        if (file.type !== 'application/pdf') {
            alert('Only PDF files are allowed');
            return;
        }
        this.file = file;
        const fileNameEl = this.container.querySelector('#file-name');
        fileNameEl.textContent = file.name;

        const uploadBtn = this.container.querySelector('#upload-btn');
        uploadBtn.disabled = false;
    }

    async handleUpload() {
        if (!this.file || this.isUploading) return;

        this.isUploading = true;
        const uploadBtn = this.container.querySelector('#upload-btn');
        const originalText = uploadBtn.textContent;
        uploadBtn.textContent = 'Uploading...';
        uploadBtn.disabled = true;

        try {
            const response = await api.uploadDocument(this.file);

            // Update store
            store.setState({
                document: {
                    id: response.document_id,
                    filename: response.filename,
                    uploadedAt: response.uploaded_at,
                    fileBlob: this.file // Store for preview
                }
            });

            this.close();
            // No navigation needed - state update triggers Home Page re-render

        } catch (error) {
            console.error('Upload failed:', error);
            alert('Upload failed: ' + error.message);
        } finally {
            this.isUploading = false;
            uploadBtn.textContent = originalText;
            uploadBtn.disabled = false;
        }
    }

    open() {
        if (this.container) {
            // Small timeout to allow transition to work if just rendered
            setTimeout(() => this.container.classList.add('open'), 10);
        }
    }

    close() {
        if (this.container) {
            this.container.classList.remove('open');
            // Reset state after transition
            setTimeout(() => {
                this.file = null;
                this.container.querySelector('#file-name').textContent = '';
                this.container.querySelector('#file-input').value = ''; // Reset input
                this.container.querySelector('#upload-btn').disabled = true;
            }, 300);
        }
    }
}
