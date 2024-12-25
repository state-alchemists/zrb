async function login(event) {
    event.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorMessage = document.getElementById('error-message');

    try {
        const response = await fetch('/api/v1/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({
                'username': username,
                'password': password,
            }),
        });

        if (response.ok) {
            const data = await response.json();
            console.log('Login successful', data);
            // Redirect to home page or dashboard
            window.location.href = '/';
        } else {
            const errorData = await response.json();
            errorMessage.textContent = errorData.detail || 'Login failed. Please try again.';
        }
    } catch (error) {
        console.error('Error:', error);
        errorMessage.textContent = 'An error occurred. Please try again.';
    }
}