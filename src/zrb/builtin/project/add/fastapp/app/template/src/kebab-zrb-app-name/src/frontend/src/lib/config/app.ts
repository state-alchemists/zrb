import axios from 'axios';

export const loginApiUrl: string = '/api/v1/auth/login';
export const refreshTokenApiUrl: string = '/api/v1/auth/refresh-token';
export const isAuthorizedApiUrl: string = '/api/v1/auth/is-authorized';
export const configApiUrl: string = '/api/v1/frontend/configs';

export async function getBrand(): Promise<string> {
    return await getConfig('brand');
}

export async function getTitle(): Promise<string> {
    return await getConfig('title');
}

export async function getAccessTokenCookieKey(): Promise<string> {
    return await getConfig('accessTokenCookieKey');
}

export async function getRefreshTokenCookieKey(): Promise<string> {
    return await getConfig('refreshTokenCookieKey');
}

async function getConfig(key: string): Promise<string> {
    const cachedValue = localStorage.getItem(`config.${key}`);
    if (cachedValue) {
        return cachedValue;
    }
    const config = await getConfigFromServer()
    localStorage.setItem(`config.brand`, config.brand);
    localStorage.setItem(`config.title`, config.title);
    localStorage.setItem(`config.accessTokenCookieKey`, config.access_token_cookie_key);
    localStorage.setItem(`config.refreshTokenCookieKey`, config.refresh_token_cookie_key);
    const value = localStorage.getItem(`config.${key}`);
    return value? value : '';
}


async function getConfigFromServer(): Promise<{[key: string]: string}> {
    const response = await axios.get(configApiUrl);
    if (response && response.status == 200 && response.data) {
        return response.data;
    }
    throw(Error('Cannot fetch config from server'));
}