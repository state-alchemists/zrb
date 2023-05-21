export function load({ params }) {
    return {
        title: 'Greetings, ' + params.slug,
        content: 'Hello ' + params.slug
    };
}