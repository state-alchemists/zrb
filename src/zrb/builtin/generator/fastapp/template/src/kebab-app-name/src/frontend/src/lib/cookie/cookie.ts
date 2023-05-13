export function setCookie(cookieName: string, cookieValue: string) {
    document.cookie = cookieName + '=' + cookieValue + ';path=/';
}

export function unsetCookie(cookieName: string) {
    document.cookie = cookieName + '=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/'
}

export function getCookie(cookieName: string): string {
    let valuePrefix = cookieName + '=';
    let cookieParts = document.cookie.split(';');
    for(let partIndex = 0; partIndex < cookieParts.length; partIndex++) {
        let cookiePart = cookieParts[partIndex].trim();
        if (cookiePart.indexOf(valuePrefix) == 0) {
            return cookiePart.substring(valuePrefix.length, cookiePart.length);
        }
    }
    return '';
}