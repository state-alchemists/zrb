<script lang="ts">
    import { goto } from '$app/navigation';
    import { onMount } from 'svelte';
    import Menu from './Menu.svelte';
    import type { SingleNavData } from './type';
    import { getAuthorization, initAuthStore, login, logout } from '../../auth/helper';
    import { userIdStore } from '../../auth/store';
	import { getNavDataPermissions } from './helper';

    export let logo: string;
    export let brand: string;
    export let navData: SingleNavData[];
    export let loginTitle: string = 'Login';
    export let logoutTitle: string = 'Logout';

    const navDataPermissions = getNavDataPermissions(navData);

    let identity: string;
    let password: string;
    let userId = '';
    let authorization: {[key: string]: boolean} = {};

    userIdStore.subscribe(async (value) => {
        userId = value;
        authorization = await getAuthorization(navDataPermissions);
    });

    onMount(async() => {
        await initAuthStore();
    });

    async function onLoginClick() {
        const loginSuccess = await login(identity, password);
        if (loginSuccess) {
            await goto('/');
            return;
        }
        alert('salah');
    }

    async function onLogoutClick() {
        logout();
        await goto('/');
    }
</script>

<div class="navbar sticky top-0 bg-base-100 z-50">
    <div class="flex-1">
        <img class="h-8 mr-3" src={logo} alt="Logo">
        <a href="/" class="btn btn-ghost normal-case text-xl">{brand}</a>
    </div>
    <div class="flex-none">
        <ul class="menu menu-horizontal px-1">
            {#each navData as singleNavData}
                <Menu singleNavData={singleNavData} authorization={authorization} />
            {/each}
            {#if userId == ''}
                <li><a href="#login-modal" class="px-4">{loginTitle}</a></li>
            {:else}
                <li><a href="#top" class="px-4" on:click={onLogoutClick}>{logoutTitle}</a></li>
            {/if}
        </ul>
    </div>
</div>

<div class="modal" id="login-modal">
    <form class="modal-box">
        <div class="mb-6">
            <label class="block text-gray-700 font-bold mb-2" for="identity">Identity</label>
            <input class="w-full px-3 py-2 border rounded-lg text-gray-700 focus:outline-none focus:shadow-outline" id="identity" type="text" placeholder="Enter your username/email/phone" bind:value={identity} />
        </div>
        <div class="mb-6">
            <label class="block text-gray-700 font-bold mb-2" for="password">Password</label>
            <input class="w-full px-3 py-2 border rounded-lg text-gray-700 focus:outline-none focus:shadow-outline" id="password" type="password" placeholder="Enter your password" bind:value={password} />
        </div>
        <div class="modal-action">
            <a href="#top" class="btn btn-primary" on:click={onLoginClick}>Sign in</a>
        </div>
    </form>
</div>