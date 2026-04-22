let _ganttRenderCount = 0;

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
                const resultLineCount = data.final_result.split("\n").length;
                resultTextarea.rows = resultLineCount <= 5 ? resultLineCount : 5;
                resultTextarea.value = data.final_result;
                logTextarea.value = data.log.join("");
                await this.showCurrentSession(data.task_status, data.finished);
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
            }
        }
    },

    async getCurrentSession() {
        const response = await fetch(`${cfg.SESSION_API_URL}${cfg.SESSION_NAME}`, {
            method: "GET",
            headers: { "Content-Type": "application/json" },
        });
        return await response.json();
    },

    async showCurrentSession(allTaskStatus, finished) {
        const ganttDiv = document.getElementById("history-gantt");
        if (!ganttDiv) return;
        if (typeof mermaid === "undefined") return;
        const definition = this.buildGanttDefinition(allTaskStatus, finished);
        if (!definition) return;
        try {
            _ganttRenderCount++;
            const { svg } = await mermaid.render(`gantt-${_ganttRenderCount}`, definition);
            ganttDiv.innerHTML = svg;
        } catch (e) {
            console.error("Mermaid render error:", e);
        }
    },

    buildGanttDefinition(allTaskStatus, finished) {
        const now = Date.now();
        const taskNames = Object.keys(allTaskStatus).filter(
            name => allTaskStatus[name].history.length > 0
        );
        if (taskNames.length === 0) return null;

        const lines = [
            "gantt",
            "    dateFormat x",
            "    axisFormat %H:%M:%S",
            "    section Tasks",
        ];

        for (const taskName of taskNames) {
            const taskStatus = allTaskStatus[taskName];
            const startTime = new Date(taskStatus.history[0].time).getTime();
            const endTime = Math.max(
                startTime + 1,
                this.getTaskEndDateTime(taskStatus, now).getTime()
            );
            const finalStatus = UTIL.getFinalTaskStatus(taskStatus);
            let mermaidStatus;
            if (finalStatus === "completed" || finalStatus === "skipped") {
                mermaidStatus = "done, ";
            } else if (finalStatus === "failed" || finalStatus === "permanently-failed") {
                mermaidStatus = "crit, ";
            } else {
                mermaidStatus = "active, ";
            }
            const safeLabel = taskName.replace(/[:#;,]/g, "-");
            lines.push(`    ${safeLabel} :${mermaidStatus}${startTime}, ${endTime}`);
        }

        return lines.join("\n");
    },

    getTaskEndDateTime(taskStatus, now) {
        if (
            taskStatus.is_completed ||
            taskStatus.is_terminated ||
            taskStatus.is_skipped ||
            taskStatus.is_permanently_failed
        ) {
            const histories = taskStatus.history;
            if (histories.length > 0) {
                return new Date(histories[histories.length - 1].time);
            }
        }
        return new Date(now);
    },
};
