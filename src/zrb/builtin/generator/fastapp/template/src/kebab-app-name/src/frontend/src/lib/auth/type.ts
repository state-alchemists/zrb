export interface TokenData {
    sub: TokenDataSub;
    expireAt: number;
}

export interface TokenDataSub {
    userId: string;
    userName: string;
    expireSeconds: number;
}