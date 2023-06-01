<script lang="ts">
    import type {SingleNavData} from './type';
    export let singleNavData: SingleNavData;
    export let authorization: {[permission: string]: boolean} = {};
    export let closeDetails: () => any = () => null;
</script>
{#if (!singleNavData.permission || singleNavData.permission == '' ||  (authorization[singleNavData.permission]))}
    {#if 'submenus' in singleNavData && singleNavData.submenus}
        <!-- svelte-ignore a11y-no-noninteractive-tabindex -->
        <li>
            <details>
                <summary>{singleNavData.title}</summary>
                <ul class="p-2 bg-base-100">
                    {#each singleNavData.submenus as submenu}
                        <svelte:self singleNavData={submenu} authorization={authorization} closeDetails={closeDetails} />
                    {/each}
                </ul>
            </details>
        </li>
    {:else}
        <li><a href={singleNavData.url} on:click={closeDetails}>{singleNavData.title}</a></li>
    {/if}
{/if}
