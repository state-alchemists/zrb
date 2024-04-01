export interface AccessTokenData {
    sub: AccessTokenDataSub;
    expireAt: number;
}

export interface AccessTokenDataSub {
    userId: string;
    userName: string;
    expireSeconds: number;
}