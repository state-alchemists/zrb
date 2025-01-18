async function updatePreviousSession(event) {
    const currentInput = event.target;
    if (currentInput.name === "CURRENT_INPUT_NAME") {
        return
    }
    const previousSessionInput = submitTaskForm.querySelector('[name="CURRENT_INPUT_NAME"]');
    if (previousSessionInput) {
        const currentSessionName = cfg.SESSION_NAME
        previousSessionInput.value = currentSessionName;
    }
}

document.getElementById("submit-task-form").querySelectorAll("input[name], textarea[name]").forEach((element) => {
    element.addEventListener("input", updatePreviousSession);
    element.addEventListener("keyup", updatePreviousSession);
});

document.getElementById("submit-task-form").querySelectorAll("select[name]").forEach((element) => {
    element.addEventListener("change", updatePreviousSession);
});

