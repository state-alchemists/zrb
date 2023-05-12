import {PUBLIC_BRAND, PUBLIC_TITLE, PUBLIC_AUTH_TOKEN_COOKIE_KEY} from '$env/static/public';
export const appBrand = PUBLIC_BRAND || 'PascalAppName';
export const appTitle = PUBLIC_TITLE || 'PascalAppName';
export const appAuthTokenCookieKey = PUBLIC_AUTH_TOKEN_COOKIE_KEY || 'auth_token';