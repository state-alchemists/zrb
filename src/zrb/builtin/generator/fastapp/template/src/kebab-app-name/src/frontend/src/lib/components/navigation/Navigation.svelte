<script lang="ts">
    import {login, logout} from '$lib/auth/auth';
    import {goto} from '$app/navigation';
    import type {SingleNavData} from './type';
    import Menu from './Menu.svelte';
    import {getCookie} from '../../cookie/cookie';

    export let logo: string;
    export let brand: string;
    export let data: SingleNavData[];
    export let authTokenCookieKey: string;
    export let loginTitle: string = 'Login';
    export let logoutTitle: string = 'Logout';

    const authToken = getCookie(authTokenCookieKey);
    let hasToken = authToken != '';

    let identity: string;
    let password: string;

    async function onLoginClick() {
        const loginSuccess = await login('/api/v1/auth/login', identity, password);
        if (loginSuccess) {
            hasToken = true;
            await goto('/');
            return;
        }
        alert('salah');
    }

    async function onLogoutClick() {
        logout();
        hasToken = false;
        await goto('/');
    }
</script>

<div class="navbar sticky top-0 bg-base-100">
    <div class="flex-1">
        <img class="h-8 mr-3" src={logo} alt="Logo">
        <a href="/" class="btn btn-ghost normal-case text-xl">{brand}</a>
    </div>
    <div class="flex-none">
        <ul class="menu menu-horizontal px-1">
            {#each data as menuData}
                <Menu data={menuData} />
            {/each}
            {#if !hasToken}
                <li><a href="#login-modal" class="px-4">{loginTitle}</a></li>
            {:else}
                <li><a href="#" class="px-4" on:click={onLogoutClick}>{logoutTitle}</a></li>
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
            <a href="#" class="btn btn-primary" on:click={onLoginClick}>Sign in</a>
        </div>
    </form>
</div>