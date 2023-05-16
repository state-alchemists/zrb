import type { SingleNavData } from '../components/navigation/type'

export const navData: SingleNavData[] = [
    {title: 'Home', url: '/'},
    {
        title: 'Auth',
        url: '#',
        submenus: [
            {title: 'Permission', url: 'auth/permission', permission: 'auth:permission:get'},
            {title: 'Group', url: 'auth/group', permission: 'auth:group:get'},
            {title: 'User', url: 'auth/user', permission: 'auth:user:get'},
        ]
    },
    {title: 'About', url: '/about'},
    {title: 'Greetings, Lord', url: '/greetings/Lord'},
    {
        title: 'Test',
        url: '#',
        submenus: [
            {title: 'Sub 1', url: '/'},
            {title: 'Sub 2 long long title', url: '/about'}
        ]
    },
    {title: 'Sample url', url: '/sample'},
]