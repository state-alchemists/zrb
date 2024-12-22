async function logout() {
    try {
        const response = await fetch('/api/v1/logout', {
            method: 'GET',
            credentials: 'same-origin' // This is important for including cookies in the request
        });

        if (response.ok) {
            // If logout was successful, redirect to the home page
            window.location.href = '/';
        } else {
            // If there was an error, log it and alert the user
            console.error('Logout failed');
            alert('Logout failed. Please try again.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred during logout. Please try again.');
    }
}