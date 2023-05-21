<script lang="ts">
    import axios from 'axios';
	import { ensureAccessToken } from '$lib/auth/helper';
	import { onMount } from 'svelte';

    let limit: number = 5;
    let pageIndex: number = 0;
    let count: number = 0;
    let keyword: string = '';
    let isAlertVisible: boolean = false;
    let errorMessage: string = '';

    let limitOptions: Array<number> = [5, 10, 30, 50, 100];
    let pageIndexes: Array<number> = [];
    let data: Array<any> = [];
    

    onMount(async() => {
        await loadData();
    });

    async function loadData() {
        const accessToken = await ensureAccessToken();
        try {
            const encodedKeyword = encodeURIComponent(keyword);
            const offset = limit * pageIndex
            const response = await axios.get(
                `/api/v1/library/books?limit=${limit}&offset=${offset}&keyword=${encodedKeyword}`,
                {headers: {Authorization: `Bearer ${accessToken}`}}
            );
            if (response?.status == 200 && response?.data) {
                count = response.data.count;
                data = response.data.data;
                pageIndexes = [];
                for (let i = 0; i*limit < count; i++)  {
                    pageIndexes.push(i);
                }
                return;
            }
            errorMessage = 'Unknown error';
        } catch(error) {
            console.error(error);
        }
        isAlertVisible = true;
    }

    async function onPaginationClick(index: number) {
        pageIndex = index;
        await loadData();
    }

</script>

<h1 class="text-3xl">Book</h1>
<div class="overflow-x-auto">

    <div class="flex items-center mb-5 mt-5">
        <label for="limit" class="mr-2">Row per page:</label>
        <select id="limit" class="select select-bordered mr-2" bind:value={limit} on:change={loadData}>
            {#each limitOptions as limitOption}
                {#if limitOption == limit }
                    <option selected>{limitOption}</option>
                {:else}
                    <option>{limitOption}</option>
                {/if}
            {/each}
        </select>
        <input type="text" placeholder="Search..." class="input input-bordered mr-2" bind:value={keyword} />
        <button class="btn btn-primary btn-square" on:click={loadData}>
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
        </button>
        <a class="btn ml-5" href="./new">New</a>
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
                <th>Code</th>
                <th>Title</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
            {#each data as row}
                <tr>
                    <th>{row.id}</th>
                    <td>{row.code}</td>
                    <td>{row.title}</td>
                    <td>
                        <a class="btn" href="./detail/{row.id}">Detail</a>
                        <a class="btn" href="./update/{row.id}">Update</a>
                        <a class="btn btn-accent" href="./delete/{row.id}">Delete</a>
                    </td>
                </tr>
            {/each}
        </tbody>
    </table>

    <div class="btn-group justify-center w-full">
        {#each pageIndexes as pageIndexOption}
            {#if pageIndexOption == pageIndex}
                <button class="btn btn-disabled">{pageIndexOption + 1}</button>
            {:else}
                <button class="btn" on:click={async () => await onPaginationClick(pageIndexOption)}>
                    {pageIndexOption + 1}
                </button>
            {/if}
        {/each}
    </div>
</div>