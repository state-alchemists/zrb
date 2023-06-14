<script lang="ts">
    import { goto } from '$app/navigation';
    import { onMount } from 'svelte';
    import Menu from './Menu.svelte';
    import type { SingleNavData } from './type';
    import { getAuthorization, initAuthStore, login, logout } from '../../auth/helper';
    import { userIdStore } from '../../auth/store';
	import { getNavDataPermissions } from './helper';
	import { getErrorMessage } from '$lib/error/helper';

    export let id: string = 'main-navbar';
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
    let isAlertVisible: boolean = false;
    let errorMessage: string = '';
    let isLoginModalOpen = false;

    userIdStore.subscribe(async (value) => {
        userId = value;
        authorization = await getAuthorization(navDataPermissions);
    });

    onMount(async() => {
        await initAuthStore();
    });

    async function onLoginClick(event: any) {
        try {
            await login(identity, password);
            isAlertVisible = false;
            isLoginModalOpen = false;
        } catch (error) {
            errorMessage = getErrorMessage(error);
            isAlertVisible = true;
        }
    }

    function onLoginLinkClick() {
        isLoginModalOpen = true;
    }

    async function onLogoutLinkClick() {
        await logout();
        await goto('/');
    }

    function closeDetails() {
        const details = document.querySelectorAll(`#${id} details[open]`);
        details.forEach(detail => {
            detail.removeAttribute('open');
        });
   }
</script>

<div id={id} class="navbar sticky top-0 bg-base-100 z-50">
    <div class="flex-1">
        <img class="h-8 mr-3" src={logo} alt="Logo">
        <a href="/" class="btn btn-ghost normal-case text-xl">{brand}</a>
    </div>
    <div class="flex-none">
        <ul class="menu menu-horizontal px-1">
            {#each navData as singleNavData}
                <Menu singleNavData={singleNavData} authorization={authorization} closeDetails={closeDetails} />
            {/each}
            {#if userId == ''}
                <li><a href="#login-modal" class="px-4" on:click={onLoginLinkClick}>{loginTitle}</a></li>
            {:else}
                <li><a href="#top" class="px-4" on:click={onLogoutLinkClick}>{logoutTitle}</a></li>
            {/if}
        </ul>
    </div>
</div>

<dialog class="modal" id="login-modal" class:modal-open={isLoginModalOpen}>
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
        <div class="alert alert-error shadow-lg mt-5 {isAlertVisible? 'visible': 'hidden'}">
            <div>
                <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current flex-shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span>{errorMessage}</span>
            </div>
        </div>
    </form>
</dialog>