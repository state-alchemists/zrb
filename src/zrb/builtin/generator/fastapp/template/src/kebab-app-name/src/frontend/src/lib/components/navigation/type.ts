export interface SingleNavData {
    url: string;
    title: string;
    permission?: string;
    submenus?: SingleNavData[];
}