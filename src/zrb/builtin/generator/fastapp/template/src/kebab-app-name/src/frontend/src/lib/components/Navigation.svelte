<script lang="ts">
    export let logo: string;
    export let brand: string;
    export let data: Array<{url: string, title: string}>;
</script>

<nav class="flex flex-wrap items-center justify-between w-full py-4 md:py-0 px-4 text-lg text-gray-700 bg-white">
    <div class="flex items-center">
        <img class="h-8 mr-3" src={logo} alt="Logo">
        <a href="/" class="font-semibold">{brand}</a>
    </div>
    <div class="block md:hidden">
        <button class="flex items-center px-3 py-2 border rounded text-gray-500 border-gray-600 hover:text-black hover:border-black">
            <svg class="h-3 w-3 fill-current" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"><title>Menu</title><path d="M0 3h20v2H0V3zm0 6h20v2H0V9zm0 6h20v2H0v-2z"/></svg>
        </button>
    </div>
    <div class="hidden md:block">
        <ul class="inline-flex">
            {#each data as {url, title}}
                <li><a href={url} class="px-4">{title}</a></li>
            {/each}
        </ul>
    </div>
</nav>