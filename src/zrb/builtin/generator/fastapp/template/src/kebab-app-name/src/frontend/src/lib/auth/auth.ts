import axios from 'axios';
import { appAuthTokenCookieKey } from '../config/config';
import { setCookie, unsetCookie } from '../cookie/cookie';

export async function login(loginUrl: string, identity: string, password: string) {
    const response = await axios.post(loginUrl, {identity, password});
    if (response && response.status == 200 && response.data && response.data.access_token) {
        setCookie(appAuthTokenCookieKey, response.data.access_token);
        return true;
    }
    return false;
}

export function logout() {
    unsetCookie(appAuthTokenCookieKey)
}
