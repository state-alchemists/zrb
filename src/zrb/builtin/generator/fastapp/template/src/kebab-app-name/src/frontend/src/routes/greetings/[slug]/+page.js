export function load({ params }) {
	return {
        title: 'hello ' + params.slug,
        content: 'hello ' + params.slug
	};
}