<script lang="ts">
    import axios from 'axios';
	import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
	import { ensureAccessToken, getAuthorization } from '$lib/auth/helper';
    import { getErrorMessage } from '$lib/error/helper';
	import ArrayOfObjectUl from '$lib/components/arrayOfObject/arrayOfObjectUl.svelte';

    export let data: {id?: string} = {};

    let row: any = {};
    let isAlertVisible: boolean = false;
    let errorMessage: string = '';
    let allowDelete: boolean = false;
 
    onMount(async() => {
        await loadAuthorization();
        if (!allowDelete) {
            goto('/');
        }
        await loadRow();
    });

    async function loadAuthorization() {
        const authorization = await getAuthorization([
            'auth:user:delete',
        ]);
        allowDelete = authorization['auth:user:delete'] || false;
    }

    async function loadRow() {
        const accessToken = await ensureAccessToken();
        try {
            const response = await axios.get(
                `/api/v1/auth/users/${data.id}`,
                {headers: {Authorization: `Bearer ${accessToken}`}}
            );
            if (response?.status == 200 && response?.data) {
                row = response.data;
                errorMessage = '';
                isAlertVisible = false;
                return;
            }
            errorMessage = 'Unknown error';
            isAlertVisible = true;
        } catch(error) {
            console.error(error);
            errorMessage = getErrorMessage(error);
            isAlertVisible = true;
        }
    }

    async function onDeleteClick() {
        const accessToken = await ensureAccessToken();
        try {
            const response = await axios.delete(
                `/api/v1/auth/users/${data.id}`,
                {headers: {Authorization: `Bearer ${accessToken}`}}
            );
            if (response?.status == 200 && response?.data) {
                errorMessage = '';
                isAlertVisible = false;
                await goto('../../');
                return;
            }
            errorMessage = 'Unknown error';
            isAlertVisible = true;
        } catch(error) {
            console.error(error);
            errorMessage = getErrorMessage(error);
            isAlertVisible = true;
        }
    }
</script>
<h1 class="text-3xl">User</h1>

<form class="max-w-md mx-auto bg-gray-100 p-6 rounded-md mt-5 mb-5">
  <h2 class="text-xl font-bold mb-4">Delete User {data.id}</h2>
    <div class="mb-4">
        <label class="block text-gray-700 font-bold mb-2" for="username">Username</label>
        <span id="username">{row.username}</span>
    </div>
    <div class="mb-4">
        <label class="block text-gray-700 font-bold mb-2" for="phone">Phone</label>
        <span id="phone">{row.phone}</span>
    </div>
    <div class="mb-4">
        <label class="block text-gray-700 font-bold mb-2" for="email">Email</label>
        <span id="email">{row.email}</span>
    </div>
    <div class="mb-4">
        <label class="block text-gray-700 font-bold mb-2" for="groups">Groups</label>
        <ArrayOfObjectUl id="groups" class="list-disc list-inside" data={row.groups} captionKey="name" />
    </div>
    <div class="mb-4">
        <label class="block text-gray-700 font-bold mb-2" for="permissions">Permissions</label>
        <ArrayOfObjectUl id="permissions" class="list-disc list-inside" data={row.permissions} captionKey="name" />
    </div>
    <div class="mb-4">
        <label class="block text-gray-700 font-bold mb-2" for="description">Description</label>
        <span id="description">{row.description}</span>
    </div>
    <!-- DON'T DELETE: insert new field here-->
    <a href="#top" class="btn btn-accent" on:click={onDeleteClick}>Delete</a>
    <a href="../../" class="btn">Cancel</a>

    <div class="alert alert-error shadow-lg mt-5 {isAlertVisible? 'visible': 'hidden'}">
        <div>
            <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current flex-shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <span>{errorMessage}</span>
        </div>
    </div>

</form>