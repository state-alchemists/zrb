<script lang="ts">
    import type {SingleNavData} from './type';
    export let singleNavData: SingleNavData;
    export let authorization: {[permission: string]: boolean} = {};
</script>
{#if (!singleNavData.permission || singleNavData.permission == '' ||  (authorization[singleNavData.permission]))}
    {#if 'submenus' in singleNavData && singleNavData.submenus}
        <!-- svelte-ignore a11y-no-noninteractive-tabindex -->
        <li tabindex="0">
            <a href="#top">
                {singleNavData.title}
                <svg class="fill-current" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><path d="M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z"/></svg>
            </a>
            <ul class="p-2 bg-base-100">
                {#each singleNavData.submenus as submenu}
                    <svelte:self singleNavData={submenu} authorization={authorization} />
                {/each}
            </ul>
        </li>
    {:else}
        <li><a href={singleNavData.url} class="px-4">{singleNavData.title}</a></li>
    {/if}
{/if}
