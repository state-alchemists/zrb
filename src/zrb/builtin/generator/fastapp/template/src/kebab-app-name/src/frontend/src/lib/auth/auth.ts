import axios from 'axios';
import jwt_decode from 'jwt-decode';
import { appAuthTokenCookieKey } from '../config/config';
import { getCookie, setCookie, unsetCookie } from '../cookie/cookie';
import { userIdStore, userNameStore } from './store';
import type { TokenData } from './type';

export async function refreshToken(refreshTokenUrl: string): Promise<boolean> {
    try {
        const oldToken: string = getCookie(appAuthTokenCookieKey);
        const oldTokenData: TokenData = decodeToken(oldToken);
        const { expireAt } = oldTokenData;
        const now = new Date();
        if (now.getTime()/1000 > expireAt) {
            throw new Error('Expired token');
        }
        const response = await axios.post(refreshTokenUrl, {token: oldToken});
        if (response && response.status == 200 && response.data && response.data.access_token) {
            const newToken: string = response.data.access_token;
            setCookie(appAuthTokenCookieKey, newToken);
            setAuthStoreByToken(newToken);
            return true;
        }
    } catch(error) {
        console.error(error);
    }
    logout();
    return false;
}

export async function login(loginUrl: string, identity: string, password: string): Promise<boolean> {
    try {
        const response = await axios.post(loginUrl, {identity, password});
        if (response && response.status == 200 && response.data && response.data.access_token) {
            const token: string = response.data.access_token;
            setCookie(appAuthTokenCookieKey, token);
            setAuthStoreByToken(token);
            return true;
        }
    } catch(error) {
        console.error(error);
    }
    logout();
    return false;
}

export function logout() {
    unsetCookie(appAuthTokenCookieKey)
    unsetAuthStore();
}

function unsetAuthStore() {
    setAuthStore('', '');
}

function setAuthStoreByToken(token: string) {
    const tokenData = decodeToken(token);
    setAuthStore(tokenData.sub.userId, tokenData.sub.userName);
}

function setAuthStore(newUserId: string, newUserName: string) {
    userIdStore.set(newUserId);
    userNameStore.set(newUserName);
}

function decodeToken(token: string): TokenData {
    const jwtTokenData: {
        exp: number,
        sub: {
            user_id: string,
            username: string,
            expire_seconds: number
        }
    } = jwt_decode(token);
    return {
        sub: {
            userId: jwtTokenData.sub.user_id,
            userName: jwtTokenData.sub.username,
            expireSeconds: jwtTokenData.sub.expire_seconds,
        },
        expireAt: jwtTokenData.exp
    }
}
