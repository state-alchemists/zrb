<script lang="ts">
	import { onMount } from "svelte";

    export let value: string[] = [];
    export let placeholder: string = 'Keyword';
    export let valueKey: string;
    export let captionKey: string;
    export let caption: string = '';
    export let fetchOptions: (keyword: string) => Promise<any>;

    let keyword: string = '';
    let options: any[] = [];

    function handleCheckboxChange(event: any) {
        const inputChecked: boolean = event.target.checked;
        const inputValue: string = event.target.value;
        if (inputChecked && value.indexOf(inputValue) == -1) {
            // Note: svelte reactivity is based on assignment, so data.push won't work
            value = [...value, inputValue];
            return;
        }
        if (!inputChecked && value.indexOf(inputValue) != -1) {
            value = value.filter((dataValue) => dataValue != inputValue);
            return;
        }
    }

    async function onKeywordChange() {
       options = await fetchOptions(keyword);
    }

    onMount(async () => {
        options = await fetchOptions(keyword);
    })
</script>
<input 
    class="input input-bordered w-full max-w-xs"
    type="text"
    placeholder={placeholder}
    bind:value={keyword}
    on:input={onKeywordChange}
    {...$$restProps}
/>
<table>
    <thead>
        <tr>
            <th></th>
            <th>{caption? caption: captionKey}</th>
        </tr>
    </thead>
    <tbody>
        {#each options as option}
            <tr>
                <td>
                    <input
                        type="checkbox"
                        value={option[valueKey]}
                        checked={value.indexOf(option[valueKey]) != -1}
                        on:change={handleCheckboxChange}
                    />
                </td>
                <td>{option[captionKey]}</td>
            </tr>
        {/each}
    </tbody>
</table>