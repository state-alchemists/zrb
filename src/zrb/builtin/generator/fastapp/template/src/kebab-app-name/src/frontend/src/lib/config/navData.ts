import type { SingleNavData } from '../components/navigation/type'

export const navData: SingleNavData[] = [
    {"title": "Home", "url": "/"},
    {"title": "About", "url": "/about"},
    {"title": "Greetings, Lord", "url": "/greetings/Lord"},
    {
        "title": "Test",
        "url": "#",
        "submenus": [
            {"title": "Sub 1", "url": "/"},
            {"title": "Sub 2 long long title", "url": "/about"}
        ]
    },
    {
        "title": "Sample url",
        "url": "/sample"
    }
]