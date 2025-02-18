const UTIL = {
    async refreshAuthToken(refreshSessionIntervalSeconds){
        const refreshUrl = "/api/v1/user-sessions";
        let shouldRefresh = true;
        async function refresh() {
            while (shouldRefresh) {
                await new Promise(resolve => setTimeout(resolve, refreshSessionIntervalSeconds * 1000));
                try {
                    const response = await fetch(refreshUrl, {
                        method: "PUT",
                        headers: { "Content-Type": "application/json" },
                        credentials: "include", // Include cookies in the request
                    });

                    if (!response.ok) {
                        if (response.status === 401 || response.status === 403) {
                            console.warn("Skipping token refresh, authentication required.");
                            shouldRefresh = false;
                            return;
                        }
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    console.log("Token refreshed successfully");
                } catch (error) {
                    console.error("Cannot refresh token", error)
                }
            }
        }
        await refresh();
    },
}