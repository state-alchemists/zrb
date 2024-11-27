function getFinalColor(finalStatus) {
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
}

function getFinalTaskStatus(taskStatus) {
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
}
