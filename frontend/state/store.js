/**
 * Very small global store with subscription support.
 */
class Store {
  constructor() {
    this._state = {
      document: {
        id: null,
        filename: null,
        uploadedAt: null,
      },
      analysis: {
        summary: null,
        redFlags: null,
        hiddenClauses: null,
        financialTerms: null,
      },
      ui: {
        loading: false,
        globalError: null,
      },
    };
    /** @type {Set<(state: any) => void>} */
    this._listeners = new Set();
  }

  getState() {
    return this._state;
  }

  /**
   * Shallow merge and notify subscribers.
   * @param {any} partial
   */
  setState(partial) {
    this._state = {
      ...this._state,
      ...partial,
    };
    this._notify();
  }

  /**
   * @param {(state: any) => void} listener
   */
  subscribe(listener) {
    this._listeners.add(listener);
    return () => this._listeners.delete(listener);
  }

  _notify() {
    for (const listener of this._listeners) {
      listener(this._state);
    }
  }
}

export const store = new Store();

