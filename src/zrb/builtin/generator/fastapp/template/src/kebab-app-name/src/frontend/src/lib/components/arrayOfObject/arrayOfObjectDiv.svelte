<script lang="ts">
    export let data: any[] = [];
    export let captionKey: string = '';
    export let separator: string = ', ';
    export let itemPerRow: number = 5;

    function rowToStr(row: any): string {
        if (captionKey == '') {
            return JSON.stringify(row)
        }
        return row[captionKey];
    }

    function dataToStr(data: any[]) {
        data.map((row) => rowToStr(row)).join(separator)
    }
</script>
{#each data as row, index}
    <div class="badge" {...$$restProps}>{rowToStr(row)}</div>
    {#if index != 0 && (index + 1) % itemPerRow == 0}<br />{/if}
{/each}
