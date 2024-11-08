window.addEventListener("load", async function () {
    // Get current session
    if (SESSION_NAME != "") {
        pollSession();
    }
    // set maxStartDate to today
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);  // Move to the next day
    tomorrow.setHours(0, 0, 0, 0);
    const formattedTomorrow = toLocalDateInputValue(tomorrow);
    const maxStartAtInput = document.getElementById("max-start-at-input");
    maxStartAtInput.value = formattedTomorrow;
    // set minStartDate to yesterday
    const today = new Date();
    today.setHours(0, 0, 0, 0);  // Set time to 00:00:00
    const formattedToday = toLocalDateInputValue(today);
    const minStartAtInput = document.getElementById("min-start-at-input");
    minStartAtInput.value = formattedToday;
    // Update session
    getExistingSessions(0);
});


async function getExistingSessions(page) {
    const minStartAtInput = document.getElementById("min-start-at-input");
    const minStartAt = formatDate(minStartAtInput.value);
    const maxStartAtInput = document.getElementById("max-start-at-input");
    const maxStartAt = formatDate(maxStartAtInput.value);
    console.log(minStartAt);
    const queryString = new URLSearchParams({
        page: page,
        from: minStartAt,
        to: maxStartAt,
    }).toString();
    try {
        // Send the AJAX request
        const response = await fetch(`${API_URL}list?${queryString}`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json"
            },
        });
        const {total, data} = await response.json();
        const ul = document.getElementById("session-history-ul");
        ul.innerHTML = '';  // Clear existing content
        data.forEach(item => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.textContent = `${item.name} - ${item.start_time}`;
            a.target = '_blank';
            a.href = `${UI_URL}${item.name}`;
            li.appendChild(a);
            ul.appendChild(li);
        }); 
        const paginationUl = document.getElementById("session-history-pagination-ul");
        paginationUl.innerHTML = '';  // Clear previous pagination

        const totalPages = Math.ceil(total / 10);  // Calculate total pages based on page size
        const maxPagesToShow = 5;  // Number of pages to display around the current page
        const halfMaxPages = Math.floor(maxPagesToShow / 2);
        
        // Add first page and previous controls
        if (page > 0) {
            paginationUl.appendChild(createPageLink("⟪", 0));  // Go to first page
            paginationUl.appendChild(createPageLink("⟨", page - 1));  // Go to previous page
        }

        let startPage = Math.max(0, page - halfMaxPages);
        let endPage = Math.min(totalPages - 1, page + halfMaxPages);

        if (page <= halfMaxPages) {
            endPage = Math.min(totalPages - 1, maxPagesToShow - 1);
        } else if (page + halfMaxPages >= totalPages) {
            startPage = Math.max(0, totalPages - maxPagesToShow);
        }

        if (startPage > 1) {
            paginationUl.appendChild(createEllipsis());
        }

        // Add page links within the calculated range
        for (let i = startPage; i <= endPage; i++) {
            if (i === page) {
                const pageLi = document.createElement('li');
                pageLi.textContent = i + 1;
                paginationUl.append(pageLi)
            } else {
                paginationUl.appendChild(createPageLink(i + 1, i))
            }
        }

        // Add ellipsis after the end page if needed
        if (endPage < totalPages - 2) {
            paginationUl.appendChild(createEllipsis());
        }

        // Add next and last page controls
        if (page < totalPages - 1) {
            paginationUl.appendChild(createPageLink("⟩", page + 1));  // Go to next page
            paginationUl.appendChild(createPageLink("⟫", totalPages - 1));  // Go to last page
        }

        console.log("Success:", data);
    } catch (error) {
        console.error("Error:", error);
    }
}


function createPageLink(text, page) {
    const li = document.createElement('li');
    const link = document.createElement('a');
    link.textContent = text;
    link.href = '#';
    link.onclick = (e) => {
        e.preventDefault();
        getExistingSessions(page);
    };
    li.appendChild(link);
    return li;
}

function createEllipsis() {
    const li = document.createElement('li');
    li.textContent = '...';
    return li;
}


function toLocalDateInputValue(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');  // Months are 0-indexed
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}


function formatDate(dateString) {
    const date = new Date(dateString);
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
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
        getExistingSessions(0);
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