import type { SingleNavData } from "./type";

export function getNavDataPermissions(navData: SingleNavData[]): string[] {
    let permissions: string[] = [];
    for (const singleNavData of navData) {
        if (singleNavData.permission && singleNavData.permission != '') {
            permissions.push(singleNavData.permission);
        }
        if (singleNavData.submenus) {
            const subPermissions: string[] = getNavDataPermissions(singleNavData.submenus);
            const uniqueSubPermissions = subPermissions.filter((value) => {
                return permissions.indexOf(value) === -1
            });
            permissions = permissions.concat(uniqueSubPermissions)
        }
    }
    return permissions
}