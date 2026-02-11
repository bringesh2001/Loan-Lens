import { ENV } from '../config/env.js';

/**
 * @typedef {Object} HttpRequestOptions
 * @property {'GET'|'POST'|'PUT'|'PATCH'|'DELETE'} [method]
 * @property {Object} [headers]
 * @property {any} [body]
 * @property {boolean} [isFormData]
 * @property {number} [timeoutMs]
 */

/**
 * Centralized HTTP client using Fetch with basic interceptors and timeouts.
 */
class HttpService {
  constructor() {
    /** @type {(config: RequestInit & { url: string }) => (RequestInit & { url: string })} */
    this.requestInterceptor = (config) => config;
    /** @type {(response: Response) => Response} */
    this.responseInterceptor = (response) => response;
  }

  /**
   * @param {(config: RequestInit & { url: string }) => (RequestInit & { url: string })} interceptor
   */
  setRequestInterceptor(interceptor) {
    this.requestInterceptor = interceptor;
  }

  /**
   * @param {(response: Response) => Response} interceptor
   */
  setResponseInterceptor(interceptor) {
    this.responseInterceptor = interceptor;
  }

  /**
   * Perform an HTTP request.
   * @param {string} path
   * @param {HttpRequestOptions} [options]
   */
  async request(path, options = {}) {
    const {
      method = 'GET',
      headers = {},
      body,
      isFormData = false,
      timeoutMs = ENV.API_TIMEOUT_MS,
    } = options;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    const url = `${ENV.API_BASE_URL}${path}`;

    /** @type {RequestInit & { url: string }} */
    let config = {
      url,
      method,
      headers: {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...headers,
      },
      body: body
        ? isFormData
          ? body
          : JSON.stringify(body)
        : undefined,
      signal: controller.signal,
      credentials: 'same-origin',
    };

    config = this.requestInterceptor(config);

    let response;
    try {
      response = await fetch(config.url, config);
      response = this.responseInterceptor(response);
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Request timed out');
      }
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }

    if (!response.ok) {
      let errorPayload;
      try {
        errorPayload = await response.json();
      } catch {
        // Ignore JSON parse errors
      }
      const message =
        (errorPayload && (errorPayload.detail || errorPayload.error)) ||
        `Request failed with status ${response.status}`;
      const err = new Error(message);
      // Attach raw response for debugging
      // @ts-ignore
      err.status = response.status;
      // @ts-ignore
      err.payload = errorPayload;
      throw err;
    }

    const contentType = response.headers.get('Content-Type') || '';
    if (contentType.includes('application/json')) {
      return response.json();
    }
    return response.text();
  }
}

export const http = new HttpService();

