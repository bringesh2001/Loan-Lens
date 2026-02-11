import { http } from './http.service.js';

/**
 * Thin wrapper over HTTP for core backend endpoints.
 * All other domain-specific services should build on top of this.
 */
class ApiService {
  /**
   * Upload a PDF document.
   * @param {File} file
   * @returns {Promise<any>}
   */
  async uploadDocument(file) {
    const formData = new FormData();
    formData.append('file', file);
    return http.request('/documents', {
      method: 'POST',
      isFormData: true,
      body: formData,
    });
  }

  /**
   * Get summary for a document.
   * @param {string} documentId
   */
  async getSummary(documentId) {
    return http.request(`/documents/${encodeURIComponent(documentId)}/summary`);
  }

  /**
   * Get red flags.
   * @param {string} documentId
   */
  async getRedFlags(documentId) {
    return http.request(
      `/documents/${encodeURIComponent(documentId)}/red-flags`,
    );
  }

  /**
   * Get hidden clauses.
   * @param {string} documentId
   */
  async getHiddenClauses(documentId) {
    return http.request(
      `/documents/${encodeURIComponent(documentId)}/hidden-clauses`,
    );
  }

  /**
   * Get financial terms.
   * @param {string} documentId
   * @param {string} [search]
   */
  async getFinancialTerms(documentId, search) {
    const params = search ? `?search=${encodeURIComponent(search)}` : '';
    return http.request(
      `/documents/${encodeURIComponent(documentId)}/financial-terms${params}`,
    );
  }

  /**
   * Chat with document.
   * @param {string} documentId
   * @param {{ message: string, conversation_id?: string }} payload
   */
  async chatWithDocument(documentId, payload) {
    return http.request(`/documents/${encodeURIComponent(documentId)}/chat`, {
      method: 'POST',
      body: payload,
    });
  }
}

export const api = new ApiService();

