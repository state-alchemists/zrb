<script lang="ts">
    export let logo: string;
    export let brand: string;
    export let data: Array<{url: string, title: string}>;
</script>

<div class="navbar bg-base-100">
    <div class="flex-1">
        <img class="h-8 mr-3" src={logo} alt="Logo">
        <a href="/" class="btn btn-ghost normal-case text-xl">{brand}</a>
    </div>
    <div class="flex-none">
        <ul class="menu menu-horizontal px-1">
            {#each data as {url, title}}
                <li><a href={url} class="px-4">{title}</a></li>
            {/each}
        </ul>
    </div>
</div>