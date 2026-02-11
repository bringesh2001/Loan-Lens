import { api } from './api.service.js';

/**
 * PDF-related domain helpers.
 */
class PdfService {
  /**
   * Upload a PDF and return document metadata.
   * @param {File} file
   */
  async uploadAndRegister(file) {
    return api.uploadDocument(file);
  }
}

export const pdfService = new PdfService();

