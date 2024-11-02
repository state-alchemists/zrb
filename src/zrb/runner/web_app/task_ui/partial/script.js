const CURRENT_URL = rstripSlash(window.location.href);

window.addEventListener("load", async function() {
    if (SESSION_NAME != "") {
        pollSession();
    }
});


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
        history.pushState(null, "", `${CURRENT_URL}/${SESSION_NAME}`);
        await pollSession();
    } catch (error) {
        console.error("Error:", error);
    }
}


async function pollSession() {
    const logTextArea = document.getElementById("log-textarea");
    let isFinished = false;
    while (!isFinished) {
        try {
            const data = await getSession();
            logTextArea.value = JSON.stringify(data, null, 2);
            if (data.finished) {
                isFinished = true;
            } else {
                await delay(500); // 2 seconds delay
            }
        } catch (error) {
            console.error("Error fetching session status:", error);
            break;
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
