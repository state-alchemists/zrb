window.addEventListener("load", async function () {
    // Get current session
    if (cfg.SESSION_NAME != "") {
        pollCurrentSession();
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
    // Update session
    pollPastSession();
});


function openPastSessionDialog(event) {
    event.preventDefault();
    const dialog = document.getElementById("past-session-dialog")
    dialog.showModal();
}


function closePastSessionDialog(event) {
    event.preventDefault();
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
        const response = await fetch(cfg.API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: jsonData
        });
        const data = await response.json();
        console.log("Success:", data);
        cfg.SESSION_NAME = data.session_name;
        history.pushState(null, "", `${cfg.CURRENT_URL}${cfg.SESSION_NAME}`);
        getAndRenderPastSession(0);
        await pollCurrentSession();
    } catch (error) {
        console.error("Error:", error);
    }
}
