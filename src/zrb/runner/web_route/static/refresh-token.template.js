function refreshAuthToken(){
    const refreshUrl = "/api/v1/refresh-token";
    async function refresh() {
        try {
            const response = await fetch(refreshUrl, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include", // Include cookies in the request
            });

            if (!response.ok) {
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