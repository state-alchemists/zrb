<script lang="ts">
    import { onMount, onDestroy } from 'svelte';
    import { createEventDispatcher } from 'svelte';
    import { afterUpdate } from 'svelte';

    export let value: any = '';

    let dispatch = createEventDispatcher();
    let textarea: any;

    let textValue = JSON.stringify(value, null, 2);

    onMount(() => {
        textarea.value = textValue;
    });

    onDestroy(() => {
        textarea = null;
    });

    afterUpdate(() => {
        textarea.value = textValue;
    });

    function handleChange(event: any) {
        try {
            value = JSON.parse(event.target.value);
            textValue = event.target.value;
            dispatch('input', value);
        } catch (error) {
            // JSON parsing error
            console.error(error);
        }
    }
</script>
<textarea bind:this={textarea} on:input={handleChange} {...$$restProps}></textarea>