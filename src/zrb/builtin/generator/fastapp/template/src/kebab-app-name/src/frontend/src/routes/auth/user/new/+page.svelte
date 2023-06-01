<script lang="ts">
    import axios from 'axios';
	import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
	import { ensureAccessToken, getAuthorization } from '$lib/auth/helper';
    import { getErrorMessage } from '$lib/error/helper';
    import ArrayOfObjectCheckboxes from '$lib/components/arrayOfObject/input/arrayOfObjectCheckboxes.svelte';

    let row: any = {}
    let isAlertVisible: boolean = false;
    let isSaving: boolean = false;
    let errorMessage: string = '';
    let allowInsert: boolean = false;

    onMount(async() => {
        await loadAuthorization();
        if (!allowInsert) {
            goto('/');
        }
        row.username = '';
        row.phone = '';
        row.email = '';
        row.password = '';
        row.groups = [];
        row.permissions = [];
        row.description = '';
        // DON'T DELETE: set field default value here
    });

    async function loadAuthorization() {
        const authorization = await getAuthorization([
            'auth:user:insert',
        ]);
        allowInsert = authorization['auth:user:insert'] || false;
    }

    async function onSaveClick() {
        isSaving = true
        const accessToken = await ensureAccessToken();
        try {
            const response = await axios.post(
                '/api/v1/auth/users', row, {headers: {Authorization: `Bearer ${accessToken}`}}
            );
            if (response?.status == 200) {
                errorMessage = '';
                isAlertVisible = false;
                await goto('../');
                return;
            }
            errorMessage = 'Unknown error';
        } catch(error) {
            console.error(error);
            errorMessage = getErrorMessage(error);
        }
        isAlertVisible = true;
        isSaving = false;
    }

    async function fetchPermissions(keyword: string): Promise<any[]> {
        const accessToken = await ensureAccessToken();
        try {
            const encodedKeyword = encodeURIComponent(keyword);
            const response = await axios.get(
                `/api/v1/auth/permissions?limit=30&keyword=${encodedKeyword}`,
                {headers: {Authorization: `Bearer ${accessToken}`}}
            );
            if (response?.status == 200 && response?.data?.data) {
                return response.data.data;
            }
            errorMessage = 'Unknown error';
        } catch(error) {
            console.error(error);
            errorMessage = getErrorMessage(error);
        }
        isAlertVisible = true;
        return [];
    }

    async function fetchGroups(keyword: string): Promise<any[]> {
        const accessToken = await ensureAccessToken();
        try {
            const encodedKeyword = encodeURIComponent(keyword);
            const response = await axios.get(
                `/api/v1/auth/groups?limit=30&keyword=${encodedKeyword}`,
                {headers: {Authorization: `Bearer ${accessToken}`}}
            );
            if (response?.status == 200 && response?.data?.data) {
                return response.data.data;
            }
            errorMessage = 'Unknown error';
        } catch(error) {
            console.error(error);
            errorMessage = getErrorMessage(error);
        }
        isAlertVisible = true;
        return [];
    }
</script>

<h1 class="text-3xl">User</h1>

<form class="max-w-md mx-auto bg-gray-100 p-6 rounded-md mt-5 mb-5">
  <h2 class="text-xl font-bold mb-4">New User</h2>
    <div class="mb-4">
        <label class="block text-gray-700 font-bold mb-2" for="username">Username</label>
        <input type="text" class="input w-full" id="username" placeholder="Username" bind:value={row.username} />
    </div>
    <div class="mb-4">
        <label class="block text-gray-700 font-bold mb-2" for="phone">Phone</label>
        <input type="text" class="input w-full" id="phone" placeholder="phone" bind:value={row.phone} />
    </div>
    <div class="mb-4">
        <label class="block text-gray-700 font-bold mb-2" for="email">Email</label>
        <input type="email" class="input w-full" id="email" placeholder="email" bind:value={row.email} />
    </div>
    <div class="mb-4">
        <label class="block text-gray-700 font-bold mb-2" for="password">Password</label>
        <input type="password" class="input w-full" id="password" placeholder="password" bind:value={row.password} />
    </div>
    <div class="mb-4">
        <label class="block text-gray-700 font-bold mb-2" for="groups">Groups</label>
        <ArrayOfObjectCheckboxes class="input w-full input-bordered max-w-xs" id="groups" valueKey="id" captionKey="name" caption="Groups" placeholder="Filter groups" fetchOptions={fetchGroups} bind:value={row.groups} />
    </div>
    <div class="mb-4">
        <label class="block text-gray-700 font-bold mb-2" for="permissions">Permissions</label>
        <ArrayOfObjectCheckboxes class="input w-full input-bordered max-w-xs" id="permissions" valueKey="id" captionKey="name" caption="Permissions" placeholder="Filter permissions" fetchOptions={fetchPermissions} bind:value={row.permissions} />
    </div>
    <div class="mb-4">
        <label class="block text-gray-700 font-bold mb-2" for="description">Description</label>
        <input type="text" class="input w-full" id="description" placeholder="Description" bind:value={row.description} />
    </div>
    <!-- DON'T DELETE: insert new field here-->
    <a href="#top" class="btn btn-primary {isSaving ? 'btn-disabled': '' }" on:click={onSaveClick}>Save</a>
    <a href="../" class="btn">Cancel</a>

    <div class="alert alert-error shadow-lg mt-5 {isAlertVisible? 'visible': 'hidden'}">
        <div>
            <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current flex-shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <span>{errorMessage}</span>
        </div>
    </div>

</form>