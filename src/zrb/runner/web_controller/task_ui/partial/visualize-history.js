function visualizeHistory(allTaskStatus, finished) {
    const taskNames = Object.keys(allTaskStatus);
    const now = Date.now();

    // Set up canvas context
    const canvas = document.getElementById("history-canvas");
    canvas.height = taskNames.length * 50 + 10;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#EEE";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Calculate start and end times
    let minDateTime = null;
    let maxDateTime = null;
    for (let taskName in allTaskStatus) {
        let history = allTaskStatus[taskName].history;
        if (history.length == 0) {
            continue;
        }
        let startTime = new Date(history[0].time);
        if (minDateTime === null || minDateTime > startTime) {
            minDateTime = startTime;
        }
        let lastTime = new Date(history[history.length - 1].time);
        if (maxDateTime === null || maxDateTime < lastTime) {
            maxDateTime = lastTime;           
        }
    }
    if (minDateTime === null || maxDateTime === null) {
        return
    }
    if (!finished) {
        maxDateTime = now;
    }
    if (maxDateTime - minDateTime == 0) {
        maxDateTime.setSeconds(maxDateTime.getSeconds() + 1) 
    }
    // Canvas settings
    const chartWidth = canvas.width;
    const barHeight = 20;
    const gap = 10;
    const timeScale = (chartWidth - 200) / (maxDateTime - minDateTime);

    // Draw labels and bars
    taskNames.forEach((taskName, index) => {
        const taskHistories = allTaskStatus[taskName].history;
        if (taskHistories.length == 0) {
            return
        }
        // Get last status
        const finalStatus = getFinalTaskStatus(allTaskStatus[taskName]);
        const startDateTime = new Date(taskHistories[0].time);
        const endDateTime = getTaskEndDateTime(allTaskStatus[taskName], now);
        const startX = 100 + (startDateTime - minDateTime) * timeScale;
        const barWidth = (endDateTime - startDateTime) * timeScale;
        const startY = index * (barHeight + gap + 20) + 5;

        // Draw task label
        ctx.fillStyle = "#000";
        ctx.font = "12px Arial";
        ctx.textAlign = "right";
        ctx.fillText(taskName, 90, startY + barHeight / 1.5);

        // Draw task bar
        ctx.fillStyle = getFinalColor(finalStatus);
        ctx.fillRect(startX, startY, barWidth, barHeight);

        ctx.fillStyle = "#000";
        ctx.textAlign = "left";
        // Combine captions if time overlap
        let labels = {};
        for (let taskHistory of taskHistories) {
            let status = taskHistory.status;
            let dateTime = new Date(taskHistory.time);
            let statusStartX = 100 + (dateTime - minDateTime) * timeScale;
            if (!(statusStartX in labels)) {
                labels[statusStartX] = {dateTime: dateTime, caption: status};
            } else {
                labels[statusStartX].caption += `, ${status}`
            }
        }
        // Draw start and end time below the bar
        for (let statusStartX in labels) {
            const {dateTime, caption} = labels[statusStartX];
            const [dateStr, timeStr] = dateTime.toISOString().split("T");
            ctx.font = "10px Arial";
            ctx.fillText(caption, statusStartX, startY + 10);
            ctx.font = "8px Arial";
            ctx.fillText(dateStr, statusStartX, startY + barHeight + 10);
            ctx.fillText(timeStr, statusStartX, startY + barHeight + 20);
        }
    });
}

function getTaskEndDateTime(taskStatus, now) {
    if (taskStatus.is_completed || taskStatus.is_terminated || taskStatus.is_skipped || taskStatus.is_permanently_failed) {
        histories = taskStatus.history;
        if (histories.length > 0) {
            return new Date(histories[histories.length - 1].time);
        }
    }
    return now;
}