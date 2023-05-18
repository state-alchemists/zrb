import {PUBLIC_BRAND, PUBLIC_TITLE, PUBLIC_AUTH_ACCESS_TOKEN_COOKIE_KEY, PUBLIC_AUTH_REFRESH_TOKEN_COOKIE_KEY} from '$env/static/public';
export const appBrand = PUBLIC_BRAND || 'PascalAppName';
export const appTitle = PUBLIC_TITLE || 'PascalAppName';
export const authAccessTokenCookieKey = PUBLIC_AUTH_ACCESS_TOKEN_COOKIE_KEY || 'access_token';
export const authRefreshTokenCookieKey = PUBLIC_AUTH_REFRESH_TOKEN_COOKIE_KEY || 'refresh_token';

export const loginApiUrl: string = '/api/v1/auth/login';
export const refreshTokenApiUrl: string = '/api/v1/auth/refresh-token';
export const isAuthorizedApiUrl: string = '/api/v1/auth/is-authorized';