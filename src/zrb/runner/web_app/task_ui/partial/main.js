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
    pollExistingSessions(PAGE);
});

async function pollExistingSessions() {
    while (true) {
        await getExistingSessions(PAGE);
        await delay(5000);
    }
}

async function getExistingSessions(page) {
    PAGE=page
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
        showExistingSession(page, total, data);
        console.log("Success:", data);
    } catch (error) {
        console.error("Error:", error);
    }
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
