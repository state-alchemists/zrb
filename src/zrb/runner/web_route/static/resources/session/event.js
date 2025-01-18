window.addEventListener("load", async function () {
    // Get current session
    if (cfg.SESSION_NAME != "") {
        CURRENT_SESSION.startPolling();
    }
    // set maxStartDate to today
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);  // Move to the next day
    tomorrow.setHours(0, 0, 0, 0);
    const formattedTomorrow = UTIL.toLocalDateInputValue(tomorrow);
    const maxStartAtInput = document.getElementById("max-start-at-input");
    maxStartAtInput.value = formattedTomorrow;
    // set minStartDate to yesterday
    const today = new Date();
    today.setHours(0, 0, 0, 0);  // Set time to 00:00:00
    const formattedToday = UTIL.toLocalDateInputValue(today);
    const minStartAtInput = document.getElementById("min-start-at-input");
    minStartAtInput.value = formattedToday;
});


const submitTaskForm = document.getElementById("submit-task-form");
async function handleInputUpdate(event) {
    const currentInput = event.target;
    const inputs = Array.from(submitTaskForm.querySelectorAll("input[name], textarea[name], select[name]"));
    const inputMap = {};
    const fixedInputNames = [];
    for (const input of inputs) {
        fixedInputNames.push(input.name);
        if (input === currentInput) {
            inputMap[input.name] = currentInput.value;
            break;
        } else {
            inputMap[input.name] = input.value;
        }
    }
    const queryString = new URLSearchParams(
        {query: JSON.stringify(inputMap)}
    ).toString();
    try {
        // Send the AJAX request
        const response = await fetch(`${cfg.INPUT_API_URL}?${queryString}`, {
            method: "GET",
            headers: {
                "Content-Type": "application/json"
            },
        });
        if (response.ok) {
            const data = await response.json();
            // Update the values of all subsequent inputs based on the response
            Object.entries(data).forEach(([key, value]) => {
                if (fixedInputNames.includes(key)) {
                    return;
                }
                const input = submitTaskForm.querySelector(`[name="${key}"]`);
                if (input === currentInput) {
                    return;
                }
                if (value === "") {
                    return;
                }
                console.log(input, data);
                input.value = value;
            });
        } else {
            console.error("Failed to fetch updated values:", response.statusText);
        }
    } catch (error) {
        console.error("Error during fetch:", error);
    }
}

submitTaskForm.querySelectorAll("input[name], textarea[name]").forEach((element) => {
    element.addEventListener("input", handleInputUpdate);
    element.addEventListener("keyup", handleInputUpdate);
});
submitTaskForm.querySelectorAll("select[name]").forEach((element) => {
    element.addEventListener("change", handleInputUpdate);
});


function openPastSessionDialog(event) {
    event.preventDefault();
    PAST_SESSION.startPolling();
    const dialog = document.getElementById("past-session-dialog")
    dialog.showModal();
}


function closePastSessionDialog(event) {
    event.preventDefault();
    PAST_SESSION.stopPolling();
    const dialog = document.getElementById("past-session-dialog")
    dialog.close();
}


async function submitNewSessionForm(event) {
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
        const response = await fetch(cfg.SESSION_API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: jsonData
        });
        if (response.ok) {
            const data = await response.json();
            cfg.SESSION_NAME = data.session_name;
            history.pushState(null, "", `${cfg.CURRENT_URL}${cfg.SESSION_NAME}`);
            await CURRENT_SESSION.startPolling();
        } else {
            console.error("Error:", response);
        }
    } catch (error) {
        console.error("Error:", error);
    }
}
