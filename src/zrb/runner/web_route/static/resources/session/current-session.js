const CURRENT_SESSION = {
    async startPolling() {
        const resultTextarea = document.getElementById("result-textarea");
        const logTextarea = document.getElementById("log-textarea");
        const submitTaskForm = document.getElementById("submit-task-form");
        let isFinished = false;
        let isInputUpdated = false;
        let errorCount = 0;
        while (!isFinished) {
            try {
                const data = await this.getCurrentSession();
                // update inputs
                if (!isInputUpdated) {
                    const dataInputs = data.input;
                    for (const inputName in dataInputs) {
                        const inputValue = dataInputs[inputName];
                        const input = submitTaskForm.querySelector(`[name="${inputName}"]`);
                        if (input) {
                            input.value = inputValue;
                        }
                    }
                    isInputUpdated = true;
                }
                resultLineCount = data.final_result.split("\n").length;
                resultTextarea.rows = resultLineCount <= 5 ? resultLineCount : 5;
                // update text areas
                resultTextarea.value = data.final_result;
                logTextarea.value = data.log.join("");
                // logTextarea.scrollTop = logTextarea.scrollHeight;
                // visualize history
                this.showCurrentSession(data.task_status, data.finished);
                if (data.finished) {
                    isFinished = true;
                } else {
                    await UTIL.delay(200);
                }
            } catch (error) {
                console.error("Error fetching session status:", error);
                errorCount++;
                if (errorCount > 5) {
                    console.error("Exceeding maximum error count, quitting");
                    return;
                }
                continue;
            }
        }
    },


    async getCurrentSession() {
        try {
            const response = await fetch(`${cfg.SESSION_API_URL}${cfg.SESSION_NAME}`, {
                method: "GET",
                headers: {
                    "Content-Type": "application/json"
                },
            });
            return await response.json();
        } catch (error) {
            console.error("Error:", error);
        }
    },


    showCurrentSession(allTaskStatus, finished) {
        const taskNames = Object.keys(allTaskStatus);
        const now = Date.now();
        const barHeight = 30;
        const gap = 40;

        // Set up canvas context
        const canvas = document.getElementById("history-canvas");
        canvas.height = taskNames.length * (barHeight + gap) + 10;
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = "#EEE";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.textBaseline = "top";
        ctx.imageSmoothingEnabled = true;

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
        const timeScale = (chartWidth - 200) / (maxDateTime - minDateTime);

        // Draw labels and bars
        taskNames.forEach((taskName, index) => {
            const taskHistories = allTaskStatus[taskName].history;
            if (taskHistories.length == 0) {
                return
            }
            // Get last status
            const finalStatus = UTIL.getFinalTaskStatus(allTaskStatus[taskName]);
            const startDateTime = new Date(taskHistories[0].time);
            const endDateTime = this.getTaskEndDateTime(allTaskStatus[taskName], now);
            const startX = 100 + (startDateTime - minDateTime) * timeScale;
            const barWidth = (endDateTime - startDateTime) * timeScale;
            const startY = index * (barHeight + gap) + 5;

            // Draw task label
            ctx.fillStyle = "#000";
            ctx.font = "10px Arial";
            ctx.textAlign = "right";
            ctx.fillText(taskName, 90, startY + barHeight - 0.5 * barHeight);

            // Draw task bar
            ctx.fillStyle = UTIL.getFinalColor(finalStatus);
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
            let sortedStartX = Object.keys(labels).sort((a, b) => a - b);
            let offsetY = 0;
            for (let statusStartX of sortedStartX) {
                const {dateTime, caption} = labels[statusStartX];
                const timeStr = dateTime.toISOString().split("T")[1].split(".")[0];
                ctx.font = "10px Arial";
                ctx.fillText(caption, statusStartX, startY + offsetY);
                ctx.font = "10px Arial";
                ctx.fillText(timeStr, statusStartX, startY + barHeight + offsetY);
                offsetY += 10
                if (offsetY >= barHeight) {
                    offsetY = 0;
                }
            }
        });
    },


    getTaskEndDateTime(taskStatus, now) {
        if (taskStatus.is_completed || taskStatus.is_terminated || taskStatus.is_skipped || taskStatus.is_permanently_failed) {
            histories = taskStatus.history;
            if (histories.length > 0) {
                return new Date(histories[histories.length - 1].time);
            }
        }
        return now;
    }
}