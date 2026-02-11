import { api } from './api.service.js';

/**
 * LLM analysis helpers that compose API calls.
 */
class LlmService {
  async fetchSummary(documentId) {
    return api.getSummary(documentId);
  }

  async fetchRedFlags(documentId) {
    return api.getRedFlags(documentId);
  }

  async fetchHiddenClauses(documentId) {
    return api.getHiddenClauses(documentId);
  }

  async fetchFinancialTerms(documentId, search) {
    return api.getFinancialTerms(documentId, search);
  }

  async chat(documentId, message, conversationId) {
    return api.chatWithDocument(documentId, {
      message,
      conversation_id: conversationId,
    });
  }
}

export const llmService = new LlmService();

