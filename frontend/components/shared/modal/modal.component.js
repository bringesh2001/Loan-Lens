export class ModalComponent {
    constructor(props = {}) {
        this.props = {
            title: props.title || '',
            content: props.content || '',
            onClose: props.onClose || (() => { }),
            isOpen: props.isOpen || false
        };
        this.element = null;
    }

    async render() {
        if (!this.template) {
            const response = await fetch('/components/shared/modal/modal.template.html');
            this.template = await response.text();
        }

        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = this.template;
        this.element = tempDiv.firstElementChild;

        // Apply props
        this.update();

        // Event listeners
        const closeBtn = this.element.querySelector('.modal-close');
        const overlay = this.element; // The outer div acts as overlay

        closeBtn.addEventListener('click', () => this.handleClose());

        // Close on overlay click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                this.handleClose();
            }
        });

        return this.element;
    }

    update() {
        if (this.element) {
            const titleEl = this.element.querySelector('.modal-title');
            const contentEl = this.element.querySelector('.modal-body');

            titleEl.textContent = this.props.title;

            // Allow HTML content or text
            if (typeof this.props.content === 'string') {
                contentEl.innerHTML = this.props.content;
            } else if (this.props.content instanceof HTMLElement) {
                contentEl.innerHTML = '';
                contentEl.appendChild(this.props.content);
            }

            if (this.props.isOpen) {
                this.element.classList.add('visible');
            } else {
                this.element.classList.remove('visible');
            }
        }
    }

    handleClose() {
        this.props.isOpen = false;
        this.update();
        this.props.onClose();
    }

    open() {
        this.props.isOpen = true;
        this.update();
    }

    close() {
        this.props.isOpen = false;
        this.update();
    }
}
