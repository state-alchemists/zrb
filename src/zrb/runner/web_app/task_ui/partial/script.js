window.addEventListener("load", function() {
    console.log("Wohoo")
});


function submitForm(event, apiUrl) {
    // Prevent the form from submitting the traditional way
    event.preventDefault();
    // Select the form
    const form = document.getElementById('submit-task-form');
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
    // Send the AJAX request
    fetch(apiUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: jsonData
    }).then(
        response => response.json()
    ).then(data => {
        console.log('Success:', data);
        const sessionId = data.session_id;
        modifyUrl(`/${sessionId}`);
    }).catch((error) => {
        console.error('Error:', error);
    });
}


function modifyUrl(suffix) {
    // Get the current URL
    const currentURL = rstripSlash(window.location.href);
    // Update the URL in the address bar
    history.pushState(null, '', currentURL + suffix);
}


function rstripSlash(str) {
    return str.replace(/\/+$/, '');  // Removes one or more trailing slashes
}