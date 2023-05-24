import type { SingleNavData } from '../components/navigation/type'

export const navData: SingleNavData[] = [
    {title: 'Home', url: '/'},
    {
        title: 'Auth',
        url: '#',
        submenus: [
            {title: 'Permission', url: '/auth/permission', permission: 'auth:permission:get'},
            {title: 'Group', url: '/auth/group', permission: 'auth:group:get'},
            {title: 'User', url: '/auth/user', permission: 'auth:user:get'},
        ]
    },
    {
        title: 'Log',
        url: '#',
        submenus: [
            {title: 'Activity', url: '/log/activity', permission: 'log:activity:get'},
        ]
    },
]