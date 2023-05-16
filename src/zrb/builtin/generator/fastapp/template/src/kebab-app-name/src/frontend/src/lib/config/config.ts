import {PUBLIC_BRAND, PUBLIC_TITLE, PUBLIC_AUTH_TOKEN_COOKIE_KEY, PUBLIC_AUTH_REFRESH_TOKEN_SECONDS} from '$env/static/public';
export const appBrand = PUBLIC_BRAND || 'PascalAppName';
export const appTitle = PUBLIC_TITLE || 'PascalAppName';
export const appAuthTokenCookieKey = PUBLIC_AUTH_TOKEN_COOKIE_KEY || 'auth_token';
export const appRefreshTokenSeconds = parseInt(PUBLIC_AUTH_REFRESH_TOKEN_SECONDS || '0');

export const loginApiUrl: string = '/api/v1/auth/login';
export const refreshTokenApiUrl: string = '/api/v1/auth/refresh-token';
export const isAuthorizedApiUrl: string = '/api/v1/auth/is-authorized';