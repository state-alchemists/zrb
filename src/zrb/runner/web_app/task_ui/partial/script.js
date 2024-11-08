window.addEventListener("load", async function () {
    // set maxStartDate to today
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);  // Move to the next day
    tomorrow.setHours(0, 0, 0, 0);
    const formattedTomorrow = formatLocalDate(tomorrow);
    const maxStartAtInput = document.getElementById("max-start-at-input");
    maxStartAtInput.value = formattedTomorrow;
    // set minStartDate to yesterday
    const today = new Date();
    today.setHours(0, 0, 0, 0);  // Set time to 00:00:00
    const formattedToday = formatLocalDate(today);
    const minStartAtInput = document.getElementById("min-start-at-input");
    minStartAtInput.value = formattedToday;
    if (SESSION_NAME != "") {
        pollSession();
    }
});

function formatLocalDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');  // Months are 0-indexed
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function openDialog(event) {
    event.preventDefault();
    const dialog = document.getElementById("session-history-dialog")
    dialog.showModal();
}


function closeDialog(event) {
    event.preventDefault();
    const dialog = document.getElementById("session-history-dialog")
    dialog.close();
}


async function submitForm(event) {
    // Prevent the form from submitting the traditional way
    event.preventDefault();
    // Select the form
    const form = document.getElementById("submit-task-form");
    // Initialize an empty object to hold form data
    const formData = {};
    // Iterate through each input in the form
    Array.from(form.elements).forEach(element => {
        // Only include inputs with a name attribute and ignore buttons
        if (element.name && (element.type !== "button" && element.type !== "submit")) {
            formData[element.name] = element.value;
        }
    });
    // Convert formData to JSON
    const jsonData = JSON.stringify(formData);
    try {
        // Send the AJAX request
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: jsonData
        });
        const data = await response.json();
        console.log("Success:", data);
        SESSION_NAME = data.session_name;
        history.pushState(null, "", `${CURRENT_URL}${SESSION_NAME}`);
        await pollSession();
    } catch (error) {
        console.error("Error:", error);
    }
}


async function pollSession() {
    const resultTextarea = document.getElementById("result-textarea");
    const logTextarea = document.getElementById("log-textarea");
    const submitTaskForm = document.getElementById("submit-task-form");
    let isFinished = false;
    let errorCount = 0;
    while (!isFinished) {
        try {
            const data = await getSession();
            // update inputs
            const dataInputs = data.input;
            for (const inputName in dataInputs) {
                const inputValue = dataInputs[inputName];
                const input = submitTaskForm.querySelector(`[name="${inputName}"]`);
                input.value = inputValue;
            }
            resultLineCount = data.final_result.split("\n").length;
            resultTextarea.rows = resultLineCount <= 5 ? resultLineCount : 5;
            // update text areas
            resultTextarea.value = data.final_result;
            logTextarea.value = data.log.join("\n");
            logTextarea.scrollTop = logTextarea.scrollHeight;
            // visualize history
            visualizeHistory(data.task_status, data.finished);
            if (data.finished) {
                isFinished = true;
            } else {
                await delay(200);
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
}


async function getSession() {
    try {
        const response = await fetch(`${API_URL}${SESSION_NAME}`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json"
            },
        });
        return await response.json();
    } catch (error) {
        console.error("Error:", error);
    }
}


function rstripSlash(str) {
    return str.replace(/\/+$/, "");  // Removes one or more trailing slashes
}


function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}


function visualizeHistory(taskStatus, finished) {
    const taskNames = Object.keys(taskStatus);
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
    for (let taskName in taskStatus) {
        let history = taskStatus[taskName].history;
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
        const taskHistories = taskStatus[taskName].history;
        if (taskHistories.length == 0) {
            return
        }
        // Get last status
        const finalStatus = getTaskFinalStatus(taskHistories, now);
        const startDateTime = new Date(taskHistories[0].time);
        const endDateTime = getTaskEndDateTime(taskHistories, finalStatus, now);
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

function getTaskEndDateTime(taskHistories, finalStatus, now) {
    if (finalStatus != "completed") {
        return now;
    }
    return new Date(taskHistories[taskHistories.length - 1].time);
}


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
        default:
            return "#ffffff";
    } 
}


function getTaskFinalStatus(taskHistories, now) {
    let finalStatus = taskHistories[taskHistories.length - 1].status;
    // If it was 'completed", then make it "completed"
    for (let history of taskHistories) {
        if (history.status == "completed") {
            finalStatus = "completed";
            break
        }
    }
    return finalStatus;
}