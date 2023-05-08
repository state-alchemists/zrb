<script lang="ts">
    import type {SingleNavData} from './type';
    export let data: SingleNavData;
</script>
{#if 'submenus' in data && data.submenus}
    <!-- svelte-ignore a11y-no-noninteractive-tabindex -->
    <li tabindex="0">
        <!-- svelte-ignore a11y-invalid-attribute -->
        <a href="#">
            Parent
            <svg class="fill-current" xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24"><path d="M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z"/></svg>
        </a>
        <ul class="p-2 bg-base-100 z-10">
            {#each data.submenus as submenu}
                <svelte:self data={submenu} />
            {/each}
        </ul>
      </li>
{:else}
    <li><a href={data.url} class="px-4">{data.title}</a></li>
{/if}
