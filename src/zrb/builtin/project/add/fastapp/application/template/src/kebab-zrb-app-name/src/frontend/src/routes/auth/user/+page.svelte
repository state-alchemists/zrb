<script lang="ts">
    import axios from 'axios';
	import { onMount } from 'svelte';
    import { goto } from '$app/navigation';
	import { ensureAccessToken, getAuthorization } from '$lib/auth/helper';
	import { getErrorMessage } from '$lib/error/helper';
	import ArrayOfObjectDiv from '$lib/components/arrayOfObject/arrayOfObjectDiv.svelte';

    let limit: number = 5;
    let pageIndex: number = 0;
    let count: number = 0;
    let keyword: string = '';
    let isAlertVisible: boolean = false;
    let errorMessage: string = '';
    let allowGet: boolean = false;
    let allowGetById: boolean = false;
    let allowInsert: boolean = false;
    let allowUpdate: boolean = false;
    let allowDelete: boolean = false;

    let limitOptions: Array<number> = [5, 10, 30, 50, 100];
    let pageIndexes: Array<number> = [];
    let rows: Array<any> = [];
    
    onMount(async() => {
        await loadAuthorization();
        if (!allowGet) {
            goto('/');
        }
        await loadRows();
    });

    async function loadAuthorization() {
        const authorization = await getAuthorization([
            'auth:user:get',
            'auth:user:get_by_id',
            'auth:user:insert',
            'auth:user:update',
            'auth:user:delete'
        ]);
        allowGet = authorization['auth:user:get'] || false;
        allowGetById = authorization['auth:user:get_by_id'] || false;
        allowInsert = authorization['auth:user:insert'] || false;
        allowUpdate = authorization['auth:user:update'] || false;
        allowDelete = authorization['auth:user:delete'] || false;
    }

    async function loadRows() {
        const accessToken = await ensureAccessToken();
        try {
            const encodedKeyword = encodeURIComponent(keyword);
            const offset = limit * pageIndex
            const response = await axios.get(
                `/api/v1/auth/users?limit=${limit}&offset=${offset}&keyword=${encodedKeyword}`,
                {headers: {Authorization: `Bearer ${accessToken}`}}
            );
            if (response?.status == 200 && response?.data) {
                count = response.data.count;
                rows = response.data.data;
                pageIndexes = [];
                for (let i = 0; i*limit < count; i++)  {
                    pageIndexes.push(i);
                }
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

    async function onPaginationClick(index: number) {
        pageIndex = index;
        await loadRows();
    }
</script>

<h1 class="text-3xl">User</h1>
<div class="overflow-x-auto">

    <div class="flex items-center mb-5 mt-5">
        <label for="limit" class="mr-2">Row per page:</label>
        <select id="limit" class="select select-bordered mr-2" bind:value={limit} on:change={loadRows}>
            {#each limitOptions as limitOption}
                {#if limitOption == limit }
                    <option selected>{limitOption}</option>
                {:else}
                    <option>{limitOption}</option>
                {/if}
            {/each}
        </select>
        <input type="text" placeholder="Search..." class="input input-bordered mr-2" bind:value={keyword} />
        <button class="btn btn-primary btn-square" on:click={loadRows}>
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
        </button>
        {#if allowInsert}
            <a class="btn ml-5" href="./new">New</a>
        {/if}
    </div>

    <div class="alert alert-error shadow-lg mt-5 mb-5 {isAlertVisible? 'visible': 'hidden'}">
        <div>
            <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current flex-shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
            <span>{errorMessage}</span>
        </div>
    </div>

    <table class="table w-full">
        <!-- head -->
        <thead>
            <tr>
                <th></th>
                <th>Username</th>
                <th>Phone</th>
                <th>Email</th>
                <th>Groups</th>
                <th>Permissions</th>
                <th>Description</th>
                <!-- DON'T DELETE: insert new column header here-->
                <th></th>
            </tr>
        </thead>
        <tbody>
            {#each rows as row}
                <tr>
                    <th>{row.id}</th>
                    <td>{row.username}</td>
                    <td>{row.phone}</td>
                    <td>{row.email}</td>
                    <td>
                        <ArrayOfObjectDiv class="badge badge-outline mr-2" data={row.groups} captionKey="name" />
                    </td>
                    <td>
                        <ArrayOfObjectDiv class="badge badge-outline mr-2" data={row.permissions} captionKey="name" />
                    </td>
                    <td>{row.description}</td>
                    <!-- DON'T DELETE: insert new column here-->
                    <td>
                        {#if allowGetById}
                            <a class="btn" href="./detail/{row.id}">Detail</a>
                        {/if}
                        {#if allowUpdate}
                            <a class="btn" href="./update/{row.id}">Update</a>
                        {/if}
                        {#if allowDelete}
                            <a class="btn btn-accent" href="./delete/{row.id}">Delete</a>
                        {/if}
                    </td>
                </tr>
            {/each}
        </tbody>
    </table>

    <div class="join mt-5 justify-center w-full">
        {#each pageIndexes as pageIndexOption}
            {#if pageIndexOption == pageIndex}
                <button class="btn btn-disabled join-item">{pageIndexOption + 1}</button>
            {:else}
                <button class="btn join-item" on:click={async () => await onPaginationClick(pageIndexOption)}>
                    {pageIndexOption + 1}
                </button>
            {/if}
        {/each}
    </div>
</div>