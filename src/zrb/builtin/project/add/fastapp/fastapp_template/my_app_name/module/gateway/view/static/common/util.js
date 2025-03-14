const UTIL = {
    refreshUrl: "/api/v1/user-sessions",
    refreshInProgress: null, // Holds the ongoing refresh request

    unsetAccessTokenExpiredAt() {
        localStorage.removeItem("access-token-expired-at");
    },

    setAccessTokenExpiredAt(expiredAt) {
        localStorage.setItem("access-token-expired-at", expiredAt);
    },

    getAccessTokenExpiredAt() {
        return localStorage.getItem("access-token-expired-at");
    },

    isAccessTokenExpired() {
        const timestamp = new Date(this.getAccessTokenExpiredAt()).getTime();
        // If expiredAt is not a valid date, timestamp will be NaN
        if (isNaN(timestamp)) {
            return true; // Consider it expired
        }
        return timestamp <= Date.now();
    },

    async fetchAPI(input, options = {}) {
        if (this.isAccessTokenExpired()) {
            await this.refreshAccessToken();
        }
        options.credentials ??= "include";
        options.headers ??= {"Content-Type": "application/json"};
        const response = await fetch(input, options);
        if (!response.ok) {
            const responseBody = await this._extractResponseBody(response);
            const errorMessage = this._extractErrorMessage(responseBody);
            if (errorMessage != null) {
                throw new Error(errorMessage);
            }
            throw new Error(`HTTP Error: ${response.status}`);
        }
        return await response.json();
    },

    async _extractResponseBody(response) {
        try {
            return await response.json();
        } catch(error) {
            return null;
        }
    },

    _extractErrorMessage(responseBody) {
        if (typeof responseBody === "string") {
            return responseBody;
        }
        if (Array.isArray(responseBody)) {
            return responseBody.map((r => this._extractErrorMessage(r))).join("\n");
        }
        if (responseBody.message) {
            return responseBody.message;
        }
        if (responseBody.msg) {
            return responseBody.msg;
        }
        if (responseBody.detail) {
            return this._extractErrorMessage(responseBody.detail);
        }
        return null;
    },

    async refreshAccessToken() {
        if (this.refreshInProgress) {
            return this.refreshInProgress; // Return the ongoing promise if already refreshing
        }
        this.refreshInProgress = (async () => {
            try {
                const response = await fetch(this.refreshUrl, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    credentials: "include", // Include cookies in the request
                });
                if (!response.ok) {
                    if (response.status === 401 || response.status === 403) {
                        console.warn("Skipping token refresh, authentication required.");
                        throw new Error("Authentication required");
                    }
                    throw new Error(`HTTP Error: ${response.status}`);
                }
                const result = await response.json();
                // Assume API return UTC + 0
                this.setAccessTokenExpiredAt(result.access_token_expired_at + "Z");
                console.log("Token refreshed successfully");
            } catch (error) {
                console.error("Cannot refresh token", error);
                throw error;
            } finally {
                this.refreshInProgress = null; // Reset flag after completion
            }
        })();
        return this.refreshInProgress;
    },

    async refreshAccessTokenPeriodically(refreshAccessTokenIntervalSeconds) {
        let shouldRefresh = true;
        while (shouldRefresh) {
            await new Promise(resolve => setTimeout(resolve, refreshAccessTokenIntervalSeconds * 1000));
            try {
                await this.refreshAccessToken();
            } catch (error) {
                if (error.message === "Authentication required") {
                    shouldRefresh = false; // Stop refreshing if authentication is required
                }
            }
        }
    },

    setFormData(form, data) {
        for (const key in data) {
            const element = form.querySelector(`[name="${key}"]`);
            if (!element) {
                continue;
            }
            const value = data[key];
            // Handle checkboxes and radio buttons
            if (element.type === 'checkbox' || element.type === 'radio') {
                const elements = form.querySelectorAll(`[name="${key}"]`);
                elements.forEach(el => {
                    // If value is an array, check if this option is included;
                    // otherwise compare to a single value.
                    if (Array.isArray(value)) {
                        el.checked = value.includes(el.value);
                    } else {
                        el.checked = (value === true) || (el.value == value);
                    }
                });
            }
            // Handle select elements
            else if (element.tagName === "SELECT") {
                if (element.multiple && Array.isArray(value)) {
                    // For multi-select, mark options as selected if their value is in the array.
                    Array.from(element.options).forEach(option => {
                        option.selected = value.includes(option.value);
                    });
                } else {
                    element.value = value;
                }
            }
            // Handle all other inputs (including textarea)
            else {
                element.value = value;
            }
        }
    },

    clearFormData(form) {
        const elements = form.querySelectorAll("input, textarea, select");
        elements.forEach(element => {
            if (element.type === "checkbox" || element.type === "radio") {
                element.checked = element.defaultChecked; // Restore default checked state
            } else if (element.tagName === "SELECT") {
                if (element.multiple) {
                    // Deselect all options for multi-select.
                    Array.from(element.options).forEach(option => option.selected = false);
                } else {
                    // Select the first option by default
                    element.selectedIndex = 0;
                }
            } else {
                element.value = element.defaultValue || ""; // Reset to default value or empty
            }
        });
    },


    getFormData(form) {
        const formData = new FormData(form);
        const data = {};
        // Populate data from FormData (this covers inputs, textareas, selects, and checked radio buttons)
        for (const [key, value] of formData.entries()) {
            // If key already exists, it’s part of a multi-value field.
            if (key in data) {
                if (!Array.isArray(data[key])) {
                    data[key] = [data[key]];
                }
                data[key].push(value);
            } else {
                data[key] = value;
            }
        }
        // Process all checkbox inputs.
        const checkboxes = form.querySelectorAll("input[type='checkbox']");
        // Use a Set to iterate over unique checkbox names.
        const checkboxNames = new Set();
        checkboxes.forEach(el => checkboxNames.add(el.name));
        checkboxNames.forEach(name => {
            const elems = form.querySelectorAll(`input[type='checkbox'][name="${name}"]`);
            if (elems.length === 1) {
                // Unique checkbox: convert its presence in formData to a boolean.
                // If it wasn’t included by FormData (because it was unchecked), default to false.
                data[name] = elems[0].checked;
            } else {
                // Multiple checkboxes: ensure the value is an array.
                // If none of the checkboxes were checked, ensure an empty array is returned.
                if (!(name in data)) {
                    data[name] = [];
                } else if (!Array.isArray(data[name])) {
                    // This case can happen if only one checkbox in the group was checked.
                    data[name] = [data[name]];
                }
            }
        });
        return data;
    },

    tryParseJSON(value) {
        try {
            return JSON.parse(value);
        } catch {
            return value;
        }
    },

};
