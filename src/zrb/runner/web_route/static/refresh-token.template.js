function refreshAuthToken(){
    const refreshUrl = "/api/v1/refresh-token";
    let shouldRefresh = true;
    async function refresh() {
        if (!shouldRefresh) {
            return;
        }
        try {
            const response = await fetch(refreshUrl, {
                method: "POST",
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
    setInterval(refresh, refreshIntervalSeconds * 1000);
    refresh();
}
refreshAuthToken();