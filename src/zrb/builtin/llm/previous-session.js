let hasUpdateCurrentPascalInputName = false;
document.getElementById("submit-task-form").addEventListener("change", async function(event) {
    const currentInput = event.target;
    if (hasUpdateCurrentPascalInputName || currentInput.name === "CURRENT_INPUT_NAME") {
        return
    }
    const previousSessionInput = submitTaskForm.querySelector('[name="CURRENT_INPUT_NAME"]');
    if (previousSessionInput) {
        const currentSessionName = cfg.SESSION_NAME
        previousSessionInput.value = currentSessionName;
    }
    hasUpdateCurrentPascalInputName = true;
});
