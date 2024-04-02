import axios from 'axios';

export function getErrorMessage(error: unknown): string {
    if (axios.isAxiosError(error)) {
        let errorMessage = error.message;
        if (error.response?.data?.detail) {
            errorMessage += JSON.stringify(error.response.data.detail);
        }
        return errorMessage;
    }
    return error + '';
}