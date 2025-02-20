const UTIL = {
    refreshUrl: "/api/v1/user-sessions",
    refreshInProgress: null, // Holds the ongoing refresh request

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
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }

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

    async refreshAccessTokenPeriodically(refreshSessionIntervalSeconds) {
        let shouldRefresh = true;

        while (shouldRefresh) {
            await new Promise(resolve => setTimeout(resolve, refreshSessionIntervalSeconds * 1000));

            try {
                await this.refreshAccessToken();
            } catch (error) {
                if (error.message === "Authentication required") {
                    shouldRefresh = false; // Stop refreshing if authentication is required
                }
            }
        }
    },
};
