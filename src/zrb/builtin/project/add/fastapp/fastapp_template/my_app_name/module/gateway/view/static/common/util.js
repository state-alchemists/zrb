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
            // Only search within this form for an element with the matching name
            const element = form.querySelector(`[name="${key}"]`);
            if (element) {
                // For checkboxes or radio buttons, update each matching element within the form
                if (element.type === 'checkbox' || element.type === 'radio') {
                    const elements = form.querySelectorAll(`[name="${key}"]`);
                    elements.forEach(el => {
                        el.checked = (el.value === data[key]);
                    });
                } else {
                    // For other types of inputs, selects, and textareas, simply set the value
                    element.value = data[key];
                }
            }
        }
    },

    clearFormData(form) {
        const elements = form.querySelectorAll("input, textarea, select");
        elements.forEach(element => {
            if (element.type === "checkbox" || element.type === "radio") {
                element.checked = element.defaultChecked; // Restore default checked state
            } else if (element.tagName === "SELECT") {
                element.selectedIndex = 0; // Select the first option by default
            } else {
                element.value = element.defaultValue || ""; // Reset to default value or empty
            }
        });
    },


    getFormData(form) {
        const formData = new FormData(form);
        const data = {};
        // Convert FormData to a plain object
        formData.forEach((value, key) => {
            data[key] = value;
        });
        return data;
    },

};
