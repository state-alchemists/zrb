<script lang="ts">
    import { beforeUpdate } from 'svelte';
    import type {SingleNavData} from './type';
    export let singleNavData: SingleNavData;
    export let authorization: {[permission: string]: boolean} = {};
    export let closeDetails: () => any = () => null;
    let isAuthorized: boolean = false;

    beforeUpdate(() => {
        isAuthorized = shouldShowSingleNavData(singleNavData, authorization);
    });

    function shouldShowSingleNavData(singleNavData: SingleNavData, authorization: {[permission: string]: boolean}): boolean {
        if (singleNavData.submenus) {
            for (const submenu of singleNavData.submenus) {
                if (shouldShowSingleNavData(submenu, authorization)) {
                    return true;
                }
            }
            return false;
        }
        return !singleNavData.permission || singleNavData.permission == '' || authorization[singleNavData.permission]
    }

</script>
{#if isAuthorized}
    {#if 'submenus' in singleNavData && singleNavData.submenus}
        {#if singleNavData.submenus.length > 0 }
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
        {/if}
    {:else}
        <li><a href={singleNavData.url} on:click={closeDetails}>{singleNavData.title}</a></li>
    {/if}
{/if}
