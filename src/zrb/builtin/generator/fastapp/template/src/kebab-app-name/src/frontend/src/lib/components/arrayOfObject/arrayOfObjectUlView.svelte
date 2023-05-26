<script lang="ts">
    export let data: any[] = [];
    export let captionKey: string = '';

    function rowToStr(row: any): string {
        if (captionKey == '') {
            return JSON.stringify(row)
        }
        return row[captionKey];
    }
</script>
<ul {...$$restProps}>
    {#each data as row}
        <li>{rowToStr(row)}</li>
    {/each}
</ul>
