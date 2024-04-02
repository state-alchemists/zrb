import axios from 'axios';
import jwt_decode from 'jwt-decode';
import { getAccessTokenCookieKey, getRefreshTokenCookieKey, isAuthorizedApiUrl, loginApiUrl, refreshTokenApiUrl } from '../config/app';
import { userIdStore, userNameStore } from './store';
import type { AccessTokenData } from './type';
import Cookies from 'js-cookie';


export async function getAuthorization(permissions: string[]): Promise<{[key: string]: boolean}> {
    try {
        const accessToken = await ensureAccessToken();
        if (accessToken == '') {
            return {};
        }
        const response = await axios.post(
            isAuthorizedApiUrl,
            {permission_names: permissions},
            {
                headers: { Authorization: `Bearer ${accessToken}` }
            }
        );
        if (response && response.status == 200 && response.data) {
            return response.data;
        }
        throw new Error('Invalid response');
    } catch(error) {
        console.error(error);
    }
    return {};
}

export async function initAuthStore() {
    try {
        const accessToken = await ensureAccessToken();
        if (accessToken) {
            setAuthStoreByAccessToken(accessToken);
        }
    } catch(error) {
        console.error(error);
    }
}

export async function ensureAccessToken(): Promise<string> {
    try {
        const oldAccessToken = await getOldAccessToken();
        if (oldAccessToken) {
            const oldAccessTokenData: AccessTokenData = decodeAccessToken(oldAccessToken);
            const { expireAt } = oldAccessTokenData;
            const now = new Date();
            if (now.getTime()/1000 < expireAt) {
                return oldAccessToken;
            }
        }
        const oldRefreshToken = await getOldRefreshToken();
        if (oldRefreshToken) {
            const response = await axios.post(
                refreshTokenApiUrl,
                {access_token: oldAccessToken},
                {
                    headers: { Authorization: `Bearer ${oldRefreshToken}` }
                }
            );
            if (response && response.status == 200 && response.data && response.data.access_token && response.data.refresh_token) {
                const newAccessToken: string = response.data.access_token;
                const newRefreshToken: string = response.data.refresh_token;
                saveToken(newAccessToken, newRefreshToken);
                setAuthStoreByAccessToken(newAccessToken);
                return newAccessToken;
            }
            throw new Error('Invalid refresh-token response');
        }
        throw new Error('Cannot refresh token');
    } catch(error) {
        await logout();
        throw(error);
    }
}

async function getOldRefreshToken(): Promise<string | null | undefined> {
    const refreshTokenCookieKey = await getRefreshTokenCookieKey();
    return localStorage.getItem(refreshTokenCookieKey); 
}

async function getOldAccessToken(): Promise<string | null | undefined> {
    const accessTokenCookieKey = await getAccessTokenCookieKey();
    return Cookies.get(accessTokenCookieKey); 
}

export async function login(identity: string, password: string) {
    try {
        const response = await axios.post(loginApiUrl, {identity, password});
        if (response && response.status == 200 && response.data && response.data.access_token && response.data.refresh_token) {
            const accessToken: string = response.data.access_token;
            const refreshToken: string = response.data.refresh_token;
            await saveToken(accessToken, refreshToken);
            setAuthStoreByAccessToken(accessToken);
            return;
        }
        throw new Error('Unknown error');
    } catch(error) {
        await logout();
        throw(error);
    }
}

async function saveToken(accessToken: string, refreshToken: string) {
    const accessTokenCookieKey = await getAccessTokenCookieKey();
    const refreshTokenCookieKey = await getRefreshTokenCookieKey();
    Cookies.set(accessTokenCookieKey, accessToken);
    localStorage.setItem(refreshTokenCookieKey, refreshToken);
}

export async function logout() {
    const accessTokenCookieKey = await getAccessTokenCookieKey();
    const refreshTokenCookieKey = await getRefreshTokenCookieKey();
    Cookies.remove(accessTokenCookieKey);
    localStorage.removeItem(refreshTokenCookieKey);
    unsetAuthStore();
}

function unsetAuthStore() {
    setAuthStore('', '');
}

function setAuthStoreByAccessToken(accessToken: string) {
    const tokenData = decodeAccessToken(accessToken);
    setAuthStore(tokenData.sub.userId, tokenData.sub.userName);
}

function setAuthStore(newUserId: string, newUserName: string) {
    userIdStore.set(newUserId);
    userNameStore.set(newUserName);
}

function decodeAccessToken(accessToken: string): AccessTokenData {
    const jwtTokenData: {
        exp: number,
        sub: {
            user_id: string,
            username: string,
            expire_seconds: number
        }
    } = jwt_decode(accessToken);
    return {
        sub: {
            userId: jwtTokenData.sub.user_id,
            userName: jwtTokenData.sub.username,
            expireSeconds: jwtTokenData.sub.expire_seconds,
        },
        expireAt: jwtTokenData.exp
    }
}
