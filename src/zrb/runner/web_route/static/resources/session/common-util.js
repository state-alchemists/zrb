const UTIL = {
    toLocalDateInputValue(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');  // Months are 0-indexed
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    },

    formatDate(dateString) {
        const date = new Date(dateString);
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');
        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    },

    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },

    getFinalColor(finalStatus) {
        switch(finalStatus) {
            case "started":
                return "#3498db";
            case "ready":
                return "#f39c12";
            case "completed":
                return "#2ecc71";
            case "skipped":
                return "#95a5a6";
            case "failed":
                return "#e74c3c";
            case "permanently-failed":
                return "#c0392b";
            case "terminated":
                return "#ffffff";
            default:
                return "#ffffff";
        } 
    },

    getFinalTaskStatus(taskStatus) {
        if (taskStatus.is_completed) {
            return "completed";
        }
        if (taskStatus.is_terminated) {
            return "terminated"
        }
        if (taskStatus.is_permanently_failed) {
            return "permanently-failed"
        }
        const histories = taskStatus.history;
        if (histories.length > 0) {
            return histories[histories.length - 1].status;
        }
        return "";
    },
}